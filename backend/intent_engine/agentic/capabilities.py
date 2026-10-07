"""Declarative V4 domain capabilities used by semantic plan validation.

The current DomainAdapter protocol does not expose signal metadata.  Keeping
this registry isolated avoids importing or executing ranking code while
validating untrusted plans.  The registry is injectable so adapter-owned
metadata can replace it in a later phase.
"""

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, FrozenSet, Mapping, Optional

from intent_engine.schemas import Domain


class ValueKind(str, Enum):
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    STRING_LIST = "string_list"


@dataclass(frozen=True)
class ValueRule:
    """Type and optional bounds for one supported signal or constraint."""

    kind: ValueKind
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    allowed_values: Optional[FrozenSet[str]] = None
    min_items: int = 0

    def __post_init__(self) -> None:
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum cannot be greater than maximum")
        if self.min_items < 0:
            raise ValueError("min_items cannot be negative")
        if self.allowed_values is not None:
            if self.kind != ValueKind.STRING:
                raise ValueError("allowed_values are only valid for string rules")
            if any(not isinstance(item, str) or not item for item in self.allowed_values):
                raise ValueError("allowed_values must contain non-blank strings")

    def error_for(self, value: Any) -> Optional[str]:
        if self.kind == ValueKind.NUMBER:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return "must be a number"
            try:
                numeric = float(value)
            except (OverflowError, ValueError):
                return "must be finite"
            if not math.isfinite(numeric):
                return "must be finite"
            if self.minimum is not None and numeric < self.minimum:
                return f"must be greater than or equal to {self.minimum:g}"
            if self.maximum is not None and numeric > self.maximum:
                return f"must be less than or equal to {self.maximum:g}"
            return None

        if self.kind == ValueKind.STRING:
            if not isinstance(value, str) or not value.strip():
                return "must be a non-blank string"
            if self.allowed_values is not None and value not in self.allowed_values:
                allowed = ", ".join(sorted(self.allowed_values))
                return f"must be one of: {allowed}"
            return None

        if self.kind == ValueKind.BOOLEAN:
            if not isinstance(value, bool):
                return "must be a boolean"
            return None

        if self.kind == ValueKind.STRING_LIST:
            if not isinstance(value, list):
                return "must be a list of strings"
            if len(value) < self.min_items:
                return f"must contain at least {self.min_items} item(s)"
            if any(not isinstance(item, str) or not item.strip() for item in value):
                return "must contain only non-blank strings"
            return None

        return "uses an unsupported capability rule"


@dataclass(frozen=True)
class DomainCapabilities:
    """Signals and constraints understood for a single V4 domain."""

    signals: Mapping[str, ValueRule]
    constraints: Mapping[str, ValueRule]

    def __post_init__(self) -> None:
        for collection_name, rules in (
            ("signals", self.signals),
            ("constraints", self.constraints),
        ):
            for name, rule in rules.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"{collection_name} keys must be non-blank strings")
                if not isinstance(rule, ValueRule):
                    raise TypeError(f"{collection_name} values must be ValueRule objects")
        object.__setattr__(self, "signals", MappingProxyType(dict(self.signals)))
        object.__setattr__(self, "constraints", MappingProxyType(dict(self.constraints)))


UNIT_INTERVAL = ValueRule(ValueKind.NUMBER, minimum=0.0, maximum=1.0)
NONNEGATIVE_NUMBER = ValueRule(ValueKind.NUMBER, minimum=0.0)
FREE_TEXT = ValueRule(ValueKind.STRING)
BOOLEAN = ValueRule(ValueKind.BOOLEAN)
NONEMPTY_STRING_LIST = ValueRule(ValueKind.STRING_LIST, min_items=1)

