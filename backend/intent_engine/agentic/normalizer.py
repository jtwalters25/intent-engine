"""Pure vocabulary normalization for the V4 streaming pilot.

This module translates already validated canonical intent signals into the
vocabulary consumed by a domain adapter's scoring methods.  It does not choose
an active step, read a clock, inspect candidates, call an adapter, or rank.

Authoritative constraints use a separate input channel.  Plan/interpreter
constraints are deliberately not accepted by this boundary, so a source label
inside probabilistic output cannot create execution authority.
"""

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Dict, Mapping, Sequence

from pydantic import ValidationError

from intent_engine.agentic.capabilities import DEFAULT_DOMAIN_CAPABILITIES
from intent_engine.agentic.schemas import (
    ConstraintSource,
    IntentConstraint,
    validate_json_value,
)
from intent_engine.agentic.validator import (
    CONSTRAINT_TYPE_ALIASES,
    FORBIDDEN_SELECTION_SIGNALS,
)
from intent_engine.schemas import Domain


SUPPORTED_NORMALIZATION_DOMAINS = frozenset({Domain.STREAMING})

_STREAMING_APPLIED_SIGNALS = MappingProxyType(
    {
        "energy": "energy_level",
        "intent_type": "intent_type",
        "time_bucket": "time_bucket",
        "viewer": "viewer_profile",
    }
)
_STREAMING_OBSERVATIONAL_SIGNALS = frozenset(
    {"runtime_preference", "tone"}
)
_PROPHECY_ENERGY_ALIASES = (
    "energy",
    "energy_level",
    "energyLevel",
)


