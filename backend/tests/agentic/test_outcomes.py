from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from intent_engine.agentic.application import (
    FixedStreamingDemoPolicyResolver, InMemoryPlanRegistry, PlanExecutionError, V4PlanningService,
)
from intent_engine.agentic.outcome_evaluator import InMemoryOutcomeStore, OutcomeEvaluation, PlanStatus
from intent_engine.api import app
from intent_engine.api_v4 import get_v4_planning_service
from intent_engine.schemas import Domain, Item


@pytest.fixture
def harness():
    clock = [datetime(2026, 10, 9, 12, tzinfo=timezone.utc)]
    instance = V4PlanningService(clock=lambda: clock[0])
    plan = instance.create_plan(text="bedtime in an hour", domain=Domain.STREAMING, explicit_context={}).plan
    items = [Item(item_id="calm", title="Calm", base_score=1, attributes={"maturity": "kids", "calm_score": 0.95}),
             Item(item_id="wild", title="Wild", base_score=2, attributes={"maturity": "kids", "calm_score": 0.1}),
             Item(item_id="adult", title="Adult", base_score=3, attributes={"maturity": "adult", "calm_score": 1}),
             Item(item_id="missing", title="Missing", base_score=1, attributes={"maturity": "kids"})]
    trace = instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    return instance, plan, clock, items, trace


def report(harness, event_type="CONTENT_STARTED", candidate="calm", **updates):
    instance, plan, _, _, _ = harness
    values = {"plan_id": plan.plan_id, "step_id": plan.steps[0].step_id,
              "event_type": event_type, "metadata": {"candidate_id": candidate} if candidate is not None else {}}
    return instance.observe(**{**values, **updates})


@pytest.mark.parametrize("candidate, expected", [("calm", "ON_TRACK"), ("wild", "OFF_TRACK"), ("missing", "UNKNOWN")])
def test_evaluation_from_retained_candidate_not_client_metadata(harness, candidate, expected):
    result = report(harness, candidate=candidate)
    assert result.evaluation.value == expected
    assert result.plan_status == PlanStatus.ACTIVE
    assert result.event_count == 1
    assert "not causal" in result.explanation


@pytest.mark.parametrize("kind", ["ITEM_SELECTED", "CONTENT_STARTED", "CONTENT_COMPLETED", "CONTENT_STOPPED", "USER_OVERRIDE"])
def test_supported_interactions_and_no_early_advancement(harness, kind):
    instance, plan, _, _, _ = harness
    result = report(harness, event_type=kind)
    assert result.active_step_id == plan.steps[0].step_id
    assert result.plan_status == PlanStatus.ACTIVE
    assert instance.advance_plan(plan_id=plan.plan_id).active_step_id == plan.steps[0].step_id


def test_server_clock_advance_resets_step_evaluation(harness):
    instance, plan, clock, items, _ = harness
    report(harness)
    clock[0] += timedelta(minutes=25)
    result = instance.advance_plan(plan_id=plan.plan_id)
    assert result.active_step_id == plan.steps[1].step_id
    assert result.evaluation == OutcomeEvaluation.UNKNOWN
    assert result.next_transition_minutes == 25
    with pytest.raises(PlanExecutionError) as error:
        report(harness, step_id=plan.steps[1].step_id)
    assert error.value.code == "stale_outcome"
    new_trace = instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    assert len(new_trace.outcome_events) == 1
    assert new_trace.outcome_events[0].timestamp == plan.created_at
    assert report(harness, step_id=plan.steps[1].step_id).evaluation == OutcomeEvaluation.ON_TRACK


def test_final_completion_terminal_and_not_causal(harness):
    instance, plan, clock, items, _ = harness
    clock[0] += timedelta(minutes=50)
    instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    result = report(harness, event_type="CONTENT_COMPLETED", step_id=plan.steps[-1].step_id)
    assert result.plan_status == PlanStatus.COMPLETE
    assert result.evaluation == OutcomeEvaluation.COMPLETE
    assert result.next_transition_minutes is None
    assert instance.advance_plan(plan_id=plan.plan_id).plan_status == PlanStatus.COMPLETE
    with pytest.raises(PlanExecutionError) as error:
        instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    assert error.value.code == "plan_terminal"


@pytest.mark.parametrize("kind", ["PLAN_CANCELLED", "SESSION_ENDED"])
def test_cancel_rejects_future_execution_and_observation(harness, kind):
    instance, plan, _, items, _ = harness
    result = report(harness, event_type=kind, candidate=None)
    assert result.plan_status == PlanStatus.CANCELLED
    assert result.evaluation == OutcomeEvaluation.UNKNOWN
    with pytest.raises(PlanExecutionError):
        instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    with pytest.raises(PlanExecutionError):
        report(harness)


