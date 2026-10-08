"""Phase 3C integration from deterministic planning through ranking."""

from datetime import datetime, timedelta, timezone

from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.agentic import (
    ConstraintSource,
    ContextInterpretation,
    IntentConstraint,
    IntentOrchestrator,
    RuleBasedIntentPlanner,
)
from intent_engine.core.domain_engine import DomainRankingEngine
from intent_engine.schemas import Domain, Item


NOW = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)


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


def _maturity_gate():
    return IntentConstraint(
        type="maturity_gate",
        value="kids",
        hard=True,
        source=ConstraintSource.SYSTEM,
    )


def _candidates():
    return [
        Item(
            item_id="calm-kids",
            title="Calm Kids Story",
            base_score=0.65,
            attributes={
                "calm_score": 1.0,
                "maturity": "kids",
                "genre": "stories",
            },
        ),
        Item(
            item_id="active-family",
            title="Active Family Show",
            base_score=0.8,
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
            attributes={
                "calm_score": 0.9,
                "maturity": "adult",
                "genre": "drama",
            },
        ),
    ]


def _ranked_payload(response):
    return [item.model_dump(mode="json") for item in response.ranked_items]


def _ranked_by_id(response):
    return {item.item.item_id: item for item in response.ranked_items}


class TestMultiStepDeterministicExecution:
    def test_wind_down_plan_executes_at_t0_t25_and_t50(self):
        gate = _maturity_gate()
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(),
            Domain.STREAMING,
            NOW,
            authoritative_constraints=(gate,),
        )
        orchestrator = IntentOrchestrator()
        engine = DomainRankingEngine({Domain.STREAMING: StreamingAdapter()})
        candidates = _candidates()

        executions = []
        for minutes in (0, 25, 50):
            prepared = orchestrator.prepare_execution(
                plan,
                now=NOW + timedelta(minutes=minutes),
                active_profile_context={"viewer": "kids"},
                authoritative_constraints=(gate,),
            )
            first = engine.rank_resolved(
                domain=prepared.domain,
                resolved_intent=prepared.normalized_input.resolved_intent,
                constraints=prepared.normalized_input.hard_constraints,
                candidates=candidates,
            )
            replay = engine.rank_resolved(
                domain=prepared.domain,
                resolved_intent=prepared.normalized_input.resolved_intent,
                constraints=prepared.normalized_input.hard_constraints,
                candidates=candidates,
            )

            assert _ranked_payload(first) == _ranked_payload(replay)
            assert dict(prepared.normalized_input.hard_constraints) == {
                "maturity_gate": "kids"
            }
            assert set(prepared.normalized_input.observational_signals) == {
                "runtime_preference",
                "tone",
            }
            assert "tone" not in prepared.normalized_input.resolved_intent
            assert (
                "runtime_preference"
                not in prepared.normalized_input.resolved_intent
            )

            adult = _ranked_by_id(first)["adult-high-base"]
            assert adult.final_score == 0.0
            assert adult.status == "blocked"
            assert adult.score_breakdown.blocked is True

            executions.append((prepared, first))

        assert [
            prepared.active_step.offset_minutes
            for prepared, _response in executions
        ] == [0, 25, 50]
        assert [
            prepared.normalized_input.resolved_intent["energy_level"]
            for prepared, _response in executions
        ] == [0.55, 0.30, 0.10]

        calm_scores = [
            _ranked_by_id(response)["calm-kids"].final_score
            for _prepared, response in executions
        ]
        assert calm_scores[2] > calm_scores[0]

    def test_same_plan_and_time_reproduce_the_same_prepared_and_ranked_state(self):
        gate = _maturity_gate()
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(),
            Domain.STREAMING,
            NOW,
            authoritative_constraints=(gate,),
        )
        orchestrator = IntentOrchestrator()
        engine = DomainRankingEngine({Domain.STREAMING: StreamingAdapter()})

        prepared_first = orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25),
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=(gate,),
        )
        prepared_replay = orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25),
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=(gate,),
        )
        ranked_first = engine.rank_resolved(
            domain=prepared_first.domain,
            resolved_intent=prepared_first.normalized_input.resolved_intent,
            constraints=prepared_first.normalized_input.hard_constraints,
            candidates=_candidates(),
        )
        ranked_replay = engine.rank_resolved(
            domain=prepared_replay.domain,
            resolved_intent=prepared_replay.normalized_input.resolved_intent,
            constraints=prepared_replay.normalized_input.hard_constraints,
            candidates=_candidates(),
        )

        assert prepared_first == prepared_replay
        assert _ranked_payload(ranked_first) == _ranked_payload(ranked_replay)