class NormalizationError(ValueError):
    """Fail-closed normalization error with stable code and path metadata."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {message}")


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


def _frozen_copy(values: Mapping[str, Any]) -> Mapping[str, Any]:
    copied = dict(values)
    validate_json_value(copied, path="normalized output")
    return _freeze_json_value(copied)


@dataclass(frozen=True)
class NormalizedAdapterInput:
    """Immutable, deterministic output for a future adapter execution seam.

    ``resolved_intent`` is meant for adapter scoring methods such as
    ``compute_multipliers``.  It is not raw input for ``resolve_intent``.
    """

    domain: Domain
    resolved_intent: Mapping[str, Any]
    hard_constraints: Mapping[str, Any]
    observational_signals: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolved_intent",
            _frozen_copy(self.resolved_intent),
        )
        object.__setattr__(
            self,
            "hard_constraints",
            _frozen_copy(self.hard_constraints),
        )
        object.__setattr__(
            self,
            "observational_signals",
            _frozen_copy(self.observational_signals),
        )


@dataclass(frozen=True)
class NormalizedProphecyContext:
    """Canonical soft context plus explicitly non-applied Prophecy metadata."""

    domain: Domain
    canonical_context: Mapping[str, Any]
    observational_signals: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_context",
            _frozen_copy(self.canonical_context),
        )
        object.__setattr__(
            self,
            "observational_signals",
            _frozen_copy(self.observational_signals),
        )


def _normalize_domain(domain: Domain, *, path: str) -> Domain:
    try:
        selected = Domain(domain)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(
            "unsupported_domain",
            path,
            f"unsupported domain: {domain!r}",
        ) from exc

    if selected not in SUPPORTED_NORMALIZATION_DOMAINS:
        raise NormalizationError(
            "unsupported_domain",
            path,
            "Phase 3A normalization supports the streaming domain only",
        )
    return selected


class PlanIntentNormalizer:
    """Translate canonical plan intent into streaming adapter vocabulary."""

    def normalize(
        self,
        *,
        domain: Domain,
        canonical_intent: Mapping[str, Any],
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> NormalizedAdapterInput:
        """Normalize signals without selecting steps or executing ranking.

        ``canonical_intent`` must be the context resolved by the caller.  Phase
        3B will define how validated plan state and the active step are merged.
        """
        selected_domain = _normalize_domain(domain, path="domain")
        checked_intent = self._validate_intent_mapping(canonical_intent)
        resolved_intent: Dict[str, Any] = {}
        observational: Dict[str, Any] = {}

        capabilities = DEFAULT_DOMAIN_CAPABILITIES[selected_domain]
        for name in sorted(checked_intent):
            value = checked_intent[name]
            path = f"canonical_intent.{name}"

            if name.lower() in FORBIDDEN_SELECTION_SIGNALS:
                raise NormalizationError(
                    "candidate_selection_forbidden",
                    path,
                    "intent normalization cannot select or score candidates",
                )

            rule = capabilities.signals.get(name)
            if rule is None:
                raise NormalizationError(
                    "unknown_signal",
                    path,
                    f"signal {name!r} is not supported for streaming",
                )

            value_error = rule.error_for(value)
            if value_error is not None:
                raise NormalizationError(
                    "invalid_signal_value",
                    path,
                    f"signal {name!r} {value_error}",
                )

            adapter_name = _STREAMING_APPLIED_SIGNALS.get(name)
            if adapter_name is not None:
                resolved_intent[adapter_name] = (
                    float(value) if name == "energy" else value
                )
            elif name in _STREAMING_OBSERVATIONAL_SIGNALS:
                observational[name] = value
            else:
                raise NormalizationError(
                    "unmapped_signal",
                    path,
                    f"no reviewed streaming mapping exists for {name!r}",
                )

        hard_constraints = self._normalize_authoritative_constraints(
            selected_domain,
            authoritative_constraints,
        )
        return NormalizedAdapterInput(
            domain=selected_domain,
            resolved_intent=resolved_intent,
            hard_constraints=hard_constraints,
            observational_signals=observational,
        )

    def _validate_intent_mapping(
        self,
        canonical_intent: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(canonical_intent, MappingABC):
            raise NormalizationError(
                "invalid_canonical_intent",
                "canonical_intent",
                "must be a mapping",
            )

        checked = dict(canonical_intent)
        if any(not isinstance(name, str) for name in checked):
            raise NormalizationError(
                "invalid_canonical_intent",
                "canonical_intent",
                "signal names must be strings",
            )
        return checked

    def _normalize_authoritative_constraints(
        self,
        domain: Domain,
        constraints: Sequence[IntentConstraint],
    ) -> Dict[str, Any]:
        if not isinstance(constraints, SequenceABC) or isinstance(
            constraints,
            (str, bytes),
        ):
            raise NormalizationError(
                "invalid_authoritative_constraint",
                "authoritative_constraints",
                "must be a sequence of IntentConstraint",
            )

        capabilities = DEFAULT_DOMAIN_CAPABILITIES[domain]
        normalized: Dict[str, Any] = {}
        identities = set()

        for index, constraint in enumerate(constraints):
            path = f"authoritative_constraints.{index}"
            if not isinstance(constraint, IntentConstraint):
                raise NormalizationError(
                    "invalid_authoritative_constraint",
                    path,
                    "must be an IntentConstraint",
                )

            try:
                checked = IntentConstraint.model_validate(
                    constraint.model_dump(mode="python")
                )
            except (ValidationError, RecursionError) as exc:
                raise NormalizationError(
                    "invalid_authoritative_constraint",
                    path,
                    "constraint failed contract validation",
                ) from exc

            identity = (checked.type, checked.source)
            if identity in identities:
                raise NormalizationError(
                    "duplicate_authoritative_constraint",
                    path,
                    "constraint type and source must be unique",
                )
            identities.add(identity)

            if not checked.hard:
                raise NormalizationError(
                    "invalid_authoritative_constraint",
                    f"{path}.hard",
                    "authoritative constraints must be explicitly hard",
                )
            if checked.source == ConstraintSource.INFERRED:
                raise NormalizationError(
                    "invalid_authoritative_constraint",
                    f"{path}.source",
                    "INFERRED constraints cannot be authoritative",
                )

            rule = capabilities.constraints.get(checked.type)
            if rule is None:
                raise NormalizationError(
                    "unknown_authoritative_constraint",
                    f"{path}.type",
                    f"constraint {checked.type!r} is not supported for streaming",
                )
            value_error = rule.error_for(checked.value)
            if value_error is not None:
                raise NormalizationError(
                    "invalid_authoritative_constraint",
                    f"{path}.value",
                    f"constraint {checked.type!r} {value_error}",
                )

            canonical_type = CONSTRAINT_TYPE_ALIASES.get(
                checked.type,
                checked.type,
            )
            if canonical_type != "viewer_maturity":
                raise NormalizationError(
                    "unmapped_authoritative_constraint",
                    f"{path}.type",
                    f"no reviewed streaming mapping exists for {checked.type!r}",
                )

            adapter_type = "maturity_gate"
            prior = normalized.get(adapter_type)
            if prior is not None and prior != checked.value:
                raise NormalizationError(
                    "conflicting_authoritative_constraint",
                    path,
                    "maturity constraint aliases must not conflict",
                )

            normalized[adapter_type] = checked.value

        # The current streaming adapter only implements the kids gate.
        # Check this after collecting constraints so alias conflicts fail with
        # the same code regardless of caller-supplied ordering.
        maturity_value = normalized.get("maturity_gate")
        if maturity_value is not None and maturity_value != "kids":
            raise NormalizationError(
                "unsupported_constraint_value",
                "authoritative_constraints",
                "the streaming adapter currently enforces only a kids gate",
            )

        return normalized


class ProphecyContextNormalizer:
    """Normalize current Prophecy energy spellings into canonical V4 context."""

    def normalize(
        self,
        context: Mapping[str, Any],
        *,
        domain: Domain = Domain.STREAMING,
    ) -> NormalizedProphecyContext:
        selected_domain = _normalize_domain(domain, path="domain")
        checked_context = self._validate_context_mapping(context)
        present_aliases = [
            name for name in _PROPHECY_ENERGY_ALIASES if name in checked_context
        ]
        if len(present_aliases) > 1:
            raise NormalizationError(
                "ambiguous_energy_scale",
                "context",
                "multiple energy spellings were supplied: "
                + ", ".join(present_aliases),
            )

        canonical: Dict[str, Any] = {}
        if present_aliases:
            name = present_aliases[0]
            value = checked_context[name]
            canonical["energy"] = self._normalize_energy(name, value)

        observational = {
            name: value
            for name, value in checked_context.items()
            if name not in present_aliases
        }
        try:
            validate_json_value(observational, path="prophecy observations")
        except (ValueError, RecursionError) as exc:
            raise NormalizationError(
                "invalid_prophecy_context",
                "context",
                "observations must contain bounded JSON-compatible values",
            ) from exc
        return NormalizedProphecyContext(
            domain=selected_domain,
            canonical_context=canonical,
            observational_signals=observational,
        )

    def _validate_context_mapping(
        self,
        context: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(context, MappingABC):
            raise NormalizationError(
                "invalid_prophecy_context",
                "context",
                "must be a mapping",
            )
        checked = dict(context)
        if any(not isinstance(name, str) for name in checked):
            raise NormalizationError(
                "invalid_prophecy_context",
                "context",
                "signal names must be strings",
            )
        return checked

    def _normalize_energy(self, name: str, value: Any) -> float:
        path = f"context.{name}"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NormalizationError(
                "invalid_prophecy_energy",
                path,
                "energy must be numeric and non-boolean",
            )
        try:
            numeric = float(value)
        except (OverflowError, ValueError) as exc:
            raise NormalizationError(
                "invalid_prophecy_energy",
                path,
                "energy must be finite",
            ) from exc
        if not math.isfinite(numeric):
            raise NormalizationError(
                "invalid_prophecy_energy",
                path,
                "energy must be finite",
            )

        maximum = 100.0 if name == "energyLevel" else 1.0
        if not 0.0 <= numeric <= maximum:
            raise NormalizationError(
                "invalid_prophecy_energy",
                path,
                f"energy must be between 0 and {maximum:g}",
            )
        return numeric / 100.0 if name == "energyLevel" else numeric
