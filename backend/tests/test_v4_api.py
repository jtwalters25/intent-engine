"""API boundary tests for the additive Phase 5A V4 planning endpoint."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from intent_engine.agentic.application import (
    FixedStreamingDemoPolicyResolver,
    InMemoryPlanRegistry,
    V4PlanningService,
)
from intent_engine.agentic.schemas import (
    ConstraintSource,
    IntentPlan,
)
from intent_engine.agentic.validator import CONSTRAINT_TYPE_ALIASES
from intent_engine.api import app
from intent_engine.api_v4 import (
    MAX_GOAL_TEXT_LENGTH,
    get_v4_planning_service,
)
from intent_engine.schemas import Domain


NOW = datetime(2026, 10, 8, 19, 0, tzinfo=timezone.utc)
OWNER_ID = "phase5a-test-owner"
SESSION_ID = "phase5a-test-session"
VALID_GOAL = "The kids are wired and bedtime is in an hour."


@dataclass(frozen=True)
class V4ApiHarness:
    client: TestClient
    service: V4PlanningService
    registry: InMemoryPlanRegistry


@pytest.fixture
def v4_api() -> Iterator[V4ApiHarness]:
    """Give each test isolated trusted dependencies and registry state."""

    registry = InMemoryPlanRegistry()
    service = V4PlanningService(
        policy_resolver=FixedStreamingDemoPolicyResolver(
            owner_id=OWNER_ID,
            session_id=SESSION_ID,
        ),
        registry=registry,
        clock=lambda: NOW,
    )
    missing = object()
    previous = app.dependency_overrides.get(get_v4_planning_service, missing)
    app.dependency_overrides[get_v4_planning_service] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield V4ApiHarness(
                client=client,
                service=service,
                registry=registry,
            )
    finally:
        if previous is missing:
            app.dependency_overrides.pop(get_v4_planning_service, None)
        else:
            app.dependency_overrides[get_v4_planning_service] = previous


def _plan_payload(*, text: str = VALID_GOAL, context=None, **extra):
    payload = {
        "text": text,
        "domain": Domain.STREAMING.value,
        "context": {} if context is None else context,
    }
    payload.update(extra)
    return payload


def _stored_record(harness: V4ApiHarness, plan_id: str):
    record = harness.registry.get(
        owner_id=OWNER_ID,
        plan_id=plan_id,
        now=NOW,
    )
    assert record is not None
    return record


def test_natural_language_streaming_goal_returns_full_valid_plan(
    v4_api: V4ApiHarness,
):
    response = v4_api.client.post("/v4/plan", json=_plan_payload())

    assert response.status_code == 200
    plan = IntentPlan.model_validate(response.json())
    assert plan.domain == Domain.STREAMING
    assert plan.objective == "wind_down"
    assert plan.current_state["viewer"] == "kids"
    assert plan.created_at == NOW
    assert plan.steps

    # The endpoint returns the complete contract, not a lossy summary.
    restored = IntentPlan.model_validate_json(plan.model_dump_json())
    assert restored == plan
    assert restored.model_dump(mode="json") == response.json()

    record = _stored_record(v4_api, plan.plan_id)
    assert record.goal_request.timestamp == NOW
    assert record.goal_request.session_id == SESSION_ID
    assert record.goal_request.text == VALID_GOAL
    assert record.plan == plan


def test_fixed_server_time_and_inputs_produce_deterministic_response(
    v4_api: V4ApiHarness,
):
    first = v4_api.client.post("/v4/plan", json=_plan_payload())
    second = v4_api.client.post("/v4/plan", json=_plan_payload())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["created_at"] == "2026-10-08T19:00:00Z"
    assert len(v4_api.registry) == 1


@pytest.mark.parametrize(
    "text, expected_code",
    [
        ("Recommend something interesting.", "unsupported_goal"),
        ("Help us focus and then wind down for bedtime.", "ambiguous_goal"),
    ],
)
def test_unsupported_and_ambiguous_goals_are_stable_422s(
    v4_api: V4ApiHarness,
    text: str,
    expected_code: str,
):
    first = v4_api.client.post("/v4/plan", json=_plan_payload(text=text))
    second = v4_api.client.post("/v4/plan", json=_plan_payload(text=text))

    assert first.status_code == second.status_code == 422
    assert first.json() == second.json()
    assert first.json()["detail"]["code"] == expected_code
    assert len(v4_api.registry) == 0


@pytest.mark.parametrize(
    "domain",
    [
        Domain.RIDE_MATCHING,
        Domain.FOOD_DELIVERY,
        Domain.MUSIC,
        Domain.ECOMMERCE,
    ],
)
def test_non_streaming_planning_is_a_stable_422(
    v4_api: V4ApiHarness,
    domain: Domain,
):
    payload = _plan_payload()
    payload["domain"] = domain.value

    response = v4_api.client.post("/v4/plan", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_domain"
    assert len(v4_api.registry) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": "", "domain": "streaming", "context": {}},
        {
            "text": "x" * (MAX_GOAL_TEXT_LENGTH + 1),
            "domain": "streaming",
            "context": {},
        },
        {"text": VALID_GOAL, "domain": "not-a-domain", "context": {}},
        {"text": VALID_GOAL, "domain": "streaming", "context": []},
        {
            "text": VALID_GOAL,
            "domain": "streaming",
            "context": {},
            "unknown": "value",
        },
    ],
)
def test_malformed_or_unknown_request_fields_are_rejected(
    v4_api: V4ApiHarness,
    payload,
):
    response = v4_api.client.post("/v4/plan", json=payload)

    assert response.status_code == 422
    assert len(v4_api.registry) == 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("timestamp", "2020-01-01T00:00:00Z"),
        ("session_id", "attacker-session"),
        ("interpretation", {"objective": "wind_down"}),
        ("plan", {"plan_id": "attacker-plan"}),
        ("constraints", [{"type": "viewer_maturity", "value": "adult"}]),
        ("hard", True),
        ("normalized", {"viewer_profile": "adult"}),
        ("candidates", [{"item_id": "chosen-by-client"}]),
    ],
)
def test_client_cannot_submit_server_owned_or_later_phase_fields(
    v4_api: V4ApiHarness,
    field: str,
    value,
):
    response = v4_api.client.post(
        "/v4/plan",
        json=_plan_payload(**{field: value}),
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(
        error["type"] == "extra_forbidden" and error["loc"][-1] == field
        for error in errors
    )
    assert len(v4_api.registry) == 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("maturity_gate", "adult"),
        ("viewer_maturity", "adult"),
        ("constraints", [{"type": "viewer_maturity", "value": "adult"}]),
        ("hard", True),
        ("normalized", {"viewer_profile": "adult"}),
        ("candidates", [{"item_id": "chosen-by-client"}]),
        ("timestamp", "2020-01-01T00:00:00Z"),
        ("session_id", "attacker-session"),
    ],
)
def test_authority_and_later_phase_fields_are_rejected_inside_context(
    v4_api: V4ApiHarness,
    field: str,
    value,
):
    first = v4_api.client.post(
        "/v4/plan",
        json=_plan_payload(context={field: value}),
    )
    second = v4_api.client.post(
        "/v4/plan",
        json=_plan_payload(context={field: value}),
    )

    assert first.status_code == second.status_code == 422
    assert first.json() == second.json()
    assert first.json()["detail"]["code"] == "unsupported_context"
    assert len(v4_api.registry) == 0


def test_untrusted_adult_context_cannot_weaken_server_owned_kids_policy(
    v4_api: V4ApiHarness,
):
    response = v4_api.client.post(
        "/v4/plan",
        json=_plan_payload(context={"viewer": "adult"}),
    )

    assert response.status_code == 200
    plan = IntentPlan.model_validate(response.json())
    assert plan.current_state["viewer"] == "kids"

    maturity_constraints = [
        constraint
        for constraint in plan.constraints
        if CONSTRAINT_TYPE_ALIASES.get(constraint.type, constraint.type)
        == "viewer_maturity"
    ]
    assert len(maturity_constraints) == 1
    assert maturity_constraints[0].value == "kids"
    assert maturity_constraints[0].hard is True
    assert maturity_constraints[0].source == ConstraintSource.SYSTEM

    record = _stored_record(v4_api, plan.plan_id)
    assert dict(record.active_profile_context) == {"viewer": "kids"}
    assert record.interpretation.entities["viewer"] == "kids"
    assert all(
        CONSTRAINT_TYPE_ALIASES.get(constraint.type, constraint.type)
        != "viewer_maturity"
        or constraint.value == "kids"
        for constraint in record.authoritative_constraints
    )


def test_unexpected_service_failure_is_generic_and_does_not_leak(
    v4_api: V4ApiHarness,
):
    secret = "database-password=do-not-leak"

    class ExplodingPlanningService:
        def create_plan(self, **_kwargs):
            raise RuntimeError(secret)

    app.dependency_overrides[get_v4_planning_service] = (
        lambda: ExplodingPlanningService()
    )

    response = v4_api.client.post("/v4/plan", json=_plan_payload())

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "planning_failed",
            "message": "The plan could not be created.",
        }
    }
    assert secret not in response.text


def test_existing_rank_endpoint_remains_operational(v4_api: V4ApiHarness):
    response = v4_api.client.post(
        "/rank",
        json={
            "items": [
                {
                    "item_id": "legacy-item",
                    "title": "Legacy Item",
                    "base_score": 0.8,
                    "attributes": {},
                }
            ],
            "user_context": {"user_id": "legacy-user"},
            "intent_text": "show me popular items",
            "mode": "simple",
        },
    )

    assert response.status_code == 200
    assert response.json()["ranked_items"][0]["item"]["item_id"] == "legacy-item"


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "/v4/execute", {}),
        ("post", "/v4/observe", {}),
        ("get", "/v4/plans/plan_123", None),
        ("get", "/v4/traces/trace_123", None),
    ],
)
def test_later_phase_routes_are_not_exposed(
    v4_api: V4ApiHarness,
    method: str,
    path: str,
    body,
):
    request = getattr(v4_api.client, method)
    response = request(path) if body is None else request(path, json=body)

    assert response.status_code == 404
