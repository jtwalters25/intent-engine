"""Deterministic Phase 3B preparation of a validated plan for execution.

The orchestrator owns trusted-time step selection and precedence between plan
state, the active step, and caller-authenticated profile context.  It prepares
adapter input through :class:`PlanIntentNormalizer`, but deliberately accepts
no candidates and performs no ranking or adapter execution.
"""

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from pydantic import ValidationError

from intent_engine.agentic.normalizer import (
    NormalizedAdapterInput,
    PlanIntentNormalizer,
)
from intent_engine.agentic.schemas import (
    ConstraintSource,
    IntentConstraint,
    IntentPlan,
    IntentStep,
    datetime_instant,
    validate_json_value,
)
from intent_engine.agentic.validator import CONSTRAINT_TYPE_ALIASES, PlanValidator
from intent_engine.schemas import Domain


PROTECTED_PROFILE_SIGNALS = frozenset({"viewer"})
_PRIVILEGED_CONSTRAINT_SOURCES = frozenset(
    {ConstraintSource.SYSTEM, ConstraintSource.DOMAIN}
)


class OrchestrationError(ValueError):
    """Fail-closed orchestration error with stable code and path metadata."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {message}")


def _timezone_aware(value: datetime) -> bool:
    return value.utcoffset() is not None


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {
                key: _freeze_json_value(value[key])
                for key in sorted(value)
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _frozen_mapping_copy(values: Mapping[str, Any]) -> Mapping[str, Any]:
    copied = dict(values)
    validate_json_value(copied, path="prepared canonical intent")
    return _freeze_json_value(copied)


@dataclass(frozen=True)
class ActivePlanStep:
    """Immutable snapshot of the selected ``IntentStep`` contract."""

    step_id: str
    offset_minutes: int
    intent: Mapping[str, Any]
    transition_reason: str
    completion_condition: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        intent = _frozen_mapping_copy(self.intent)
        completion = (
            None
            if self.completion_condition is None
            else _frozen_mapping_copy(self.completion_condition)
        )
        object.__setattr__(self, "intent", intent)
        object.__setattr__(self, "completion_condition", completion)

    @classmethod
    def from_intent_step(cls, step: IntentStep) -> "ActivePlanStep":
        if not isinstance(step, IntentStep):
            raise TypeError("step must be an IntentStep")
        checked = IntentStep.model_validate(step.model_dump(mode="python"))
        return cls(
            step_id=checked.step_id,
            offset_minutes=checked.offset_minutes,
            intent=checked.intent,
            transition_reason=checked.transition_reason,
            completion_condition=checked.completion_condition,
        )


@dataclass(frozen=True)
class PreparedPlanExecution:
    """Immutable output ready for the future Phase 3C execution seam.

    This value is an in-process preparation result, not proof that external
    data is authenticated.  Phase 3C must obtain it from ``IntentOrchestrator``
    rather than deserialize it from a request.
    """

    plan_id: str
    domain: Domain
    evaluated_at: datetime
    active_step: ActivePlanStep
    canonical_intent: Mapping[str, Any]
    normalized_input: NormalizedAdapterInput

    def __post_init__(self) -> None:
        if not isinstance(self.active_step, ActivePlanStep):
            raise TypeError("active_step must be an ActivePlanStep")
        if not isinstance(self.normalized_input, NormalizedAdapterInput):
            raise TypeError("normalized_input must be a NormalizedAdapterInput")

        object.__setattr__(
            self,
            "canonical_intent",
            _frozen_mapping_copy(self.canonical_intent),
        )


class IntentOrchestrator:
    """Prepare one active plan step without ranking or mutating the plan."""

    def __init__(
        self,
        validator: Optional[PlanValidator] = None,
        normalizer: Optional[PlanIntentNormalizer] = None,
    ) -> None:
        self._validator = PlanValidator() if validator is None else validator
        self._normalizer = (
            PlanIntentNormalizer() if normalizer is None else normalizer
        )

    def prepare_execution(
        self,
        plan: IntentPlan,
        *,
        now: datetime,
        active_profile_context: Mapping[str, Any],
        authoritative_constraints: Sequence[IntentConstraint],
    ) -> PreparedPlanExecution:
        """Revalidate and resolve the plan state active at trusted ``now``.

        ``active_profile_context`` and ``authoritative_constraints`` are
        explicit trusted channels owned by the caller.  Labels embedded in a
        plan never authenticate either channel.
        """
        if not isinstance(now, datetime):
            raise OrchestrationError(
                "invalid_now",
                "now",
                "trusted now must be a datetime",
            )

        trusted_constraints = self._snapshot_authoritative_constraints(
            authoritative_constraints
        )

        # Always use the validator's reparsed copy after this point. This
        # catches post-construction mutation and avoids reading a stale caller
        # object after the execution-time validation boundary.
        checked_plan = self._validator.validate(
            plan,
            now=now,
            authoritative_constraints=trusted_constraints,
        )
        self._validate_plan_constraint_authority(
            checked_plan,
            trusted_constraints,
        )

        if _timezone_aware(checked_plan.created_at) != _timezone_aware(now):
            raise OrchestrationError(
                "timezone_mismatch",
                "now",
                "now and plan.created_at must use matching timezone awareness",
            )
        if datetime_instant(now) < datetime_instant(checked_plan.created_at):
            raise OrchestrationError(
                "plan_not_started",
                "now",
                "plan cannot execute before created_at",
            )

        active_step = self._select_active_step(checked_plan, now)
        trusted_profile = self._validate_active_profile_context(
            active_profile_context,
            checked_plan.domain,
        )
        self._validate_profile_constraint_coherence(
            trusted_profile,
            trusted_constraints,
        )

        canonical_intent = dict(checked_plan.current_state)
        canonical_intent.update(active_step.intent)
        # Protected values from the authenticated profile channel always win
        # over interpreted plan state and step intent.
        canonical_intent.update(trusted_profile)

        normalized = self._normalizer.normalize(
            domain=checked_plan.domain,
            canonical_intent=canonical_intent,
            authoritative_constraints=trusted_constraints,
        )
        return PreparedPlanExecution(
            plan_id=checked_plan.plan_id,
            domain=checked_plan.domain,
            evaluated_at=now,
            active_step=ActivePlanStep.from_intent_step(active_step),
            canonical_intent=canonical_intent,
            normalized_input=normalized,
        )

    def _select_active_step(
        self,
        plan: IntentPlan,
        now: datetime,
    ) -> IntentStep:
        elapsed_seconds = (
            datetime_instant(now) - datetime_instant(plan.created_at)
        ).total_seconds()
        active = None
        for step in plan.steps:
            if step.offset_minutes * 60 > elapsed_seconds:
                break
            active = step

        if active is None:
            raise OrchestrationError(
                "no_active_step",
                "steps",
                "no plan step is active at the supplied time",
            )
        return active

    def _snapshot_authoritative_constraints(
        self,
        constraints: Sequence[IntentConstraint],
    ) -> Sequence[IntentConstraint]:
        if not isinstance(constraints, SequenceABC) or isinstance(
            constraints,
            (str, bytes),
        ):
            raise OrchestrationError(
                "invalid_authoritative_constraints",
                "authoritative_constraints",
                "must be a sequence of IntentConstraint",
            )

        try:
            supplied = tuple(constraints)
        except Exception as exc:
            raise OrchestrationError(
                "invalid_authoritative_constraints",
                "authoritative_constraints",
                "could not read the constraint sequence safely",
            ) from exc

        checked = []
        for index, constraint in enumerate(supplied):
            path = f"authoritative_constraints.{index}"
            if not isinstance(constraint, IntentConstraint):
                raise OrchestrationError(
                    "invalid_authoritative_constraint",
                    path,
                    "must be an IntentConstraint",
                )
            try:
                checked.append(
                    IntentConstraint.model_validate(
                        constraint.model_dump(mode="python")
                    )
                )
            except (ValidationError, RecursionError) as exc:
                raise OrchestrationError(
                    "invalid_authoritative_constraint",
                    path,
                    "constraint failed contract validation",
                ) from exc
        return tuple(checked)

    def _validate_plan_constraint_authority(
        self,
        plan: IntentPlan,
        authoritative_constraints: Sequence[IntentConstraint],
    ) -> None:
        for index, constraint in enumerate(plan.constraints):
            path = f"constraints.{index}"
            if constraint.hard:
                if constraint.source == ConstraintSource.INFERRED or not any(
                    constraint == authoritative
                    for authoritative in authoritative_constraints
                ):
                    raise OrchestrationError(
                        "untrusted_plan_constraint_authority",
                        path,
                        "hard plan constraints must be corroborated by the "
                        "separate authoritative channel",
                    )
            elif constraint.source in _PRIVILEGED_CONSTRAINT_SOURCES:
                raise OrchestrationError(
                    "untrusted_plan_constraint_authority",
                    path,
                    "soft plan constraints cannot claim SYSTEM or DOMAIN source",
                )

    def _validate_profile_constraint_coherence(
        self,
        profile: Mapping[str, Any],
        authoritative_constraints: Sequence[IntentConstraint],
    ) -> None:
        if profile.get("viewer") != "kids":
            return

        has_kids_gate = any(
            constraint.hard
            and constraint.source != ConstraintSource.INFERRED
            and CONSTRAINT_TYPE_ALIASES.get(constraint.type, constraint.type)
            == "viewer_maturity"
            and constraint.value == "kids"
            for constraint in authoritative_constraints
        )
        if not has_kids_gate:
            raise OrchestrationError(
                "missing_profile_safety_constraint",
                "authoritative_constraints",
                "a trusted kids profile requires an authoritative kids maturity gate",
            )

    def _validate_active_profile_context(
        self,
        context: Mapping[str, Any],
        domain: Domain,
    ) -> Mapping[str, Any]:
        if not isinstance(context, MappingABC):
            raise OrchestrationError(
                "invalid_active_profile_context",
                "active_profile_context",
                "must be a mapping",
            )

        checked = dict(context)
        if any(not isinstance(name, str) for name in checked):
            raise OrchestrationError(
                "invalid_active_profile_context",
                "active_profile_context",
                "profile signal names must be strings",
            )

        unknown = sorted(set(checked) - PROTECTED_PROFILE_SIGNALS)
        if unknown:
            raise OrchestrationError(
                "unknown_active_profile_signal",
                "active_profile_context",
                "unsupported trusted profile signal(s): " + ", ".join(unknown),
            )

        try:
            validate_json_value(checked, path="active_profile_context")
        except (ValueError, RecursionError) as exc:
            raise OrchestrationError(
                "invalid_active_profile_context",
                "active_profile_context",
                "must contain bounded JSON-compatible values",
            ) from exc

        capabilities = self._validator.capabilities.get(domain)
        if capabilities is None:
            raise OrchestrationError(
                "unsupported_domain",
                "domain",
                f"no profile capabilities registered for {domain.value}",
            )

        for name, value in checked.items():
            rule = capabilities.signals.get(name)
            if rule is None:
                raise OrchestrationError(
                    "unsupported_profile_signal",
                    f"active_profile_context.{name}",
                    f"profile signal {name!r} is not supported for {domain.value}",
                )
            value_error = rule.error_for(value)
            if value_error is not None:
                raise OrchestrationError(
                    "invalid_active_profile_value",
                    f"active_profile_context.{name}",
                    f"profile signal {name!r} {value_error}",
                )

        return MappingProxyType(checked)