VIEWER = ValueRule(
    ValueKind.STRING,
    allowed_values=frozenset({"kids", "teen", "family", "adult"}),
)
STREAMING_TIME_BUCKET = ValueRule(
    ValueKind.STRING,
    allowed_values=frozenset(
        {
            "early_morning",
            "morning",
            "afternoon",
            "evening",
            "bedtime",
            "late_night",
        }
    ),
)
RIDE_TIME_BUCKET = ValueRule(
    ValueKind.STRING,
    allowed_values=frozenset(
        {
            "morning_commute",
            "morning",
            "afternoon",
            "evening_commute",
            "evening",
            "late_night",
        }
    ),
)
RUNTIME_PREFERENCE = ValueRule(
    ValueKind.STRING,
    allowed_values=frozenset({"short", "medium", "long"}),
)
MATURITY = ValueRule(
    ValueKind.STRING,
    allowed_values=frozenset({"kids", "teen", "family", "adult"}),
)


def _intent_types(*values: str) -> ValueRule:
    return ValueRule(ValueKind.STRING, allowed_values=frozenset(values))


def _profile_constraints(*, explicit: bool = False) -> Mapping[str, ValueRule]:
    constraints = {
        # The first two names occur in the V4 spec; maturity_gate is the
        # existing adapter-facing name.  Translation remains a later phase.
        "viewer_safety": MATURITY,
        "viewer_maturity": MATURITY,
        "maturity_gate": MATURITY,
    }
    if explicit:
        constraints["block_explicit"] = BOOLEAN
    return constraints


DEFAULT_DOMAIN_CAPABILITIES: Mapping[Domain, DomainCapabilities] = MappingProxyType(
    {
        Domain.STREAMING: DomainCapabilities(
            signals={
                # V4 canonical names.  Phase 3 must explicitly translate
                # energy -> energy_level and viewer -> viewer_profile.
                "energy": UNIT_INTERVAL,
                "viewer": VIEWER,
                "tone": FREE_TEXT,
                "runtime_preference": RUNTIME_PREFERENCE,
                "time_bucket": STREAMING_TIME_BUCKET,
                "intent_type": _intent_types(
                    "popular", "educational", "calm", "discovery", "unknown"
                ),
            },
            constraints=_profile_constraints(),
        ),
        Domain.MUSIC: DomainCapabilities(
            signals={
                "energy": UNIT_INTERVAL,
                "listener_profile": VIEWER,
                "tone": FREE_TEXT,
                "time_bucket": STREAMING_TIME_BUCKET,
                "intent_type": _intent_types(
                    "focus", "calm", "upbeat", "discovery", "unknown"
                ),
            },
            constraints=_profile_constraints(explicit=True),
        ),
        Domain.ECOMMERCE: DomainCapabilities(
            signals={
                "price_sensitivity": UNIT_INTERVAL,
                "quality_priority": UNIT_INTERVAL,
                "shopper_profile": VIEWER,
                "intent_type": _intent_types(
                    "gift", "budget", "premium", "practical", "discovery", "unknown"
                ),
            },
            constraints=_profile_constraints(),
        ),
        Domain.RIDE_MATCHING: DomainCapabilities(
            signals={
                "urgency": UNIT_INTERVAL,
                "surge_sensitivity": UNIT_INTERVAL,
                "comfort_preference": UNIT_INTERVAL,
                "time_bucket": RIDE_TIME_BUCKET,
                "intent_type": _intent_types(
                    "budget", "comfort", "premium", "urgent", "habitual"
                ),
            },
            constraints={"surge_cap": NONNEGATIVE_NUMBER},
        ),
        Domain.FOOD_DELIVERY: DomainCapabilities(
            signals={
                "hunger_urgency": UNIT_INTERVAL,
                "price_sensitivity": UNIT_INTERVAL,
                "health_priority": UNIT_INTERVAL,
                "comfort_preference": UNIT_INTERVAL,
                "time_bucket": STREAMING_TIME_BUCKET,
                "intent_type": _intent_types(
                    "comfort", "healthy", "fast", "discovery", "habitual", "unknown"
                ),
            },
            constraints={"allergens": NONEMPTY_STRING_LIST},
        ),
    }
)
