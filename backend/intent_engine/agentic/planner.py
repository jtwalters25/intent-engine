"""Deterministic Phase 2 intent planning.

The planner converts a structured ``ContextInterpretation`` into an
``IntentPlan``.  It does not accept candidates, import ranking code, or confer
authority on constraints produced by interpretation.  Every returned plan has
crossed the Phase 1 validation boundary.
"""

from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
import re
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from pydantic import ValidationError

from intent_engine.agentic.schemas import (
    ConstraintSource,
    ContextInterpretation,
    IntentConstraint,
    IntentPlan,
    IntentStep,
)
from intent_engine.agentic.validator import PlanValidationError, PlanValidator
from intent_engine.schemas import Domain


RULE_BASED_PLANNER_VERSION = "v4-rule-based-1"
SUPPORTED_OBJECTIVES = frozenset(
    {"wind_down", "focus", "family_time", "quick_session", "high_energy"}
)
SUPPORTED_PLANNING_DOMAINS = frozenset({Domain.STREAMING})

DEFAULT_CURRENT_ENERGY = 0.5
DEFAULT_VIEWER = "family"
MAX_HORIZON_MINUTES = 240

DEFAULT_HORIZON_MINUTES = MappingProxyType(
    {
        "wind_down": 60,
        "focus": 45,
        "family_time": 90,
        "quick_session": 20,
        "high_energy": 45,
    }
)

MIN_HORIZON_MINUTES = MappingProxyType(
    {
        "wind_down": 15,
        "focus": 10,
        "family_time": 15,
        "quick_session": 5,
        "high_energy": 10,
    }
)

_OBJECTIVE_ALIASES = MappingProxyType(
    {
        "wind_down": "wind_down",
        "winddown": "wind_down",
        "focus": "focus",
        "family_time": "family_time",
        "family": "family_time",
        "quick_session": "quick_session",
        "quick": "quick_session",
        "high_energy": "high_energy",
        "energetic": "high_energy",
    }
)

_NONCANONICAL_SIGNAL_NAMES = frozenset(
    {
        "energy_level",
        "energyLevel",
        "viewer_profile",
    }
)

_DEFAULTABLE_MISSING_FIELDS = frozenset(
    {
        "energy",
        "current_energy",
        "viewer",
        "viewer_profile",
        "horizon",
        "horizon_minutes",
        "plan_horizon",
    }
)

_VIEWERS = frozenset({"kids", "teen", "family", "adult"})


