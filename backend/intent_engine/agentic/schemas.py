"""Typed contracts for the V4 agentic intent boundary.

These models describe goals and intent plans only.  They intentionally contain
no candidate-selection or scoring behavior.  Inputs at this boundary may come
from probabilistic components, so unknown fields are rejected instead of being
silently ignored.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from intent_engine.schemas import Domain, Item, RankingMode


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


class TraceValidationStatus(str, Enum):
    """Outcome of one deterministic validation stage."""

    PASSED = "passed"
    FAILED = "failed"


class TraceValidationIssue(AgenticContract):
    """Machine-readable validation evidence recorded in a trace."""

    code: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class TraceValidationResult(AgenticContract):
    """Typed receipt for a validation stage.

    A successful execution trace currently records the deterministic plan
    execution boundary.  Failed-attempt traces require a separate partial
    lifecycle contract because they may not have a plan or ranking result.
    """

    stage: str = Field(..., min_length=1)
    status: TraceValidationStatus
    evaluated_at: datetime
    plan_id: str = Field(..., min_length=1)
    domain: Domain
    issues: List[TraceValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def issues_must_match_status(self) -> "TraceValidationResult":
        if self.status == TraceValidationStatus.PASSED and self.issues:
            raise ValueError("passed validation results must not contain issues")
        if self.status == TraceValidationStatus.FAILED and not self.issues:
            raise ValueError("failed validation results must contain an issue")
        return self


class IntentApplicationTrace(AgenticContract):
    """Intent data at each deterministic execution boundary."""

    domain: Domain
    canonical_intent: Dict[str, Any]
    applied_intent: Dict[str, Any]
    applied_hard_constraints: Dict[str, Any]
    observational_signals: Dict[str, Any]

    @field_validator(
        "canonical_intent",
        "applied_intent",
        "applied_hard_constraints",
        "observational_signals",
    )
    @classmethod
    def values_must_be_json_compatible(
        cls, value: Dict[str, Any]
    ) -> Dict[str, Any]:
        validate_json_value(value, path="intent application")
        return value

    @model_validator(mode="after")
    def applied_and_observational_signals_must_be_disjoint(
        self,
    ) -> "IntentApplicationTrace":
        overlap = sorted(set(self.applied_intent) & set(self.observational_signals))
        if overlap:
            raise ValueError(
                "applied and observational signals overlap: " + ", ".join(overlap)
            )
        return self


class CandidateSafetyDecision(AgenticContract):
    """Observed hard-gate outcome for one ranked candidate.

    The reason is the generic evidence emitted by the ranker.  This record
    intentionally does not attribute a block to a particular constraint,
    because the current adapter contract does not expose that causality.
    """

    candidate_id: str
    rank: int = Field(..., ge=1, strict=True)
    blocked: StrictBool
    reason: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def reason_must_match_blocked_state(self) -> "CandidateSafetyDecision":
        if self.blocked and self.reason is None:
            raise ValueError("blocked safety decisions require a reason")
        if not self.blocked and self.reason is not None:
            raise ValueError("allowed safety decisions must not contain a block reason")
        return self


def _finite_trace_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


class RankingMultiplierTrace(AgenticContract):
    """Strict copy of the deterministic multipliers used for one item."""

    context: float
    profile: float
    urgency: float
    cost: float
    prophecy: float

    @field_validator("context", "profile", "urgency", "cost", "prophecy", mode="before")
    @classmethod
    def multiplier_must_be_nonnegative(cls, value: Any) -> float:
        numeric = _finite_trace_number(value, field_name="multiplier")
        if numeric < 0:
            raise ValueError("multiplier must be nonnegative")
        return numeric


class RankingScoreTrace(AgenticContract):
    """Strict score evidence copied from the existing ranking response."""

    base_score: float
    multipliers: RankingMultiplierTrace
    diversity_penalty: float
    final_score: float
    blocked: StrictBool
    block_reason: Optional[str] = Field(default=None, min_length=1)

    @field_validator("base_score", "final_score", mode="before")
    @classmethod
    def scores_must_be_nonnegative(cls, value: Any) -> float:
        numeric = _finite_trace_number(value, field_name="score")
        if numeric < 0:
            raise ValueError("score must be nonnegative")
        return numeric

    @field_validator("diversity_penalty", mode="before")
    @classmethod
    def penalty_must_be_finite(cls, value: Any) -> float:
        return _finite_trace_number(value, field_name="diversity_penalty")

    @model_validator(mode="after")
    def block_evidence_must_be_consistent(self) -> "RankingScoreTrace":
        if self.blocked:
            if self.final_score != 0.0:
                raise ValueError("blocked candidates must have a zero final score")
            if self.block_reason is None:
                raise ValueError("blocked candidates require a block reason")
        elif self.block_reason is not None:
            raise ValueError("unblocked candidates must not contain a block reason")
        return self


class RankedCandidateStatus(str, Enum):
    """Statuses currently emitted by the deterministic domain ranker."""

    BOOSTED = "boosted"
    NEUTRAL = "neutral"
    DEMOTED = "demoted"
    BLOCKED = "blocked"


class RankedCandidateTrace(AgenticContract):
    """One fully explained deterministic ranking decision."""

    item: Item
    rank: int = Field(..., ge=1, strict=True)
    final_score: float
    status: RankedCandidateStatus
    explanation: str
    score_breakdown: RankingScoreTrace

    @field_validator("final_score", mode="before")
    @classmethod
    def final_score_must_be_nonnegative(cls, value: Any) -> float:
        numeric = _finite_trace_number(value, field_name="final_score")
        if numeric < 0:
            raise ValueError("final_score must be nonnegative")
        return numeric

    @field_validator("item")
    @classmethod
    def item_must_be_traceable(cls, value: Item) -> Item:
        validate_json_value(value.attributes, path="ranked candidate attributes")
        for field_name in (
            "base_score",
            "price",
            "popularity_score",
            "quality_score",
        ):
            _finite_trace_number(getattr(value, field_name), field_name=field_name)
        return value

    @model_validator(mode="after")
    def score_and_status_must_be_consistent(self) -> "RankedCandidateTrace":
        if self.final_score != self.score_breakdown.final_score:
            raise ValueError("candidate and score-breakdown final scores must match")
        if self.item.base_score != self.score_breakdown.base_score:
            raise ValueError("candidate and score-breakdown base scores must match")
        if self.score_breakdown.blocked != (
            self.status == RankedCandidateStatus.BLOCKED
        ):
            raise ValueError("candidate status and blocked evidence must match")

        if not self.score_breakdown.blocked:
            breakdown = self.score_breakdown
            if breakdown.diversity_penalty > 0:
                raise ValueError("diversity penalty must not be positive")
            expected_score = (
                breakdown.base_score
                * breakdown.multipliers.context
                * breakdown.multipliers.profile
                * breakdown.multipliers.urgency
                * breakdown.multipliers.cost
                * breakdown.multipliers.prophecy
            )
            expected_score = max(
                0.0,
                expected_score + breakdown.diversity_penalty,
            )
            if self.final_score != expected_score:
                raise ValueError("final score does not match its score breakdown")

            if self.final_score > self.item.base_score:
                expected_status = RankedCandidateStatus.BOOSTED
            elif self.final_score < self.item.base_score * 0.9:
                expected_status = RankedCandidateStatus.DEMOTED
            else:
                expected_status = RankedCandidateStatus.NEUTRAL
            if self.status != expected_status:
                raise ValueError("candidate status does not match its final score")
        return self


class RankingDecisionTrace(AgenticContract):
    """Typed deterministic output and replay-version metadata."""

    domain: Domain
    mode_used: RankingMode
    intent_type: str = Field(..., min_length=1)
    engine_version: str = Field(..., min_length=1)
    adapter_version: str = Field(..., min_length=1)
    input_candidates: List[Item] = Field(..., min_length=1)
    ranked_candidates: List[RankedCandidateTrace] = Field(..., min_length=1)

    @field_validator("input_candidates")
    @classmethod
    def input_candidates_must_be_traceable(cls, value: List[Item]) -> List[Item]:
        for item in value:
            validate_json_value(item.attributes, path="input candidate attributes")
            for field_name in (
                "base_score",
                "price",
                "popularity_score",
                "quality_score",
            ):
                _finite_trace_number(getattr(item, field_name), field_name=field_name)
        return value

    @model_validator(mode="after")
    def candidate_inputs_and_order_must_be_coherent(
        self,
    ) -> "RankingDecisionTrace":
        ranks = [entry.rank for entry in self.ranked_candidates]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("ranked candidates must use contiguous response order")

        scores = [entry.final_score for entry in self.ranked_candidates]
        if any(current > previous for previous, current in zip(scores, scores[1:])):
            raise ValueError("ranked candidates must be ordered by final score")

        input_payloads = sorted(
            json.dumps(
                item.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            for item in self.input_candidates
        )
        output_payloads = sorted(
            json.dumps(
                entry.item.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            for entry in self.ranked_candidates
        )
        if input_payloads != output_payloads:
            raise ValueError("ranked candidates must match the ranking inputs")
        return self


class TraceLatency(AgenticContract):
    """Nondeterministic measurements kept outside decision canonicalization."""

    ranking_total_ms: float = 0.0
    intent_parsing_ms: float = 0.0
    ranking_ms: float = 0.0
    diversity_check_ms: float = 0.0

    @field_validator(
        "ranking_total_ms",
        "intent_parsing_ms",
        "ranking_ms",
        "diversity_check_ms",
        mode="before",
    )
    @classmethod
    def latency_must_be_nonnegative(cls, value: Any) -> float:
        numeric = _finite_trace_number(value, field_name="latency")
        if numeric < 0:
            raise ValueError("latency must be nonnegative")
        return numeric


class ExecutionTrace(AgenticContract):
    """Typed trace of one successful deterministic V4 execution."""

    trace_id: str = Field(..., min_length=1)
    goal_request: GoalRequest
    interpretation: ContextInterpretation
    plan: IntentPlan
    validation_results: List[TraceValidationResult] = Field(..., min_length=1)
    active_step: IntentStep
    intent_application: IntentApplicationTrace
    safety_decisions: List[CandidateSafetyDecision]
    ranking_trace: RankingDecisionTrace
    outcome_events: List[OutcomeEvent]
    latency: TraceLatency

    @model_validator(mode="after")
    def lifecycle_must_be_coherent(self) -> "ExecutionTrace":
        if self.goal_request.domain != self.plan.domain:
            raise ValueError("goal and plan domains must match")
        if self.intent_application.domain != self.plan.domain:
            raise ValueError("intent application and plan domains must match")
        if self.ranking_trace.domain != self.plan.domain:
            raise ValueError("ranking and plan domains must match")
        if self.ranking_trace.mode_used != RankingMode.ADVANCED:
            raise ValueError("successful V4 execution traces require advanced mode")

        matching_steps = [
            step for step in self.plan.steps if step.step_id == self.active_step.step_id
        ]
        if len(matching_steps) != 1 or matching_steps[0] != self.active_step:
            raise ValueError("active_step must exactly match one plan step")

        for result in self.validation_results:
            if result.status != TraceValidationStatus.PASSED:
                raise ValueError("successful execution traces require passed validation")
            if result.plan_id != self.plan.plan_id or result.domain != self.plan.domain:
                raise ValueError("validation result does not match the traced plan")

        expected_intent_type = self.intent_application.applied_intent.get(
            "intent_type", "unknown"
        )
        if self.ranking_trace.intent_type != expected_intent_type:
            raise ValueError("ranking intent type does not match applied intent")

        ranked = self.ranking_trace.ranked_candidates
        ranked_ids = [entry.item.item_id for entry in ranked]
        safety_ids = [decision.candidate_id for decision in self.safety_decisions]
        if safety_ids != ranked_ids:
            raise ValueError("safety decisions must align with ranked candidates")
        for decision, entry in zip(self.safety_decisions, ranked):
            if decision.rank != entry.rank:
                raise ValueError("safety and ranking positions must match")
            if decision.blocked != entry.score_breakdown.blocked:
                raise ValueError("safety and ranking blocked evidence must match")
            if decision.reason != entry.score_breakdown.block_reason:
                raise ValueError("safety and ranking block reasons must match")

        valid_step_ids = {step.step_id for step in self.plan.steps}
        for event in self.outcome_events:
            if event.plan_id != self.plan.plan_id or event.step_id not in valid_step_ids:
                raise ValueError("outcome event does not match the traced plan")
        return self