@pytest.mark.parametrize("updates", [{"metadata": {}}, {"metadata": {"candidate_id": "adult"}},
    {"metadata": {"candidate_id": "unknown"}}, {"metadata": {"candidate_id": "calm", "energy": 0}},
    {"metadata": {"candidate_id": "calm", "hard": False}}, {"metadata": {"candidate_id": []}},
    {"event_type": "SET_SCORE"}])
def test_malformed_and_unsafe_outcomes_not_recorded(harness, updates):
    instance, plan, _, _, _ = harness
    with pytest.raises(PlanExecutionError) as error:
        report(harness, **updates)
    assert error.value.status_code == 422
    assert instance.advance_plan(plan_id=plan.plan_id).event_count == 0


@pytest.mark.parametrize("step", ["unknown", 1])
def test_wrong_step_rejected(harness, step):
    with pytest.raises(PlanExecutionError) as error:
        report(harness, step_id=step)
    assert error.value.status_code == 409


def test_expired_and_missing_indistinguishable(harness):
    instance, plan, clock, _, _ = harness
    clock[0] += timedelta(minutes=60)
    for plan_id in (plan.plan_id, "unknown"):
        with pytest.raises(PlanExecutionError) as error:
            instance.advance_plan(plan_id=plan_id)
        assert error.value.status_code == 404


def test_foreign_owner_and_policy_drift(harness):
    instance, plan, _, _, _ = harness
    instance._policy_resolver = FixedStreamingDemoPolicyResolver(owner_id="foreign")
    with pytest.raises(PlanExecutionError) as error:
        report(harness)
    assert error.value.status_code == 404
    instance._policy_resolver = FixedStreamingDemoPolicyResolver(session_id="changed")
    with pytest.raises(PlanExecutionError) as error:
        report(harness)
    assert error.value.status_code == 409


def test_observation_requires_execution(harness):
    instance, _, _, _, _ = harness
    plan = instance.create_plan(text="focus", domain=Domain.STREAMING, explicit_context={}).plan
    with pytest.raises(PlanExecutionError) as error:
        instance.observe(plan_id=plan.plan_id, step_id=plan.steps[0].step_id, event_type="USER_OVERRIDE", metadata={})
    assert error.value.code == "stale_outcome"


def test_bounded_event_count_under_concurrency(harness):
    instance, plan, _, _, _ = harness
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: report(harness), range(100)))
    assert instance.advance_plan(plan_id=plan.plan_id).event_count == 100
    with pytest.raises(PlanExecutionError) as error:
        report(harness)
    assert error.value.code == "outcome_limit"


def test_terminal_state_not_independently_evicted():
    store = InMemoryOutcomeStore(capacity=1)
    store.get("owner", "first").status = PlanStatus.CANCELLED
    with pytest.raises(ValueError):
        store.get("owner", "second")
    assert store.get("owner", "first").status == PlanStatus.CANCELLED


def test_outcomes_do_not_change_ranking_and_trace_is_detached(harness):
    instance, plan, _, items, first = harness
    result = report(harness)
    second = instance.execute_plan(plan_id=plan.plan_id, candidates=items)
    assert second.ranking_trace == first.ranking_trace
    assert len(second.outcome_events) == 1
    second.outcome_events.clear()
    assert instance.advance_plan(plan_id=plan.plan_id).event_count == result.event_count


def test_http_contracts_and_server_timestamp(harness):
    instance, plan, _, _, _ = harness
    app.dependency_overrides[get_v4_planning_service] = lambda: instance
    try:
        with TestClient(app) as client:
            payload = {"plan_id": plan.plan_id, "step_id": plan.steps[0].step_id,
                       "event_type": "CONTENT_STARTED", "metadata": {"candidate_id": "calm"}}
            response = client.post("/v4/observe", json=payload)
            assert response.status_code == 200
            assert response.json()["evaluation"] == "ON_TRACK"
            assert client.post("/v4/advance", json={"plan_id": plan.plan_id}).json()["event_count"] == 1
            for invalid in ({}, {**payload, "timestamp": "2030-01-01"},
                            {**payload, "event_type": "SET_SCORE"}, {**payload, "metadata": {"policy": "adult"}}):
                assert client.post("/v4/observe", json=invalid).status_code == 422
            assert client.post("/v4/advance", json={"plan_id": "missing"}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_v4_planning_service, None)