class PlanningError(ValueError):
    """A fail-closed planner error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@runtime_checkable
class IntentPlanner(Protocol):
    """Interface for components that produce plans but never rank candidates."""

    def create_plan(
        self,
        interpretation: ContextInterpretation,
        domain: Domain,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> IntentPlan:
        ...


class RuleBasedIntentPlanner:
    """Small, deterministic planner for the V4 streaming pilot."""

    def __init__(self, validator: Optional[PlanValidator] = None) -> None:
        self._validator = PlanValidator() if validator is None else validator

    def create_plan(
        self,
        interpretation: ContextInterpretation,
        domain: Domain,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> IntentPlan:
        """Create and validate a deterministic plan.

        ``now`` and ``authoritative_constraints`` are trusted caller inputs.
        Neither is derived from the interpretation.
        """
        if not isinstance(now, datetime):
            raise PlanningError("invalid_now", "trusted now must be a datetime")

        selected_domain = self._normalize_domain(domain)
        if selected_domain not in SUPPORTED_PLANNING_DOMAINS:
            raise PlanningError(
                "unsupported_domain",
                "Phase 2 rule-based planning supports the streaming domain only",
            )

        checked_interpretation = self._validate_interpretation(interpretation)
        objective = self._normalize_objective(checked_interpretation.objective)
        self._reject_noncanonical_signals(checked_interpretation)
        self._validate_missing_information(checked_interpretation)

        trusted_constraints = self._validate_authoritative_constraints(
            authoritative_constraints
        )
        interpreted_constraints = self._validate_interpreted_constraints(
            checked_interpretation.explicit_constraints
        )
        constraints = trusted_constraints + interpreted_constraints

        assumptions = list(checked_interpretation.assumptions)
        current_energy = self._resolve_energy(checked_interpretation, assumptions)
        viewer = self._resolve_viewer(checked_interpretation, assumptions)
        horizon = self._resolve_horizon(
            checked_interpretation,
            objective,
            assumptions,
        )

        if interpreted_constraints:
            assumptions.append(
                "Interpreted USER/INFERRED constraints remain non-authoritative; "
                "only caller-supplied hard constraints are authoritative."
            )

        assumptions = self._deduplicate(assumptions)
        desired_state, step_specs = self._build_objective_plan(
            objective=objective,
            current_energy=current_energy,
            viewer=viewer,
            horizon_minutes=horizon,
        )

        current_state = {
            "energy": current_energy,
            "viewer": viewer,
        }
        draft_steps = [
            IntentStep(
                step_id=f"draft_step_{index + 1}",
                offset_minutes=offset,
                intent=intent,
                transition_reason=reason,
            )
            for index, (offset, intent, reason) in enumerate(step_specs)
        ]

        try:
            draft = IntentPlan(
                plan_id="draft_plan",
                domain=selected_domain,
                objective=objective,
                current_state=current_state,
                desired_state=desired_state,
                constraints=constraints,
                steps=draft_steps,
                assumptions=assumptions,
                confidence=checked_interpretation.confidence,
                created_at=now,
                expires_at=now + timedelta(minutes=horizon),
                planner_version=RULE_BASED_PLANNER_VERSION,
            )
        except ValidationError as exc:
            raise PlanningError(
                "invalid_generated_plan",
                "rule-based planner produced a structurally invalid plan",
            ) from exc

        validated_draft = self._validate_plan(
            draft,
            now=now,
            authoritative_constraints=trusted_constraints,
        )
        plan_id = self._deterministic_plan_id(validated_draft)
        final_steps = [
            step.model_copy(update={"step_id": f"{plan_id}_step_{index + 1}"})
            for index, step in enumerate(validated_draft.steps)
        ]
        final_plan = validated_draft.model_copy(
            update={"plan_id": plan_id, "steps": final_steps}
        )
        return self._validate_plan(
            final_plan,
            now=now,
            authoritative_constraints=trusted_constraints,
        )

    def _normalize_domain(self, domain: Domain) -> Domain:
        try:
            return Domain(domain)
        except (TypeError, ValueError) as exc:
            raise PlanningError("unsupported_domain", f"unsupported domain: {domain!r}") from exc

    def _validate_interpretation(self, interpretation: Any) -> ContextInterpretation:
        payload = (
            interpretation.model_dump(mode="python")
            if isinstance(interpretation, ContextInterpretation)
            else interpretation
        )
        try:
            return ContextInterpretation.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise PlanningError(
                "invalid_interpretation",
                "interpretation failed contract validation",
            ) from exc

    def _normalize_objective(self, objective: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", objective.lower()).strip("_")
        canonical = _OBJECTIVE_ALIASES.get(normalized)
        if canonical is None or canonical not in SUPPORTED_OBJECTIVES:
            raise PlanningError(
                "unsupported_objective",
                f"unsupported objective: {objective!r}",
            )
        return canonical

    def _reject_noncanonical_signals(
        self, interpretation: ContextInterpretation
    ) -> None:
        for container_name, container in (
            ("entities", interpretation.entities),
            ("inferred_context", interpretation.inferred_context),
        ):
            found = sorted(_NONCANONICAL_SIGNAL_NAMES.intersection(container))
            if found:
                joined = ", ".join(found)
                raise PlanningError(
                    "noncanonical_signal",
                    f"{container_name} uses noncanonical signal name(s): {joined}",
                )

    def _validate_missing_information(
        self, interpretation: ContextInterpretation
    ) -> None:
        unsupported = []
        for item in interpretation.missing_information:
            normalized = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
            if normalized not in _DEFAULTABLE_MISSING_FIELDS:
                unsupported.append(item)
        if unsupported:
            raise PlanningError(
                "unresolved_missing_information",
                "no safe deterministic default exists for: " + ", ".join(unsupported),
            )

    def _validate_authoritative_constraints(
        self,
        constraints: Sequence[IntentConstraint],
    ) -> List[IntentConstraint]:
        if constraints is None or isinstance(constraints, (str, bytes)):
            raise PlanningError(
                "invalid_authoritative_constraint",
                "authoritative constraints must be a sequence of IntentConstraint",
            )
        checked = []
        for index, constraint in enumerate(constraints):
            if not isinstance(constraint, IntentConstraint):
                raise PlanningError(
                    "invalid_authoritative_constraint",
                    f"authoritative constraint {index} must be an IntentConstraint",
                )
            try:
                copied = IntentConstraint.model_validate(
                    constraint.model_dump(mode="python")
                )
            except ValidationError as exc:
                raise PlanningError(
                    "invalid_authoritative_constraint",
                    f"authoritative constraint {index} is malformed",
                ) from exc
            if not copied.hard:
                raise PlanningError(
                    "invalid_authoritative_constraint",
                    "authoritative constraints must be explicitly hard",
                )
            if copied.source == ConstraintSource.INFERRED:
                raise PlanningError(
                    "invalid_authoritative_constraint",
                    "INFERRED constraints cannot be authoritative",
                )
            checked.append(copied)
        return checked

    def _validate_interpreted_constraints(
        self,
        constraints: Sequence[IntentConstraint],
    ) -> List[IntentConstraint]:
        checked = []
        for constraint in constraints:
            if constraint.source not in (
                ConstraintSource.USER,
                ConstraintSource.INFERRED,
            ):
                raise PlanningError(
                    "untrusted_constraint_authority",
                    "interpretation cannot claim SYSTEM or DOMAIN authority",
                )
            if constraint.hard:
                raise PlanningError(
                    "untrusted_constraint_authority",
                    "interpreted constraints cannot become authoritative hard constraints",
                )
            checked.append(
                IntentConstraint.model_validate(constraint.model_dump(mode="python"))
            )
        return checked

    def _context_value(
        self,
        interpretation: ContextInterpretation,
        names: Sequence[str],
    ) -> Tuple[bool, Any]:
        found = []
        for container_name, container in (
            ("entities", interpretation.entities),
            ("inferred_context", interpretation.inferred_context),
        ):
            for name in names:
                if name in container:
                    found.append((f"{container_name}.{name}", container[name]))

        if not found:
            return False, None

        first_path, first_value = found[0]
        if any(value != first_value for _, value in found[1:]):
            paths = ", ".join(path for path, _ in found)
            raise PlanningError(
                "conflicting_context",
                f"conflicting values supplied across: {paths}",
            )
        return True, first_value

    def _resolve_energy(
        self,
        interpretation: ContextInterpretation,
        assumptions: List[str],
    ) -> float:
        present, value = self._context_value(
            interpretation,
            ("energy", "current_energy"),
        )
        if not present:
            assumptions.append(
                "Current energy was not provided; used deterministic neutral "
                f"energy {DEFAULT_CURRENT_ENERGY:.1f}."
            )
            return DEFAULT_CURRENT_ENERGY
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PlanningError("invalid_context", "energy must be numeric")
        try:
            numeric = float(value)
        except (OverflowError, ValueError) as exc:
            raise PlanningError("invalid_context", "energy must be finite") from exc
        if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise PlanningError("invalid_context", "energy must be between 0 and 1")
        return numeric

    def _resolve_viewer(
        self,
        interpretation: ContextInterpretation,
        assumptions: List[str],
    ) -> str:
        present, value = self._context_value(interpretation, ("viewer",))
        if not present:
            assumptions.append(
                "Viewer was not provided; used deterministic family viewer intent."
            )
            return DEFAULT_VIEWER
        if not isinstance(value, str) or value not in _VIEWERS:
            raise PlanningError(
                "invalid_context",
                "viewer must be one of: adult, family, kids, teen",
            )
        return value

    def _resolve_horizon(
        self,
        interpretation: ContextInterpretation,
        objective: str,
        assumptions: List[str],
    ) -> int:
        present, value = self._context_value(
            interpretation,
            ("horizon_minutes",),
        )
        if not present:
            default = DEFAULT_HORIZON_MINUTES[objective]
            assumptions.append(
                "Plan horizon was not provided; used deterministic "
                f"{objective} horizon of {default} minutes."
            )
            return default
        if isinstance(value, bool) or not isinstance(value, int):
            raise PlanningError(
                "invalid_horizon",
                "horizon_minutes must be an integer",
            )
        minimum = MIN_HORIZON_MINUTES[objective]
        if not minimum <= value <= MAX_HORIZON_MINUTES:
            raise PlanningError(
                "invalid_horizon",
                f"{objective} horizon must be between {minimum} and "
                f"{MAX_HORIZON_MINUTES} minutes",
            )
        return value

    def _build_objective_plan(
        self,
        *,
        objective: str,
        current_energy: float,
        viewer: str,
        horizon_minutes: int,
    ) -> Tuple[Dict[str, Any], List[Tuple[int, Dict[str, Any], str]]]:
        if objective == "wind_down":
            target = min(current_energy, 0.1)
            energies = [
                min(current_energy, 0.55),
                min(current_energy, 0.30),
                target,
            ]
            offsets = [
                0,
                max(1, int(horizon_minutes * 5 / 12)),
                min(
                    horizon_minutes - 1,
                    max(2, int(horizon_minutes * 5 / 6)),
                ),
            ]
            tones = ["familiar", "calm", "soothing"]
            reasons = [
                "Begin with moderately lower stimulation.",
                "Transition toward calm content as the horizon advances.",
                "Reach the low-energy wind-down target before plan expiry.",
            ]
            steps = [
                (
                    offset,
                    {
                        "energy": round(energy, 3),
                        "tone": tone,
                        "runtime_preference": "short",
                        "intent_type": "calm",
                    },
                    reason,
                )
                for offset, energy, tone, reason in zip(
                    offsets,
                    energies,
                    tones,
                    reasons,
                )
            ]
            return (
                {
                    "energy": round(target, 3),
                    "tone": "soothing",
                    "runtime_preference": "short",
                    "intent_type": "calm",
                },
                steps,
            )

        if objective == "focus":
            intent = {
                "energy": 0.4,
                "tone": "focused",
                "runtime_preference": "medium",
                "intent_type": "educational",
            }
            return intent.copy(), [(0, intent, "Establish a steady focus state.")]

        if objective == "family_time":
            intent = {
                "energy": 0.6,
                "viewer": "family",
                "tone": "familiar",
                "runtime_preference": "long",
                "intent_type": "popular",
            }
            return intent.copy(), [
                (0, intent, "Establish a shared family viewing intent.")
            ]

        if objective == "quick_session":
            intent = {
                "energy": round(current_energy, 3),
                "tone": "familiar",
                "runtime_preference": "short",
                "intent_type": "popular",
            }
            return intent.copy(), [
                (0, intent, "Prefer a short session without selecting a candidate.")
            ]

        if objective == "high_energy":
            first_energy = max(current_energy, 0.65)
            target = max(first_energy, 0.9)
            base_intent = {
                "tone": "energetic",
                "runtime_preference": "medium",
                "intent_type": "popular",
            }
            first_intent = dict(base_intent, energy=round(first_energy, 3))
            target_intent = dict(base_intent, energy=round(target, 3))
            return target_intent.copy(), [
                (0, first_intent, "Raise stimulation toward the high-energy goal."),
                (
                    max(1, horizon_minutes // 2),
                    target_intent,
                    "Reach and maintain the high-energy target.",
                ),
            ]

        raise PlanningError(
            "unsupported_objective",
            f"unsupported objective: {objective!r}",
        )

    def _validate_plan(
        self,
        plan: IntentPlan,
        *,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint],
    ) -> IntentPlan:
        try:
            return self._validator.validate(
                plan,
                now=now,
                authoritative_constraints=authoritative_constraints,
            )
        except PlanValidationError as exc:
            raise PlanningError(
                "plan_validation_failed",
                "planner output failed the Phase 1 validation boundary",
            ) from exc

    def _deterministic_plan_id(self, plan: IntentPlan) -> str:
        semantic = plan.model_dump(mode="json")
        semantic.pop("plan_id", None)
        for step in semantic["steps"]:
            step.pop("step_id", None)
        payload = json.dumps(
            semantic,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return "plan_" + sha256(payload.encode("utf-8")).hexdigest()[:20]

    def _deduplicate(self, values: Sequence[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result
