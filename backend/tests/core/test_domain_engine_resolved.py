"""Phase 3C tests for already-resolved deterministic ranking."""

from collections.abc import Sequence
import inspect
from types import MappingProxyType

import pytest

from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.core.domain_engine import (
    DIVERSITY_PENALTY,
    DomainRankingEngine,
)
from intent_engine.schemas import (
    Domain,
    Intent,
    Item,
    MultiplierSet,
    RankingMode,
    RankingRequest,
    UserContext,
)


def _item(
    item_id,
    base_score,
    *,
    calm_score=0.5,
    maturity="family",
    genre="animation",
):
    return Item(
        item_id=item_id,
        title=item_id,
        base_score=base_score,
        attributes={
            "calm_score": calm_score,
            "maturity": maturity,
            "genre": genre,
        },
    )


class _TrackingStreamingAdapter(StreamingAdapter):
    def __init__(self, *, fail_on_resolve=False, mutate_inputs=False):
        self.fail_on_resolve = fail_on_resolve
        self.mutate_inputs = mutate_inputs
        self.resolve_calls = 0
        self.resolved_intents = []
        self.constraints = []
        self.last_resolved = None

    def resolve_intent(self, raw_input):
        self.resolve_calls += 1
        if self.fail_on_resolve:
            raise AssertionError("rank_resolved must not resolve intent again")
        resolved = super().resolve_intent(raw_input)
        self.last_resolved = dict(resolved)
        return resolved

    def compute_multipliers(self, item, intent):
        self.resolved_intents.append(dict(intent))
        if self.mutate_inputs:
            intent["adapter_mutation"] = item.item_id
        return super().compute_multipliers(item, intent)

    def apply_hard_constraints(self, item, constraints):
        self.constraints.append(dict(constraints))
        if self.mutate_inputs:
            constraints["adapter_mutation"] = item.item_id
        return super().apply_hard_constraints(item, constraints)


class _ConstantAdapter:
    @property
    def domain(self):
        return Domain.STREAMING

    def resolve_intent(self, raw_input):
        return dict(raw_input)

    def compute_multipliers(self, item, intent):
        return MultiplierSet(
            context=2.0,
            profile=0.5,
            urgency=1.5,
            cost=0.8,
            prophecy=1.25,
        )

    def apply_hard_constraints(self, item, constraints):
        return item.item_id in constraints.get("blocked_ids", ())

    def explain(self, item, multipliers):
        return f"explained:{item.item_id}"

    def diversity_key(self, item):
        return item.attributes.get("genre", "unknown")


class _DestructiveStreamingAdapter(StreamingAdapter):
    """Try to corrupt trusted input after each adapter call."""

    def __init__(self):
        self.gates_seen = []
        self.energies_seen = []

    def apply_hard_constraints(self, item, constraints):
        self.gates_seen.append(constraints.get("maturity_gate"))
        blocked = super().apply_hard_constraints(item, constraints)
        constraints["metadata"]["labels"].clear()
        constraints.clear()
        item.attributes["metadata"]["labels"].clear()
        item.attributes["adapter_mutation"] = "constraint"
        return blocked

    def compute_multipliers(self, item, intent):
        self.energies_seen.append(intent.get("energy_level"))
        multipliers = super().compute_multipliers(item, intent)
        intent["metadata"]["labels"].clear()
        intent.clear()
        item.attributes["metadata"]["labels"].clear()
        item.attributes["adapter_mutation"] = "multiplier"
        return multipliers

    def diversity_key(self, item):
        key = super().diversity_key(item)
        item.attributes["adapter_mutation"] = "diversity"
        return key

    def explain(self, item, multipliers):
        explanation = super().explain(item, multipliers)
        item.attributes["adapter_mutation"] = "explanation"
        multipliers.context = 999.0
        return explanation


