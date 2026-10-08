"""Typed contracts for the V4 agentic intent boundary.

These models describe goals and intent plans only.  They intentionally contain
no candidate-selection or scoring behavior.  Inputs at this boundary may come
from probabilistic components, so unknown fields are rejected instead of being
silently ignored.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from intent_engine.schemas import Domain


MAX_PLAN_STEPS = 5
MAX_JSON_NESTING = 64
MAX_JSON_ITEMS = 10_000


def _validate_confidence(value: Any) -> float:
    """Accept real numeric confidence values while rejecting coercion/booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number between 0 and 1")
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("confidence must be finite") from exc
    if not math.isfinite(numeric):
        raise ValueError("confidence must be finite")
    return numeric


def _is_timezone_aware(value: datetime) -> bool:
    return value.utcoffset() is not None


def datetime_instant(value: datetime) -> datetime:
    """Normalize aware datetimes to UTC so comparisons use elapsed time.

    Python intentionally compares two aware datetimes sharing the same tzinfo
    by wall-clock fields. That produces incorrect ordering across daylight-
    saving folds and gaps. Naive timestamps retain their existing semantics.
    """
    return value.astimezone(timezone.utc) if _is_timezone_aware(value) else value


def add_elapsed_minutes(value: datetime, minutes: int) -> datetime:
    """Add elapsed minutes while preserving the original timezone object."""
    duration = timedelta(minutes=minutes)
    if not _is_timezone_aware(value):
        return value + duration
    return (value.astimezone(timezone.utc) + duration).astimezone(value.tzinfo)


def validate_json_value(value: Any, *, path: str = "value") -> None:
    """Reject values that cannot originate from or serialize to strict JSON."""
    pending = [(value, path, 0)]
    visited_items = 0

    while pending:
        current, current_path, depth = pending.pop()
        visited_items += 1
        if visited_items > MAX_JSON_ITEMS:
            raise ValueError(
                f"{path} exceeds the maximum JSON item count of {MAX_JSON_ITEMS}"
            )

        if current is None or isinstance(current, (str, bool)):
            continue
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            if isinstance(current, float) and not math.isfinite(current):
                raise ValueError(
                    f"{current_path} must not contain NaN or infinity"
                )
            continue

        if isinstance(current, list):
            if depth >= MAX_JSON_NESTING:
                raise ValueError(
                    f"{path} exceeds the maximum JSON nesting of {MAX_JSON_NESTING}"
                )
            pending.extend(
                (item, f"{current_path}[{index}]", depth + 1)
                for index, item in enumerate(current)
            )
            continue

        if isinstance(current, dict):
            if depth >= MAX_JSON_NESTING:
                raise ValueError(
                    f"{path} exceeds the maximum JSON nesting of {MAX_JSON_NESTING}"
                )
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError(f"{current_path} object keys must be strings")
                pending.append((item, f"{current_path}.{key}", depth + 1))
            continue

        raise ValueError(f"{current_path} must be JSON-compatible")


