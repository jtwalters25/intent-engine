"""Fail-closed semantic validation for V4 IntentPlan objects."""

from dataclasses import dataclass
from datetime import datetime
import json
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple

from pydantic import ValidationError

from intent_engine.agentic.capabilities import (
    DEFAULT_DOMAIN_CAPABILITIES,
    DomainCapabilities,
)
from intent_engine.agentic.schemas import IntentConstraint, IntentPlan
from intent_engine.schemas import Domain


FORBIDDEN_SELECTION_SIGNALS = frozenset(
    {
        "candidate_id",
        "final_score",
        "item_id",
        "rank",
        "ranked_items",
        "recommended_item",
        "recommended_title",
        "score",
        "selected_candidate",
        "selected_candidate_id",
    }
)

# The V4 spec uses two names for this concept, while current adapters use a
# third.  Treat them as one semantic constraint during conflict detection.
CONSTRAINT_TYPE_ALIASES = MappingProxyType(
    {
        "viewer_safety": "viewer_maturity",
        "viewer_maturity": "viewer_maturity",
        "maturity_gate": "viewer_maturity",
    }
)


@dataclass(frozen=True)
class ValidationIssue:
    """One machine-readable plan validation failure."""

    code: str
    path: str
    message: str


class PlanValidationError(ValueError):
    """Raised when an IntentPlan cannot cross the deterministic boundary."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues: Tuple[ValidationIssue, ...] = tuple(issues)
        summary = "; ".join(
            f"{issue.path}: {issue.message}" for issue in self.issues
        )
        super().__init__(summary or "intent plan validation failed")


def _timezone_aware(value: datetime) -> bool:
    return value.utcoffset() is not None


def _canonical_value(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _semantic_constraint_type(constraint_type: str) -> str:
    return CONSTRAINT_TYPE_ALIASES.get(constraint_type, constraint_type)


def canonical_plan_json(plan: IntentPlan) -> str:
    """Return stable JSON for an already validated plan."""
    if not isinstance(plan, IntentPlan):
        raise TypeError("plan must be an IntentPlan")
    # Revalidate nested mutable structures so post-construction mutation cannot
    # turn canonical serialization into a lossy or non-JSON representation.
    try:
        payload = plan.model_dump(mode="python")
        checked = IntentPlan.model_validate(payload)
    except RecursionError as exc:
        raise ValueError("plan contains recursively nested data") from exc
    return json.dumps(
        checked.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


class PlanValidator:
    """Validate plan semantics without invoking adapters or ranking code."""

    def __init__(
        self,
        capabilities: Optional[Mapping[Domain, DomainCapabilities]] = None,
    ) -> None:
        selected = (
            DEFAULT_DOMAIN_CAPABILITIES if capabilities is None else capabilities
        )
        normalized = {Domain(domain): capability for domain, capability in selected.items()}
        self._capabilities: Mapping[Domain, DomainCapabilities] = MappingProxyType(
            normalized
        )

    @property
    def capabilities(self) -> Mapping[Domain, DomainCapabilities]:
        return self._capabilities

    def validate_payload(
        self,
        payload: Any,
        *,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> IntentPlan:
        """Parse untrusted data and apply structural and semantic validation."""
        plan = self._parse_plan(payload)
        return self.validate(
            plan,
            now=now,
            authoritative_constraints=authoritative_constraints,
        )

    def validate(
        self,
        plan: IntentPlan,
        *,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> IntentPlan:
        """Return a revalidated copy or reject the plan without mutating it."""
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")

        # Re-parse a dump so list/dict mutations after model construction cannot
        # bypass intrinsic Pydantic invariants.
        if isinstance(plan, IntentPlan):
            try:
                payload = plan.model_dump(mode="python")
            except RecursionError as exc:
                raise PlanValidationError(
                    [
                        ValidationIssue(
                            code="schema_validation",
                            path="$",
                            message="plan contains recursively nested data",
                        )
                    ]
                ) from exc
        else:
            payload = plan
        checked = self._parse_plan(payload)
        issues = []

        if checked.expires_at is not None:
            if _timezone_aware(checked.expires_at) != _timezone_aware(now):
                issues.append(
                    ValidationIssue(
                        code="timezone_mismatch",
                        path="expires_at",
                        message="expires_at and now must use matching timezone awareness",
                    )
                )
            elif checked.expires_at <= now:
                issues.append(
                    ValidationIssue(
                        code="expired_plan",
                        path="expires_at",
                        message="plan has expired",
                    )
                )

        domain_capabilities = self._capabilities.get(checked.domain)
        if domain_capabilities is None:
            issues.append(
                ValidationIssue(
                    code="missing_domain_capabilities",
                    path="domain",
                    message=f"no validation capabilities registered for {checked.domain.value}",
                )
            )
        else:
            self._validate_signals(checked, domain_capabilities, issues)
            self._validate_constraints(checked, domain_capabilities, issues)
            self._validate_authoritative_constraints(
                checked,
                domain_capabilities,
                authoritative_constraints,
                issues,
            )

        if issues:
            raise PlanValidationError(issues)
        return checked

    def canonicalize(
        self,
        plan: IntentPlan,
        *,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> str:
        """Validate and return a deterministic representation of the plan."""
        checked = self.validate(
            plan,
            now=now,
            authoritative_constraints=authoritative_constraints,
        )
        return canonical_plan_json(checked)

    def _parse_plan(self, payload: Any) -> IntentPlan:
        try:
            return IntentPlan.model_validate(payload)
        except ValidationError as exc:
            issues = []
            for error in exc.errors(include_url=False, include_context=False):
                location = ".".join(str(part) for part in error["loc"]) or "$"
                issues.append(
                    ValidationIssue(
                        code="schema_validation",
                        path=location,
                        message=error["msg"],
                    )
                )
            raise PlanValidationError(issues) from exc
        except RecursionError as exc:
            raise PlanValidationError(
                [
                    ValidationIssue(
                        code="schema_validation",
                        path="$",
                        message="plan exceeds safe nesting limits",
                    )
                ]
            ) from exc

    def _validate_signals(
        self,
        plan: IntentPlan,
        capabilities: DomainCapabilities,
        issues: list,
    ) -> None:
        locations = [
            ("current_state", plan.current_state, False),
            ("desired_state", plan.desired_state, False),
        ]
        locations.extend(
            (f"steps.{index}.intent", step.intent, True)
            for index, step in enumerate(plan.steps)
        )

        for base_path, signals, selection_sensitive in locations:
            for name, value in signals.items():
                path = f"{base_path}.{name}"
                if selection_sensitive and name.lower() in FORBIDDEN_SELECTION_SIGNALS:
                    issues.append(
                        ValidationIssue(
                            code="candidate_selection_forbidden",
                            path=path,
                            message="intent steps cannot select or score candidates",
                        )
                    )
                    continue

                rule = capabilities.signals.get(name)
                if rule is None:
                    issues.append(
                        ValidationIssue(
                            code="unknown_signal",
                            path=path,
                            message=f"signal {name!r} is not supported for {plan.domain.value}",
                        )
                    )
                    continue

                value_error = rule.error_for(value)
                if value_error is not None:
                    issues.append(
                        ValidationIssue(
                            code="invalid_signal_value",
                            path=path,
                            message=f"signal {name!r} {value_error}",
                        )
                    )

    def _validate_constraints(
        self,
        plan: IntentPlan,
        capabilities: DomainCapabilities,
        issues: list,
    ) -> None:
        seen = set()
        semantic_values = {}
        for index, constraint in enumerate(plan.constraints):
            path = f"constraints.{index}"
            identity = (constraint.type, constraint.source)
            if identity in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate_constraint",
                        path=path,
                        message=(
                            "constraints with the same type and source are ambiguous"
                        ),
                    )
                )
            else:
                seen.add(identity)

            rule = capabilities.constraints.get(constraint.type)
            if rule is None:
                issues.append(
                    ValidationIssue(
                        code="unknown_constraint",
                        path=f"{path}.type",
                        message=(
                            f"constraint {constraint.type!r} is not supported for "
                            f"{plan.domain.value}"
                        ),
                    )
                )
                continue

            value_error = rule.error_for(constraint.value)
            if value_error is not None:
                issues.append(
                    ValidationIssue(
                        code="malformed_constraint",
                        path=f"{path}.value",
                        message=f"constraint {constraint.type!r} {value_error}",
                    )
                )
                continue

            semantic_type = _semantic_constraint_type(constraint.type)
            semantic_value = (_canonical_value(constraint.value), constraint.hard)
            prior_value = semantic_values.get(semantic_type)
            if prior_value is not None and prior_value != semantic_value:
                issues.append(
                    ValidationIssue(
                        code="conflicting_constraint",
                        path=path,
                        message=(
                            f"constraint {constraint.type!r} conflicts with another "
                            f"{semantic_type!r} constraint"
                        ),
                    )
                )
            elif prior_value is None:
                semantic_values[semantic_type] = semantic_value

    def _validate_authoritative_constraints(
        self,
        plan: IntentPlan,
        capabilities: DomainCapabilities,
        authoritative_constraints: Sequence[IntentConstraint],
        issues: list,
    ) -> None:
        seen = set()
        semantic_values = {}
        for index, authoritative in enumerate(authoritative_constraints):
            if not isinstance(authoritative, IntentConstraint):
                issues.append(
                    ValidationIssue(
                        code="invalid_authoritative_constraint",
                        path=f"authoritative_constraints.{index}",
                        message="must be an IntentConstraint",
                    )
                )
                continue

            try:
                checked_authoritative = IntentConstraint.model_validate(
                    authoritative.model_dump(mode="python")
                )
            except ValidationError as exc:
                issues.append(
                    ValidationIssue(
                        code="invalid_authoritative_constraint",
                        path=f"authoritative_constraints.{index}",
                        message=str(exc.errors(include_url=False)[0]["msg"]),
                    )
                )
                continue

            identity = (
                checked_authoritative.type,
                checked_authoritative.source,
            )
            if identity in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate_authoritative_constraint",
                        path=f"authoritative_constraints.{index}",
                        message="authoritative constraints must be unique by type and source",
                    )
                )
                continue
            seen.add(identity)

            if not checked_authoritative.hard:
                continue

            rule = capabilities.constraints.get(checked_authoritative.type)
            if rule is None:
                issues.append(
                    ValidationIssue(
                        code="unknown_authoritative_constraint",
                        path=f"authoritative_constraints.{index}.type",
                        message=(
                            f"constraint {checked_authoritative.type!r} is not supported for "
                            f"{plan.domain.value}"
                        ),
                    )
                )
                continue

            value_error = rule.error_for(checked_authoritative.value)
            if value_error is not None:
                issues.append(
                    ValidationIssue(
                        code="invalid_authoritative_constraint",
                        path=f"authoritative_constraints.{index}.value",
                        message=(
                            f"constraint {checked_authoritative.type!r} {value_error}"
                        ),
                    )
                )
                continue

            semantic_type = _semantic_constraint_type(checked_authoritative.type)
            semantic_value = (
                _canonical_value(checked_authoritative.value),
                checked_authoritative.hard,
            )
            prior_value = semantic_values.get(semantic_type)
            if prior_value is not None and prior_value != semantic_value:
                issues.append(
                    ValidationIssue(
                        code="conflicting_authoritative_constraint",
                        path=f"authoritative_constraints.{index}",
                        message=(
                            "authoritative constraints for the same policy must "
                            "not conflict"
                        ),
                    )
                )
                continue
            if prior_value is None:
                semantic_values[semantic_type] = semantic_value

            preserved = any(
                candidate.type == checked_authoritative.type
                and candidate.source == checked_authoritative.source
                and candidate.hard
                and _canonical_value(candidate.value)
                == _canonical_value(checked_authoritative.value)
                for candidate in plan.constraints
            )
            if not preserved:
                issues.append(
                    ValidationIssue(
                        code="hard_constraint_weakened",
                        path="constraints",
                        message=(
                            f"authoritative hard constraint {checked_authoritative.type!r} "
                            "must be preserved exactly"
                        ),
                    )
                )


# A descriptive alias for callers that prefer the fully qualified name.
IntentPlanValidator = PlanValidator
