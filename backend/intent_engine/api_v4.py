"""Additive FastAPI routes for the V4 agentic planning boundary."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator

from intent_engine.agentic.application import PlanCreationError, V4PlanningService
from intent_engine.agentic.schemas import (
    AgenticContract,
    IntentPlan,
    validate_json_value,
)
from intent_engine.schemas import Domain


MAX_GOAL_TEXT_LENGTH = 4096

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


_default_v4_service = V4PlanningService()


def get_v4_planning_service() -> V4PlanningService:
    """FastAPI dependency seam for isolated policy, time, and storage tests."""
    return _default_v4_service


@router.post(
    "/plan",
    response_model=IntentPlan,
    summary="Create a deterministic V4 streaming intent plan",
)
async def create_v4_plan(
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
        raise HTTPException(
            status_code=500,
            detail={
                "code": "planning_failed",
                "message": "The plan could not be created.",
            },
        ) from exc


__all__ = [
    "MAX_GOAL_TEXT_LENGTH",
    "V4PlanRequest",
    "get_v4_planning_service",
    "router",
]