class AgenticContract(BaseModel):
    """Strict base configuration for data that may originate from an agent."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ConstraintSource(str, Enum):
    """Authority that introduced an intent constraint."""

    USER = "USER"
    SYSTEM = "SYSTEM"
    DOMAIN = "DOMAIN"
    INFERRED = "INFERRED"


class GoalRequest(AgenticContract):
    """A natural-language goal and the explicit context supplied with it."""

    text: str = Field(..., min_length=1)
    domain: Domain
    timestamp: datetime
    explicit_context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = Field(default=None, min_length=1)

    @field_validator("explicit_context")
    @classmethod
    def context_must_be_json_compatible(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        validate_json_value(value, path="explicit_context")
        return value


class IntentConstraint(AgenticContract):
    """A typed constraint attached to an interpretation or plan."""

    type: str = Field(..., min_length=1)
    value: Any
    hard: StrictBool = False
    source: ConstraintSource

    @field_validator("value")
    @classmethod
    def value_must_be_present_and_json_compatible(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("constraint value must not be null")
        validate_json_value(value, path="constraint value")
        return value


class ContextInterpretation(AgenticContract):
    """Structured interpretation of a GoalRequest before planning."""

    objective: str = Field(..., min_length=1)
    entities: Dict[str, Any]
    explicit_constraints: List[IntentConstraint]
    inferred_context: Dict[str, Any]
    assumptions: List[str]
    missing_information: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def confidence_must_be_numeric(cls, value: Any) -> float:
        return _validate_confidence(value)

    @field_validator("entities", "inferred_context")
    @classmethod
    def context_maps_must_be_json_compatible(
        cls, value: Dict[str, Any]
    ) -> Dict[str, Any]:
        validate_json_value(value, path="interpretation context")
        return value

    @field_validator("assumptions", "missing_information")
    @classmethod
    def explanation_items_must_not_be_blank(cls, value: List[str]) -> List[str]:
        if any(not item.strip() for item in value):
            raise ValueError("text entries must not be blank")
        return value


class IntentStep(AgenticContract):
    """One time-relative intent state; never a candidate selection."""

    step_id: str = Field(..., min_length=1)
    offset_minutes: int = Field(..., ge=0, strict=True)
    intent: Dict[str, Any] = Field(..., min_length=1)
    transition_reason: str = Field(..., min_length=1)
    completion_condition: Optional[Dict[str, Any]] = None

    @field_validator("intent", "completion_condition")
    @classmethod
    def dynamic_fields_must_be_json_compatible(cls, value: Any) -> Any:
        validate_json_value(value, path="intent step")
        return value


class IntentPlan(AgenticContract):
    """A validated-shape, time-aware description of intent."""

    plan_id: str = Field(..., min_length=1)
    domain: Domain
    objective: str = Field(..., min_length=1)
    current_state: Dict[str, Any]
    desired_state: Dict[str, Any]
    constraints: List[IntentConstraint]
    steps: List[IntentStep] = Field(
        ...,
        min_length=1,
        max_length=MAX_PLAN_STEPS,
    )
    assumptions: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    expires_at: Optional[datetime] = None
    planner_version: str = Field(..., min_length=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def confidence_must_be_numeric(cls, value: Any) -> float:
        return _validate_confidence(value)

    @field_validator("current_state", "desired_state")
    @classmethod
    def state_must_be_json_compatible(
        cls, value: Dict[str, Any]
    ) -> Dict[str, Any]:
        validate_json_value(value, path="plan state")
        return value

    @field_validator("assumptions")
    @classmethod
    def assumptions_must_not_be_blank(cls, value: List[str]) -> List[str]:
        if any(not item.strip() for item in value):
            raise ValueError("assumptions must not contain blank entries")
        return value

    @model_validator(mode="after")
    def validate_plan_structure(self) -> "IntentPlan":
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")

        offsets = [step.offset_minutes for step in self.steps]
        if any(current <= previous for previous, current in zip(offsets, offsets[1:])):
            raise ValueError("steps must use strictly increasing offset_minutes")

        if self.expires_at is not None:
            if _is_timezone_aware(self.created_at) != _is_timezone_aware(self.expires_at):
                raise ValueError("created_at and expires_at must use matching timezone awareness")
            if datetime_instant(self.expires_at) <= datetime_instant(self.created_at):
                raise ValueError("expires_at must be later than created_at")

        return self


class OutcomeEvent(AgenticContract):
    """An observed event associated with a plan step."""

    event_type: str = Field(..., min_length=1)
    timestamp: datetime
    plan_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    metadata: Dict[str, Any]

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_json_compatible(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        validate_json_value(value, path="outcome metadata")
        return value


class ExecutionTrace(AgenticContract):
    """Phase-1 trace envelope; lifecycle population is deferred to Phase 4."""

    trace_id: str = Field(..., min_length=1)
    goal_request: GoalRequest
    interpretation: ContextInterpretation
    plan: IntentPlan
    validation_results: List[Dict[str, Any]]
    active_step: IntentStep
    safety_decisions: List[Dict[str, Any]]
    ranking_trace: Any
    outcome_events: List[OutcomeEvent]
    latency: Dict[str, float]

    @field_validator(
        "validation_results",
        "safety_decisions",
        "ranking_trace",
    )
    @classmethod
    def trace_data_must_be_json_compatible(cls, value: Any) -> Any:
        validate_json_value(value, path="execution trace")
        return value

    @field_validator("latency", mode="before")
    @classmethod
    def latency_values_must_be_nonnegative(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("latency must be an object")
        for stage, duration in value.items():
            if not isinstance(stage, str) or not stage.strip():
                raise ValueError("latency stage names must not be blank")
            if isinstance(duration, bool) or not isinstance(duration, (int, float)):
                raise ValueError("latency values must be numeric")
            try:
                numeric_duration = float(duration)
            except (OverflowError, ValueError) as exc:
                raise ValueError("latency values must be finite") from exc
            if not math.isfinite(numeric_duration) or duration < 0:
                raise ValueError("latency values must be finite and nonnegative")
        return value