class _ChangingCandidateSequence(Sequence):
    """Expose accidental double consumption of the caller's sequence."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)
        self.iterations = 0

    def __len__(self):
        return len(self.candidates)

    def __getitem__(self, index):
        return self.candidates[index]

    def __iter__(self):
        self.iterations += 1
        if self.iterations == 1:
            return iter(self.candidates)
        return iter(())


def _ranked_payload(response):
    return [item.model_dump(mode="json") for item in response.ranked_items]


class TestResolvedRankingBoundary:
    def test_resolved_intent_bypasses_adapter_resolution(self):
        adapter = _TrackingStreamingAdapter(fail_on_resolve=True)
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        resolved = MappingProxyType(
            {
                "energy_level": 0.2,
                "intent_type": "calm",
                "time_bucket": "bedtime",
                "viewer_profile": "family",
            }
        )

        response = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent=resolved,
            constraints=MappingProxyType({}),
            candidates=[_item("calm", 0.7, calm_score=1.0)],
        )

        assert adapter.resolve_calls == 0
        assert adapter.resolved_intents == [dict(resolved)]
        assert response.intent.intent_type == "calm"
        assert response.mode_used == RankingMode.ADVANCED
        assert response.latency.intent_parsing_ms == 0.0

    def test_explicit_planned_intent_type_is_honored(self):
        adapter = _TrackingStreamingAdapter(fail_on_resolve=True)
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        candidates = [
            _item("calm", 0.7, calm_score=1.0, genre="calm"),
            _item("stimulating", 0.7, calm_score=0.0, genre="action"),
        ]

        calm = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent={"intent_type": "calm", "energy_level": 0.5},
            constraints={},
            candidates=candidates,
        )
        popular = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent={"intent_type": "popular", "energy_level": 0.5},
            constraints={},
            candidates=candidates,
        )

        assert calm.ranked_items[0].item.item_id == "calm"
        assert popular.ranked_items[0].item.item_id == "stimulating"
        assert adapter.resolve_calls == 0

    def test_authoritative_hard_constraints_reach_gate_exactly(self):
        adapter = _TrackingStreamingAdapter(fail_on_resolve=True)
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        constraints = MappingProxyType({"maturity_gate": "kids"})

        response = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent={
                "intent_type": "popular",
                "viewer_profile": "kids",
            },
            constraints=constraints,
            candidates=[
                _item("adult", 1.0, maturity="adult"),
                _item("kids", 0.2, maturity="kids"),
            ],
        )

        adult = next(
            ranked
            for ranked in response.ranked_items
            if ranked.item.item_id == "adult"
        )
        assert adapter.constraints == [dict(constraints), dict(constraints)]
        assert adult.final_score == 0.0
        assert adult.status == "blocked"
        assert adult.score_breakdown.blocked is True
        assert adult.score_breakdown.block_reason == "Hard constraint violated"

    def test_inputs_are_snapshotted_once_and_callers_are_not_mutated(self):
        adapter = _TrackingStreamingAdapter(
            fail_on_resolve=True,
            mutate_inputs=True,
        )
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        resolved = {"intent_type": "calm", "energy_level": 0.2}
        constraints = {"maturity_gate": "kids"}
        candidates = _ChangingCandidateSequence(
            [_item("kids", 0.5, maturity="kids")]
        )

        engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent=resolved,
            constraints=constraints,
            candidates=candidates,
        )

        assert candidates.iterations == 1
        assert resolved == {"intent_type": "calm", "energy_level": 0.2}
        assert constraints == {"maturity_gate": "kids"}

    def test_adapter_mutation_cannot_drop_later_gate_or_escape_boundary(self):
        adapter = _DestructiveStreamingAdapter()
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        resolved = {
            "intent_type": "calm",
            "energy_level": 0.2,
            "metadata": {"labels": ["caller-owned"]},
        }
        constraints = {
            "maturity_gate": "kids",
            "metadata": {"labels": ["caller-owned"]},
        }
        candidates = [
            _item("kids", 0.2, maturity="kids"),
            _item("adult", 1.0, maturity="adult"),
        ]
        for candidate in candidates:
            candidate.attributes["metadata"] = {
                "labels": ["caller-owned"]
            }

        response = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent=resolved,
            constraints=constraints,
            candidates=candidates,
        )

        adult = next(
            ranked
            for ranked in response.ranked_items
            if ranked.item.item_id == "adult"
        )
        assert adapter.gates_seen == ["kids", "kids"]
        assert adapter.energies_seen == [0.2, 0.2]
        assert adult.status == "blocked"
        assert adult.score_breakdown.blocked is True
        assert resolved["metadata"]["labels"] == ["caller-owned"]
        assert constraints["metadata"]["labels"] == ["caller-owned"]
        assert all(
            "adapter_mutation" not in candidate.attributes
            for candidate in candidates
        )
        assert all(
            candidate.attributes["metadata"]["labels"] == ["caller-owned"]
            for candidate in candidates
        )
        assert all(
            "adapter_mutation" not in ranked.item.attributes
            for ranked in response.ranked_items
        )
        assert all(
            ranked.item.attributes["metadata"]["labels"] == ["caller-owned"]
            for ranked in response.ranked_items
        )
        assert all(
            ranked.score_breakdown.multipliers.context != 999.0
            for ranked in response.ranked_items
        )

    def test_boundary_accepts_only_execution_inputs(self):
        parameters = inspect.signature(
            DomainRankingEngine.rank_resolved
        ).parameters

        assert set(parameters) == {
            "self",
            "domain",
            "resolved_intent",
            "constraints",
            "candidates",
        }
        for forbidden in (
            "plan",
            "now",
            "profile",
            "goal",
            "observational_signals",
            "prophecy",
            "llm",
        ):
            assert forbidden not in parameters


class TestResolvedRankingParity:
    def test_legacy_rank_still_resolves_once_and_matches_shared_scoring(self):
        adapter = _TrackingStreamingAdapter()
        engine = DomainRankingEngine({Domain.STREAMING: adapter})
        candidates = [
            _item("calm", 0.7, calm_score=1.0, genre="calm"),
            _item("adult", 0.95, calm_score=0.4, maturity="adult"),
            _item("other", 0.6, calm_score=0.2, genre="calm"),
        ]
        request = RankingRequest(
            domain=Domain.STREAMING,
            mode=RankingMode.SIMPLE,
            items=candidates,
            user_context=UserContext(
                user_id="test",
                intent=Intent(intent_type="browse", keywords=["calm"]),
            ),
            constraints={"maturity_gate": "kids"},
        )

        legacy = engine.rank(request)
        resolved = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent=adapter.last_resolved,
            constraints=request.constraints,
            candidates=request.items,
        )

        assert adapter.resolve_calls == 1
        assert _ranked_payload(legacy) == _ranked_payload(resolved)
        assert legacy.intent is request.user_context.intent
        assert legacy.mode_used == RankingMode.SIMPLE
        assert resolved.mode_used == RankingMode.ADVANCED

    def test_multiplier_formula_blocking_explanation_and_breakdown_are_shared(self):
        engine = DomainRankingEngine({Domain.STREAMING: _ConstantAdapter()})

        response = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent={"intent_type": "calm"},
            constraints={"blocked_ids": ["blocked"]},
            candidates=[
                _item("allowed", 0.8, genre="one"),
                _item("blocked", 1.0, genre="two"),
            ],
        )

        allowed = next(
            ranked
            for ranked in response.ranked_items
            if ranked.item.item_id == "allowed"
        )
        blocked = next(
            ranked
            for ranked in response.ranked_items
            if ranked.item.item_id == "blocked"
        )
        assert allowed.final_score == pytest.approx(1.2)
        assert allowed.score_breakdown.final_score == pytest.approx(1.2)
        assert allowed.explanation == "explained:allowed"
        assert blocked.final_score == 0.0
        assert blocked.status == "blocked"
        assert blocked.score_breakdown.blocked is True
        assert blocked.explanation == "explained:blocked"

    def test_existing_global_diversity_count_and_stable_ties_are_preserved(self):
        engine = DomainRankingEngine({Domain.STREAMING: _ConstantAdapter()})
        multiplier_product = 2.0 * 0.5 * 1.5 * 0.8 * 1.25
        candidates = [
            _item("first-a", 0.9, genre="a"),
            _item("middle-b", 0.85, genre="b"),
            _item("later-a", 0.8, genre="a"),
            _item("tie-first", 0.4, genre="c"),
            _item("tie-second", 0.4, genre="d"),
        ]

        response = engine.rank_resolved(
            domain=Domain.STREAMING,
            resolved_intent={},
            constraints={},
            candidates=candidates,
        )
        ranked = {item.item.item_id: item for item in response.ranked_items}
        ids = [item.item.item_id for item in response.ranked_items]

        assert ranked["later-a"].score_breakdown.diversity_penalty == (
            DIVERSITY_PENALTY
        )
        assert ranked["later-a"].final_score == pytest.approx(
            0.8 * multiplier_product + DIVERSITY_PENALTY
        )
        assert ids.index("tie-first") < ids.index("tie-second")


class TestResolvedRankingFailures:
    @pytest.fixture
    def engine(self):
        return DomainRankingEngine({Domain.STREAMING: StreamingAdapter()})

    def test_unregistered_domain_fails(self):
        engine = DomainRankingEngine({})

        with pytest.raises(ValueError, match="No adapter registered"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    def test_registered_non_streaming_domain_is_not_enabled_implicitly(self):
        engine = DomainRankingEngine(
            {Domain.RIDE_MATCHING: _ConstantAdapter()}
        )

        with pytest.raises(ValueError, match="streaming domain only"):
            engine.rank_resolved(
                domain=Domain.RIDE_MATCHING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    def test_misregistered_adapter_domain_fails_closed(self):
        class WrongDomainAdapter(_ConstantAdapter):
            @property
            def domain(self):
                return Domain.RIDE_MATCHING

        engine = DomainRankingEngine(
            {Domain.STREAMING: WrongDomainAdapter()}
        )

        with pytest.raises(ValueError, match="does not match registration"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize("value", [None, "", "   ", 1, True])
    def test_invalid_intent_type_is_rejected_instead_of_misreported(
        self,
        engine,
        value,
    ):
        with pytest.raises(ValueError, match="nonblank string"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={"intent_type": value},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize("value", [None, [], "intent", 4])
    def test_resolved_intent_must_be_a_mapping(self, engine, value):
        with pytest.raises(TypeError, match="resolved_intent must be a mapping"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent=value,
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize("value", [None, [], "constraints", 4])
    def test_constraints_must_be_a_mapping(self, engine, value):
        with pytest.raises(TypeError, match="constraints must be a mapping"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints=value,
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize(
        "name,value",
        [
            ("resolved_intent", {1: "calm"}),
            ("constraints", {1: "kids"}),
        ],
    )
    def test_mapping_keys_must_be_strings(self, engine, name, value):
        arguments = {
            "domain": Domain.STREAMING,
            "resolved_intent": {},
            "constraints": {},
            "candidates": [_item("one", 0.5)],
        }
        arguments[name] = value

        with pytest.raises(TypeError, match=f"{name} keys must be strings"):
            engine.rank_resolved(**arguments)

    def test_cyclic_nested_input_fails_closed(self, engine):
        cycle = {}
        cycle["self"] = cycle

        with pytest.raises(TypeError, match="must not contain a cycle"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={"intent_type": "calm", "metadata": cycle},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize(
        "value,error",
        [
            (None, TypeError),
            ("items", TypeError),
            ((item for item in ()), TypeError),
            ([], ValueError),
            ([object()], TypeError),
        ],
    )
    def test_candidates_must_be_a_nonempty_item_sequence(
        self,
        engine,
        value,
        error,
    ):
        with pytest.raises(error):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=value,
            )

    def test_post_construction_candidate_mutation_fails_at_boundary(self, engine):
        candidate = _item("one", 0.5)
        candidate.attributes = None

        with pytest.raises(TypeError, match=r"candidates\[0\].*validation"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[candidate],
            )

    def test_non_boolean_hard_gate_result_fails_closed(self):
        class InvalidGateAdapter(_ConstantAdapter):
            def apply_hard_constraints(self, item, constraints):
                return 1

        engine = DomainRankingEngine(
            {Domain.STREAMING: InvalidGateAdapter()}
        )

        with pytest.raises(TypeError, match="must be a bool"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize(
        "value",
        [float("nan"), float("inf"), float("-inf"), -0.1],
        ids=["nan", "positive-infinity", "negative-infinity", "negative"],
    )
    def test_invalid_adapter_multiplier_fails_closed(self, value):
        class InvalidMultiplierAdapter(_ConstantAdapter):
            def compute_multipliers(self, item, intent):
                return MultiplierSet(context=value)

        engine = DomainRankingEngine(
            {Domain.STREAMING: InvalidMultiplierAdapter()}
        )

        with pytest.raises(TypeError, match="finite and nonnegative"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 0.5)],
            )

    @pytest.mark.parametrize("field", ["base_score", "price"])
    def test_nonfinite_candidate_numeric_field_fails_closed(self, engine, field):
        candidate = _item("one", 0.5)
        setattr(candidate, field, float("inf"))

        with pytest.raises(TypeError, match="failed Item validation"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[candidate],
            )

    def test_finite_multiplier_product_overflow_fails_closed(self):
        class OverflowAdapter(_ConstantAdapter):
            def compute_multipliers(self, item, intent):
                return MultiplierSet(context=1e308, profile=2.0)

        engine = DomainRankingEngine({Domain.STREAMING: OverflowAdapter()})

        with pytest.raises(ValueError, match="score must be finite"):
            engine.rank_resolved(
                domain=Domain.STREAMING,
                resolved_intent={},
                constraints={},
                candidates=[_item("one", 1.0)],
            )
