"""End-to-end stored-plan execution and external trust boundary tests."""

from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from intent_engine.api import app
from intent_engine.api_v4 import get_v4_planning_service
from intent_engine.agentic.application import V4PlanningService, FixedStreamingDemoPolicyResolver, TrustedPlanningContext
from intent_engine.agentic.trace import canonical_execution_decision_json
from intent_engine.schemas import Item

NOW = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)
CANDIDATES = [
    {"item_id": "calm", "title": "Calm", "base_score": .8, "attributes": {"maturity": "kids", "calm_score": .9}},
    {"item_id": "active", "title": "Active", "base_score": .9, "attributes": {"maturity": "kids", "calm_score": .1}},
    {"item_id": "adult", "title": "Adult", "base_score": 100, "attributes": {"maturity": "adult", "calm_score": 1}},
]


@pytest.fixture
def harness():
    time = [NOW]
    service = V4PlanningService(clock=lambda: time[0])
    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_v4_planning_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as client:
        plan = client.post("/v4/plan", json={"text": "The kids are wired and bedtime is in an hour.", "domain": "streaming"}).json()
        yield client, service, time, plan
    app.dependency_overrides.clear()
    app.dependency_overrides.update(old)


def execute(harness, **updates):
    client, _, _, plan = harness
    body = {"plan_id": plan["plan_id"], "candidates": deepcopy(CANDIDATES)}
    body.update(updates)
    return client.post("/v4/execute", json=body)


@pytest.mark.parametrize("minutes,index", [(0, 0), (25, 1), (50, 2)])
def test_plan_execute_selects_steps_and_preserves_hard_gate(harness, minutes, index):
    _, _, time, plan = harness
    time[0] = NOW + timedelta(minutes=minutes)
    response = execute(harness)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["active_step"]["step_id"] == plan["steps"][index]["step_id"]
    adult = next(row for row in result["ranking"] if row["item"]["item_id"] == "adult")
    assert adult["status"] == "blocked"
    assert adult["final_score"] == 0
    assert adult["score_breakdown"]["blocked"]
    assert set(result) == {"trace_id", "active_step", "ranking", "explanation"}


def test_same_execution_decisions_with_distinct_trace_ids(harness):
    _, service, _, plan = harness
    candidates = [Item.model_validate(item) for item in CANDIDATES]
    first = service.execute_plan(plan_id=plan["plan_id"], candidates=candidates)
    second = service.execute_plan(plan_id=plan["plan_id"], candidates=candidates)
    assert first.trace_id != second.trace_id
    assert canonical_execution_decision_json(first) == canonical_execution_decision_json(second)
    assert first.intent_application.applied_hard_constraints == {"maturity_gate": "kids"}
    assert "tone" in first.intent_application.observational_signals
    assert "tone" not in first.intent_application.applied_intent


@pytest.mark.parametrize("field", ["plan", "profile", "constraints", "resolved_intent", "prepared_execution", "timestamp", "trace_id", "engine_version", "adapter_version"])
def test_client_cannot_supply_execution_authority(harness, field):
    assert execute(harness, **{field: {}}).status_code == 422


@pytest.mark.parametrize("candidates", [[], CANDIDATES * 40, [CANDIDATES[0], CANDIDATES[0]], [{"item_id": "a", "title": "A", "attributes": {}}]])
def test_invalid_candidate_collections(harness, candidates):
    assert execute(harness, candidates=candidates).status_code == 422


@pytest.mark.parametrize("field,value", [("unknown", 1), ("base_score", "NaN"), ("base_score", "Infinity"), ("item_id", "")])
def test_invalid_candidate_fields(harness, field, value):
    candidate = deepcopy(CANDIDATES[0])
    candidate[field] = value
    assert execute(harness, candidates=[candidate]).status_code == 422


@pytest.mark.parametrize("field,value", [("calm_score", 2), ("complexity", True), ("maturity", "unknown"), ("maturity", {}), ("maturity", [])])
def test_invalid_streaming_attributes(harness, field, value):
    candidate = deepcopy(CANDIDATES[0])
    candidate["attributes"][field] = value
    assert execute(harness, candidates=[candidate]).status_code == 422


def test_missing_foreign_and_expired_plans_are_indistinguishable(harness):
    _, service, time, _ = harness
    missing = execute(harness, plan_id="missing")
    service._policy_resolver = FixedStreamingDemoPolicyResolver(owner_id="other-owner")
    foreign = execute(harness)
    service._policy_resolver = FixedStreamingDemoPolicyResolver()
    time[0] = NOW + timedelta(minutes=60)
    expired = execute(harness)
    assert missing.status_code == foreign.status_code == expired.status_code == 404
    assert missing.json() == foreign.json() == expired.json()


def test_prestart_returns_conflict(harness):
    harness[2][0] = NOW - timedelta(seconds=1)
    assert execute(harness).status_code == 409


def test_policy_change_requires_new_plan(harness):
    class ChangedPolicy:
        def resolve(self, domain):
            original = FixedStreamingDemoPolicyResolver().resolve(domain)
            return TrustedPlanningContext(owner_id=original.owner_id, session_id="changed", active_profile_context=original.active_profile_context, authoritative_constraints=original.authoritative_constraints)
    harness[1]._policy_resolver = ChangedPolicy()
    response = execute(harness)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "policy_changed"


def test_unexpected_fault_has_generic_error(harness, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("secret")
    monkeypatch.setattr(harness[1], "execute_plan", fail)
    response = execute(harness)
    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json()["detail"]["code"] == "execution_failed"


def test_resolved_execution_bypasses_raw_intent_resolution(harness, monkeypatch):
    from intent_engine.adapters.streaming import StreamingAdapter
    def fail(*args, **kwargs):
        raise AssertionError("raw resolver called")
    monkeypatch.setattr(StreamingAdapter, "resolve_intent", fail)
    assert execute(harness).status_code == 200


def test_execute_requires_plan_and_candidates(harness):
    assert harness[0].post("/v4/execute", json={}).status_code == 422


def test_execution_ranking_matches_direct_resolved_engine(harness):
    from intent_engine.adapters.streaming import StreamingAdapter
    from intent_engine.core.domain_engine import DomainRankingEngine
    from intent_engine.agentic.orchestrator import IntentOrchestrator
    from intent_engine.schemas import Domain
    _, service, _, plan = harness
    record = service.registry.get(owner_id="public-streaming-demo", plan_id=plan["plan_id"], now=NOW)
    prepared = IntentOrchestrator().prepare_execution(record.plan, now=NOW, active_profile_context=record.active_profile_context, authoritative_constraints=record.authoritative_constraints)
    ranked = DomainRankingEngine({Domain.STREAMING: StreamingAdapter()}).rank_resolved(domain=Domain.STREAMING, resolved_intent=prepared.normalized_input.resolved_intent, constraints=prepared.normalized_input.hard_constraints, candidates=[Item.model_validate(item) for item in CANDIDATES])
    result = execute(harness).json()["ranking"]
    assert [(row["item"]["item_id"], row["final_score"], row["explanation"]) for row in result] == [(row.item.item_id, row.final_score, row.explanation) for row in ranked.ranked_items]
