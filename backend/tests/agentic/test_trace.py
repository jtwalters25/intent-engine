"""Phase 4 execution-trace construction and determinism tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.agentic import (
    ActivePlanStep,
    ConstraintSource,
    ContextInterpretation,
    ExecutionTrace,
    ExecutionTraceBuilder,
    GoalRequest,
    IntentConstraint,
    IntentOrchestrator,
    OutcomeEvent,
    RuleBasedIntentPlanner,
    TraceBuildError,
    TraceValidationStatus,
    canonical_execution_decision_json,
)
from intent_engine.core.domain_engine import DomainRankingEngine
from intent_engine.schemas import CandidateItem, Domain, Item


NOW = datetime(2026, 10, 8, 19, 0, tzinfo=timezone.utc)


def _maturity_gate():
    return IntentConstraint(
        type="maturity_gate",
        value="kids",
        hard=True,
        source=ConstraintSource.SYSTEM,
    )


def _goal_request():
    return GoalRequest(
        text="The kids are wired and bedtime is in an hour.",
        domain=Domain.STREAMING,
        timestamp=NOW,
        explicit_context={"viewer": "kids", "source": {"surface": "demo"}},
        session_id="session_trace",
    )


def _interpretation():
    return ContextInterpretation(
        objective="wind_down",
        entities={"viewer": "kids", "energy": 0.85},
        explicit_constraints=[],
        inferred_context={"horizon_minutes": 60},
        assumptions=[],
        missing_information=[],
        confidence=0.92,
    )


def _candidates():
    return [
        Item(
            item_id="calm-kids",
            title="Calm Kids Story",
            base_score=0.65,
            category="stories",
            price=2.5,
            popularity_score=0.74,
            quality_score=0.91,
            attributes={
                "calm_score": 1.0,
                "maturity": "kids",
                "genre": "stories",
                "provenance": {"catalog": "streaming-demo"},
            },
        ),
        Item(
            item_id="active-family",
            title="Active Family Show",
            base_score=0.8,
            category="adventure",
            price=4.0,
            popularity_score=0.83,
            quality_score=0.72,
            attributes={
                "calm_score": 0.05,
                "maturity": "family",
                "genre": "adventure",
            },
        ),
        Item(
            item_id="adult-high-base",
            title="Adult High Base",
            base_score=1.0,
            category="drama",
            price=8.0,
            popularity_score=0.97,
            quality_score=0.88,
            attributes={
                "calm_score": 0.9,
                "maturity": "adult",
                "genre": "drama",
            },
        ),
    ]


def _completed_execution():
    goal = _goal_request()
    interpretation = _interpretation()
    gate = _maturity_gate()
    plan = RuleBasedIntentPlanner().create_plan(
        interpretation,
        Domain.STREAMING,
        NOW,
        authoritative_constraints=(gate,),
    )
    prepared = IntentOrchestrator().prepare_execution(
        plan,
        now=NOW + timedelta(minutes=25),
        active_profile_context={"viewer": "kids"},
        authoritative_constraints=(gate,),
    )
    ranking_execution = DomainRankingEngine(
        {Domain.STREAMING: StreamingAdapter()}
    ).rank_resolved_execution(
        domain=prepared.domain,
        resolved_intent=prepared.normalized_input.resolved_intent,
        constraints=prepared.normalized_input.hard_constraints,
        candidates=_candidates(),
    )
    return {
        "goal_request": goal,
        "interpretation": interpretation,
        "plan": plan,
        "prepared_execution": prepared,
        "ranking_execution": ranking_execution,
    }


def _build(execution, *, trace_id="trace_one"):
    return ExecutionTraceBuilder().build(
        trace_id=trace_id,
        engine_version="domain-ranking-v3",
        adapter_version="streaming-v3",
        **execution,
    )


@pytest.fixture
def execution():
    return _completed_execution()


class TestExecutionTraceBuilder:
    def test_builds_complete_trace_from_real_execution(self, execution):
        trace = _build(execution)

        assert trace.trace_id == "trace_one"
        assert trace.goal_request == execution["goal_request"]
        assert trace.interpretation == execution["interpretation"]
        assert trace.plan == execution["plan"]
        assert trace.active_step.step_id == (
            execution["prepared_execution"].active_step.step_id
        )
        assert trace.active_step.offset_minutes == 25
        assert len(trace.validation_results) == 1
        validation = trace.validation_results[0]
        assert validation.stage == "plan_execution_boundary"
        assert validation.status == TraceValidationStatus.PASSED
        assert validation.evaluated_at == NOW + timedelta(minutes=25)
        assert validation.plan_id == trace.plan.plan_id
        assert trace.ranking_trace.domain == Domain.STREAMING
        assert trace.ranking_trace.intent_type == "calm"
        assert trace.outcome_events == []

    def test_records_applied_observational_and_hard_constraint_data_separately(
        self, execution
    ):
        trace = _build(execution)
        application = trace.intent_application

        assert application.canonical_intent == {
            "energy": 0.3,
            "intent_type": "calm",
            "runtime_preference": "short",
            "tone": "calm",
            "viewer": "kids",
        }
        assert application.applied_intent == {
            "energy_level": 0.3,
            "intent_type": "calm",
            "viewer_profile": "kids",
        }
        assert application.applied_hard_constraints == {
            "maturity_gate": "kids"
        }
        assert application.observational_signals == {
            "runtime_preference": "short",
            "tone": "calm",
        }
        assert set(application.applied_intent).isdisjoint(
            application.observational_signals
        )
        assert "tone" not in application.applied_intent
        assert "runtime_preference" not in application.applied_intent

    def test_blocking_is_generic_observed_evidence_not_causal_attribution(
        self, execution
    ):
        trace = _build(execution)
        candidates = {
            entry.item.item_id: entry
            for entry in trace.ranking_trace.ranked_candidates
        }
        safety = {
            decision.candidate_id: decision
            for decision in trace.safety_decisions
        }

        adult = candidates["adult-high-base"]
        adult_safety = safety["adult-high-base"]
        assert adult.status == "blocked"
        assert adult.final_score == 0.0
        assert adult.score_breakdown.blocked is True
        assert adult.score_breakdown.block_reason == "Hard constraint violated"
        assert adult_safety.blocked is True
        assert adult_safety.reason == "Hard constraint violated"
        assert set(adult_safety.model_dump()) == {
            "candidate_id",
            "rank",
            "blocked",
            "reason",
        }

        allowed = safety["calm-kids"]
        assert allowed.blocked is False
        assert allowed.reason is None

    def test_ranking_candidates_align_exactly_with_ranker_response(self, execution):
        trace = _build(execution)
        response = execution["ranking_execution"].response

        assert len(trace.ranking_trace.ranked_candidates) == len(
            response.ranked_items
        )
        for traced, ranked, safety in zip(
            trace.ranking_trace.ranked_candidates,
            response.ranked_items,
            trace.safety_decisions,
        ):
            assert traced.item.item_id == ranked.item.item_id
            assert traced.rank == ranked.rank
            assert traced.final_score == ranked.final_score
            assert traced.status.value == ranked.status
            assert traced.explanation == ranked.explanation
            assert traced.score_breakdown.final_score == (
                ranked.score_breakdown.final_score
            )
            assert traced.score_breakdown.multipliers.model_dump() == (
                ranked.score_breakdown.multipliers.model_dump()
            )
            assert safety.candidate_id == traced.item.item_id
            assert safety.rank == traced.rank
            assert safety.blocked == traced.score_breakdown.blocked
            assert safety.reason == traced.score_breakdown.block_reason

        assert [
            item.model_dump(mode="json")
            for item in trace.ranking_trace.input_candidates
        ] == [
            item.model_dump(mode="json")
            for item in execution["ranking_execution"].candidates
        ]

    def test_json_round_trip_retains_full_item_replay_fields(self, execution):
        trace = _build(execution)

        restored = ExecutionTrace.model_validate_json(trace.model_dump_json())
        calm = next(
            entry.item
            for entry in restored.ranking_trace.ranked_candidates
            if entry.item.item_id == "calm-kids"
        )

        assert restored == trace
        assert isinstance(calm, Item)
        assert calm.category == "stories"
        assert calm.price == 2.5
        assert calm.popularity_score == 0.74
        assert calm.quality_score == 0.91
        assert calm.attributes["provenance"] == {
            "catalog": "streaming-demo"
        }

    def test_builder_snapshots_inputs_from_later_caller_mutation(self, execution):
        trace = _build(execution)
        original = trace.model_dump(mode="json")

        execution["goal_request"].explicit_context["source"]["surface"] = "changed"
        execution["interpretation"].entities["energy"] = 0.0
        execution["plan"].current_state["energy"] = 0.0
        ranked = execution["ranking_execution"].response.ranked_items[0]
        ranked.item.attributes["maturity"] = "adult"
        ranked.explanation = "caller mutation"
        ranked.score_breakdown.multipliers.context = 999.0

        assert trace.model_dump(mode="json") == original

    def test_post_construction_invalid_contract_is_rejected(self, execution):
        execution["plan"].current_state["energy"] = float("nan")

        with pytest.raises(TraceBuildError) as exc_info:
            _build(execution)

        assert exc_info.value.code == "invalid_trace_input"
        assert exc_info.value.path == "plan"

    @pytest.mark.parametrize(
        ("field", "mutate"),
        [
            (
                "domain",
                lambda values: setattr(
                    values["ranking_execution"].response,
                    "domain",
                    Domain.RIDE_MATCHING,
                ),
            ),
            (
                "plan",
                lambda values: values.__setitem__(
                    "prepared_execution",
                    replace(values["prepared_execution"], plan_id="wrong-plan"),
                ),
            ),
            (
                "step",
                lambda values: values.__setitem__(
                    "prepared_execution",
                    replace(
                        values["prepared_execution"],
                        active_step=ActivePlanStep(
                            step_id="not-in-plan",
                            offset_minutes=25,
                            intent={"energy": 0.3},
                            transition_reason="Forged active step",
                        ),
                    ),
                ),
            ),
            (
                "intent",
                lambda values: setattr(
                    values["ranking_execution"].response.intent,
                    "intent_type",
                    "popular",
                ),
            ),
            (
                "rank",
                lambda values: setattr(
                    values["ranking_execution"].response.ranked_items[0],
                    "rank",
                    2,
                ),
            ),
            (
                "score",
                lambda values: setattr(
                    values["ranking_execution"].response.ranked_items[0],
                    "score",
                    values["ranking_execution"].response.ranked_items[0].score
                    + 0.01,
                ),
            ),
        ],
        ids=lambda value: value if isinstance(value, str) else None,
    )
    def test_rejects_cross_lifecycle_mismatches(self, execution, field, mutate):
        mutate(execution)

        with pytest.raises(TraceBuildError):
            _build(execution)

    @pytest.mark.parametrize(
        ("field", "replacement", "error_code"),
        [
            (
                "resolved_intent",
                {
                    "energy_level": 0.55,
                    "intent_type": "calm",
                    "viewer_profile": "kids",
                },
                "intent_mismatch",
            ),
            ("constraints", {}, "constraint_mismatch"),
        ],
    )
    def test_rejects_ranking_inputs_that_do_not_match_preparation(
        self,
        execution,
        field,
        replacement,
        error_code,
    ):
        execution["ranking_execution"] = replace(
            execution["ranking_execution"],
            **{field: replacement},
        )

        with pytest.raises(TraceBuildError) as exc_info:
            _build(execution)

        assert exc_info.value.code == error_code

    def test_rejects_internally_impossible_score_evidence(self, execution):
        ranked = execution["ranking_execution"].response.ranked_items[0]
        ranked.final_score = 123.0
        ranked.score = 123.0
        ranked.score_breakdown.final_score = 123.0
        ranked.status = "boosted"

        with pytest.raises(TraceBuildError) as exc_info:
            _build(execution)

        assert exc_info.value.code == "invalid_ranking_response"

    def test_rejects_response_that_is_not_in_descending_score_order(
        self, execution
    ):
        response = execution["ranking_execution"].response
        response.ranked_items.reverse()
        for rank, item in enumerate(response.ranked_items, start=1):
            item.rank = rank

        with pytest.raises(TraceBuildError) as exc_info:
            _build(execution)

        assert exc_info.value.code == "invalid_trace_evidence"

    def test_duplicate_candidate_ids_remain_traceable_end_to_end(self, execution):
        prepared = execution["prepared_execution"]
        duplicates = [_candidates()[0], _candidates()[0].model_copy(deep=True)]
        execution["ranking_execution"] = DomainRankingEngine(
            {Domain.STREAMING: StreamingAdapter()}
        ).rank_resolved_execution(
            domain=prepared.domain,
            resolved_intent=prepared.normalized_input.resolved_intent,
            constraints=prepared.normalized_input.hard_constraints,
            candidates=duplicates,
        )

        trace = _build(execution)

        assert [item.item.item_id for item in trace.ranking_trace.ranked_candidates] == [
            "calm-kids",
            "calm-kids",
        ]
        assert [(item.candidate_id, item.rank) for item in trace.safety_decisions] == [
            ("calm-kids", 1),
            ("calm-kids", 2),
        ]

    def test_rejects_candidate_that_lost_full_item_contract(self, execution):
        ranked = execution["ranking_execution"].response.ranked_items[0]
        ranked.item = CandidateItem(
            item_id=ranked.item.item_id,
            title=ranked.item.title,
            attributes=ranked.item.attributes,
            base_score=ranked.item.base_score,
        )

        with pytest.raises(TraceBuildError) as exc_info:
            _build(execution)

        assert exc_info.value.code == "untraceable_candidate"

    @pytest.mark.parametrize(
        ("keyword", "value"),
        [
            ("trace_id", "   "),
            ("engine_version", ""),
            ("adapter_version", 7),
        ],
    )
    def test_rejects_invalid_trace_metadata(self, execution, keyword, value):
        arguments = {
            "trace_id": "trace_one",
            "engine_version": "domain-ranking-v3",
            "adapter_version": "streaming-v3",
            **execution,
        }
        arguments[keyword] = value

        with pytest.raises(TraceBuildError):
            ExecutionTraceBuilder().build(**arguments)


class TestCanonicalExecutionDecision:
    def test_equivalent_mapping_insertion_order_is_canonical(self, execution):
        first = _build(execution)
        reordered = first.model_copy(deep=True)
        reordered.intent_application.canonical_intent = dict(
            reversed(list(reordered.intent_application.canonical_intent.items()))
        )

        assert canonical_execution_decision_json(first) == (
            canonical_execution_decision_json(reordered)
        )

    def test_excludes_trace_id_latency_and_outcomes(self, execution):
        first = _build(execution, trace_id="trace_one")
        first_payload = json.loads(canonical_execution_decision_json(first))

        replay_execution = _completed_execution()
        replay_execution["ranking_execution"].response.latency.total_ms = 999.0
        replay_execution["ranking_execution"].response.latency.ranking_ms = 998.0
        replay = _build(replay_execution, trace_id="trace_two")
        replay.outcome_events = [
            OutcomeEvent(
                event_type="CONTENT_STARTED",
                timestamp=NOW + timedelta(minutes=26),
                plan_id=replay.plan.plan_id,
                step_id=replay.active_step.step_id,
                metadata={"candidate_id": "calm-kids"},
            )
        ]

        assert "trace_id" not in first_payload
        assert "latency" not in first_payload
        assert "outcome_events" not in first_payload
        assert canonical_execution_decision_json(first) == (
            canonical_execution_decision_json(replay)
        )

    def test_canonical_helper_revalidates_mutated_trace(self, execution):
        trace = _build(execution)
        trace.ranking_trace.ranked_candidates[0].item.attributes["bad"] = float(
            "nan"
        )

        with pytest.raises(TraceBuildError) as exc_info:
            canonical_execution_decision_json(trace)

        assert exc_info.value.code == "invalid_trace_input"
        assert exc_info.value.path == "trace"
