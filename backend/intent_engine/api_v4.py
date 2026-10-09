"""Additive FastAPI routes for the V4 agentic planning boundary."""

import logging
from typing import Any, Dict, List
import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict, Field, field_validator, model_validator

from intent_engine.agentic.application import PlanCreationError, PlanExecutionError, V4PlanningService
from intent_engine.agentic.llm_planner import configured_llm_components
from intent_engine.agentic.outcome_evaluator import LifecycleResponse, OutcomeType
from intent_engine.agentic.schemas import (
    AgenticContract,
    IntentPlan,
    IntentStep,
    RankedCandidateTrace,
    validate_json_value,
)
from intent_engine.schemas import Domain, Item


MAX_GOAL_TEXT_LENGTH = 4096
MAX_EXECUTION_CANDIDATES = 100


class V4Candidate(Item):
    """Bounded external candidate; legacy Item acceptance stays unchanged."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    item_id: str = Field(..., min_length=1, max_length=256)
    title: str = Field(..., min_length=1, max_length=1024)
    base_score: float = Field(default=0.0, ge=0, le=1_000_000)

    @field_validator("base_score", "price", "popularity_score", "quality_score", mode="before")
    @classmethod
    def finite_numeric_fields(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("candidate scores and prices must be numeric")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("candidate scores and prices must be finite")
        return value

    @field_validator("attributes")
    @classmethod
    def validate_streaming_attributes(cls, values):
        validate_json_value(values, path="candidate.attributes")
        maturity = values.get("maturity")
        if not isinstance(maturity, str) or maturity not in {"kids", "family", "teen", "adult"}:
            raise ValueError("streaming candidates require a known maturity label")
        for field in ("calm_score", "complexity"):
            if field in values:
                value = values[field]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError(f"{field} must be a number between 0 and 1")
        return values


class V4ExecuteRequest(AgenticContract):
    plan_id: str = Field(..., min_length=1, max_length=128)
    candidates: List[V4Candidate] = Field(..., min_length=1, max_length=MAX_EXECUTION_CANDIDATES)

    @model_validator(mode="after")
    def candidate_ids_are_unique(self):
        ids = [candidate.item_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate item_id values must be unique")
        return self


class V4AdvanceRequest(AgenticContract):
    plan_id: str = Field(..., min_length=1, max_length=128)


class V4ObserveRequest(V4AdvanceRequest):
    step_id: str = Field(..., min_length=1, max_length=256)
    event_type: OutcomeType
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def bounded_metadata(cls, value):
        validate_json_value(value, path="outcome metadata")
        if set(value) - {"candidate_id"}:
            raise ValueError("only candidate_id is supported")
        return value


class V4ExecutionResponse(AgenticContract):
    trace_id: str
    active_step: IntentStep
    ranking: List[RankedCandidateTrace]
    explanation: Dict[str, str]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v4", tags=["v4"])


class V4PlanRequest(AgenticContract):
    """Public plan request with no client-controlled authority fields."""

    text: str = Field(..., min_length=1, max_length=MAX_GOAL_TEXT_LENGTH)
    domain: Domain
    context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def context_must_be_bounded_json(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        validate_json_value(value, path="context")
        return value


_v4_interpreter, _v4_planner = configured_llm_components()
_default_v4_service = V4PlanningService(interpreter=_v4_interpreter, planner=_v4_planner)


def get_v4_planning_service() -> V4PlanningService:
    """FastAPI dependency seam for isolated policy, time, and storage tests."""
    return _default_v4_service


@router.post(
    "/plan",
    response_model=IntentPlan,
    summary="Create a deterministic V4 streaming intent plan",
)
def create_v4_plan(
    request: V4PlanRequest,
    service: V4PlanningService = Depends(get_v4_planning_service),
) -> IntentPlan:
    """Interpret a goal and create a plan without ranking candidates."""
    try:
        result = service.create_plan(
            text=request.text,
            domain=request.domain,
            explicit_context=request.context,
        )
        return result.plan
    except PlanCreationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.public_message},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected V4 planning failure")
        raise HTTPException(status_code=500, detail={"code": "planning_failed", "message": "The plan could not be created."}) from exc


@router.post("/execute", response_model=V4ExecutionResponse)
async def execute_v4_plan(
    request: V4ExecuteRequest,
    service: V4PlanningService = Depends(get_v4_planning_service),
) -> V4ExecutionResponse:
    """Execute a stored streaming plan using current server-owned policy."""
    try:
        trace = service.execute_plan(
            plan_id=request.plan_id,
            candidates=[Item.model_validate(candidate.model_dump()) for candidate in request.candidates],
        )
        return V4ExecutionResponse(
            trace_id=trace.trace_id, active_step=trace.active_step,
            ranking=trace.ranking_trace.ranked_candidates,
            explanation={
                "plan_reason": trace.active_step.transition_reason,
                "ranking_reason": "Ranking uses deterministic multipliers and authoritative hard safety gates.",
            },
        )
    except PlanExecutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.public_message}) from exc
    except Exception as exc:
        logger.exception("Unexpected V4 execution failure")
        raise HTTPException(status_code=500, detail={"code": "execution_failed", "message": "The plan could not be executed."}) from exc


__all__ = [
    "MAX_GOAL_TEXT_LENGTH",
    "V4PlanRequest",
    "V4ExecuteRequest",
    "V4ExecutionResponse",
    "get_v4_planning_service",
    "router",
]


@router.post("/advance", response_model=LifecycleResponse)
def advance_v4_plan(request: V4AdvanceRequest, service: V4PlanningService = Depends(get_v4_planning_service)):
    """Evaluate lifecycle at server time; never skip steps or expose traces."""
    try:
        return service.advance_plan(plan_id=request.plan_id)
    except PlanExecutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.public_message}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "lifecycle_failed", "message": "Lifecycle is unavailable."}) from exc


@router.post("/observe", response_model=LifecycleResponse)
def observe_v4_plan(request: V4ObserveRequest, service: V4PlanningService = Depends(get_v4_planning_service)):
    """Accept a playback report bound to current retained execution evidence."""
    try:
        return service.observe(plan_id=request.plan_id, step_id=request.step_id,
                               event_type=request.event_type, metadata=request.metadata)
    except PlanExecutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.public_message}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "observation_failed", "message": "The outcome could not be recorded."}) from exc
