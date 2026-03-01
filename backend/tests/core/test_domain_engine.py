"""Tests for the domain-agnostic DomainRankingEngine."""

import pytest

from intent_engine.core.domain_engine import DomainRankingEngine, DIVERSITY_PENALTY
from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.adapters.ride_matching import RideMatchingAdapter
from intent_engine.adapters.food_delivery import FoodDeliveryAdapter
from intent_engine.schemas import (
    Domain,
    Intent,
    Item,
    RankingMode,
    RankingRequest,
    UserContext,
)


def _make_request(domain, items, intent_type="browse", constraints=None, intent_text=None):
    return RankingRequest(
        domain=domain,
        items=items,
        user_context=UserContext(
            user_id="test",
            intent=Intent(intent_type=intent_type),
        ),
        constraints=constraints or {},
        intent_text=intent_text,
    )


def _streaming_item(item_id, title, base_score, calm_score=0.5, maturity="family", genre="animation"):
    return Item(
        item_id=item_id,
        title=title,
        base_score=base_score,
        attributes={"calm_score": calm_score, "maturity": maturity, "genre": genre},
    )


def _ride_item(item_id, title, base_score, eta=5, price_mult=1.0, comfort=0.5, ride_type="standard"):
    return Item(
        item_id=item_id,
        title=title,
        base_score=base_score,
        attributes={
            "eta_minutes": eta,
            "price_multiplier": price_mult,
            "comfort_score": comfort,
            "ride_type": ride_type,
        },
    )


@pytest.fixture
def engine():
    return DomainRankingEngine({
        Domain.STREAMING: StreamingAdapter(),
        Domain.RIDE_MATCHING: RideMatchingAdapter(),
        Domain.FOOD_DELIVERY: FoodDeliveryAdapter(),
    })


class TestDomainEngine:
    def test_registered_domains(self, engine):
        assert set(engine.registered_domains) == {
            Domain.STREAMING,
            Domain.RIDE_MATCHING,
            Domain.FOOD_DELIVERY,
        }

    def test_raises_for_unregistered_domain(self):
        engine = DomainRankingEngine({})
        req = _make_request(Domain.STREAMING, [_streaming_item("1", "A", 0.5)])
        with pytest.raises(ValueError, match="No adapter registered"):
            engine.rank(req)

    def test_raises_for_none_domain(self):
        engine = DomainRankingEngine({Domain.STREAMING: StreamingAdapter()})
        req = _make_request(None, [_streaming_item("1", "A", 0.5)])
        with pytest.raises(ValueError):
            engine.rank(req)

    def test_returns_all_items(self, engine):
        items = [_streaming_item(str(i), f"Item {i}", 0.5) for i in range(5)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        assert len(resp.ranked_items) == 5

    def test_items_sorted_by_final_score_desc(self, engine):
        items = [
            _streaming_item("a", "Low", 0.2),
            _streaming_item("b", "High", 0.9),
            _streaming_item("c", "Mid", 0.5),
        ]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        scores = [ri.final_score for ri in resp.ranked_items]
        assert scores == sorted(scores, reverse=True)

    def test_rank_positions_assigned(self, engine):
        items = [_streaming_item(str(i), f"Item {i}", 0.5 + i * 0.1) for i in range(3)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        ranks = [ri.rank for ri in resp.ranked_items]
        assert ranks == [1, 2, 3]

    def test_score_breakdown_present(self, engine):
        items = [_streaming_item("1", "Test", 0.7)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        breakdown = resp.ranked_items[0].score_breakdown
        assert breakdown is not None
        assert breakdown.base_score == 0.7
        assert breakdown.multipliers is not None

    def test_latency_tracked(self, engine):
        items = [_streaming_item("1", "Test", 0.5)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        assert resp.latency.total_ms > 0
        assert resp.latency.intent_parsing_ms >= 0
        assert resp.latency.ranking_ms >= 0

    def test_response_includes_domain(self, engine):
        items = [_streaming_item("1", "Test", 0.5)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        assert resp.domain == Domain.STREAMING

    def test_diversity_penalty_applied(self, engine):
        # 3 items same genre — 2nd and 3rd should get penalties
        items = [
            _streaming_item("a", "A", 0.8, genre="drama"),
            _streaming_item("b", "B", 0.7, genre="drama"),
            _streaming_item("c", "C", 0.6, genre="drama"),
        ]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        breakdowns = [ri.score_breakdown for ri in resp.ranked_items]
        # At least one item should have a negative diversity penalty
        penalties = [b.diversity_penalty for b in breakdowns if b and not b.blocked]
        assert any(p < 0 for p in penalties)

    def test_blocked_item_scores_zero(self, engine):
        items = [
            _streaming_item("1", "Adult Show", 0.9, maturity="adult"),
        ]
        resp = engine.rank(_make_request(
            Domain.STREAMING, items, constraints={"maturity_gate": "kids"}
        ))
        assert resp.ranked_items[0].final_score == 0.0
        assert resp.ranked_items[0].status == "blocked"
        assert resp.ranked_items[0].score_breakdown.blocked is True

    def test_explanation_present(self, engine):
        items = [_streaming_item("1", "Test", 0.5)]
        resp = engine.rank(_make_request(Domain.STREAMING, items))
        assert resp.ranked_items[0].explanation != ""
