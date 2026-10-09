"""Bounded deterministic lifecycle; client reports are not causal evidence."""

from collections import OrderedDict
from datetime import datetime
from enum import Enum
import math
from typing import Dict, List, Optional

from pydantic import Field

from intent_engine.agentic.schemas import AgenticContract, ExecutionTrace, IntentPlan, OutcomeEvent, datetime_instant


class OutcomeType(str, Enum):
    ITEM_SELECTED = "ITEM_SELECTED"
    CONTENT_STARTED = "CONTENT_STARTED"
    CONTENT_COMPLETED = "CONTENT_COMPLETED"
    CONTENT_STOPPED = "CONTENT_STOPPED"
    USER_OVERRIDE = "USER_OVERRIDE"
    PLAN_CANCELLED = "PLAN_CANCELLED"
    SESSION_ENDED = "SESSION_ENDED"


class PlanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class OutcomeEvaluation(str, Enum):
    ON_TRACK = "ON_TRACK"
    OFF_TRACK = "OFF_TRACK"
    UNKNOWN = "UNKNOWN"
    COMPLETE = "COMPLETE"


class LifecycleResponse(AgenticContract):
    plan_status: PlanStatus
    evaluation: OutcomeEvaluation
    active_step_id: str
    next_transition_minutes: Optional[float] = Field(default=None, ge=0)
    event_count: int = Field(default=0, ge=0)
    explanation: str


class OutcomeState:
    """Private state; all access is serialized by the application's lock."""

    def __init__(self):
        self.status = PlanStatus.ACTIVE
        self.events: List[OutcomeEvent] = []
        self.trace: Optional[ExecutionTrace] = None
        self.evaluation = OutcomeEvaluation.UNKNOWN
        self.evaluated_step_id: Optional[str] = None


class InMemoryOutcomeStore:
    def __init__(self, capacity: int = 256):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("outcome capacity must be positive")
        self.capacity = capacity
        self._states: Dict[tuple, OutcomeState] = OrderedDict()

    def get(self, owner_id: str, plan_id: str) -> OutcomeState:
        key = (owner_id, plan_id)
        if key not in self._states:
            # Never evict terminal state independently of a retained plan: that
            # could resurrect a cancelled plan. Fail closed at capacity instead.
            if len(self._states) >= self.capacity:
                raise ValueError("outcome capacity reached")
            self._states[key] = OutcomeState()
        return self._states[key]

    def purge(self, registry, now: datetime):
        for owner, plan_id in list(self._states):
            if registry.get(owner_id=owner, plan_id=plan_id, now=now) is None:
                del self._states[(owner, plan_id)]


def evaluate(event: OutcomeEvent, trace: ExecutionTrace) -> OutcomeEvaluation:
    """Only compare playback reports to server-retained candidate attributes."""
    if event.event_type not in {"ITEM_SELECTED", "CONTENT_STARTED", "CONTENT_COMPLETED"}:
        return OutcomeEvaluation.UNKNOWN
    candidate = next((row for row in trace.ranking_trace.ranked_candidates
                      if row.item.item_id == event.metadata.get("candidate_id")), None)
    if candidate is None or candidate.status.value == "blocked":
        return OutcomeEvaluation.UNKNOWN
    if trace.plan.objective != "wind_down":
        return OutcomeEvaluation.UNKNOWN
    calm = candidate.item.attributes.get("calm_score")
    target = trace.active_step.intent.get("energy")
    if any(isinstance(value, bool) or not isinstance(value, (float, int))
           or not math.isfinite(value) or not 0 <= value <= 1 for value in (calm, target)):
        return OutcomeEvaluation.UNKNOWN
    return OutcomeEvaluation.ON_TRACK if 1 - calm <= target + 1e-9 else OutcomeEvaluation.OFF_TRACK


def advance(plan: IntentPlan, now: datetime, state: OutcomeState, active_step_id: str) -> LifecycleResponse:
    elapsed = (datetime_instant(now) - datetime_instant(plan.created_at)).total_seconds() / 60
    upcoming = [step.offset_minutes - elapsed for step in plan.steps if step.offset_minutes > elapsed]
    evaluation = OutcomeEvaluation.UNKNOWN
    if state.status == PlanStatus.COMPLETE:
        evaluation = OutcomeEvaluation.COMPLETE
    elif state.status == PlanStatus.ACTIVE and state.evaluated_step_id == active_step_id:
        evaluation = state.evaluation
    return LifecycleResponse(
        plan_status=state.status, evaluation=evaluation, active_step_id=active_step_id,
        next_transition_minutes=min(upcoming) if upcoming and state.status == PlanStatus.ACTIVE else None,
        event_count=len(state.events),
        explanation="Playback reports describe observed interaction, not causal goal success. Temporal steps follow server time.",
    )
