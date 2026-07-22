"""Tests for the e-commerce domain adapter."""

import pytest

from intent_engine.adapters.ecommerce import EcommerceAdapter
from intent_engine.schemas import Domain, Item


def _product(maturity="family", price_tier=2, quality_score=0.5, gift_score=0.5,
             popularity=None, category="general", base_score=0.7):
    attrs = {
        "maturity": maturity,
        "price_tier": price_tier,
        "quality_score": quality_score,
        "gift_score": gift_score,
        "category_type": category,
    }
    if popularity is not None:
        attrs["popularity"] = popularity
    return Item(
        item_id="prod1",
        title="Test Product",
        base_score=base_score,
        attributes=attrs,
    )


@pytest.fixture
def adapter():
    return EcommerceAdapter()


def _intent(intent_type="unknown", price_sensitivity=0.5, quality_priority=0.5,
            shopper_profile="adult"):
    return {
        "intent_type": intent_type,
        "price_sensitivity": price_sensitivity,
        "quality_priority": quality_priority,
        "shopper_profile": shopper_profile,
    }


class TestEcommerceAdapter:
    def test_domain_property(self, adapter):
        assert adapter.domain == Domain.ECOMMERCE

    # --- resolve_intent ---

    def test_resolve_gift_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["gift", "present"]})["intent_type"] == "gift"

    def test_resolve_budget_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["affordable"]})["intent_type"] == "budget"

    def test_resolve_premium_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["luxury"]})["intent_type"] == "premium"

    def test_resolve_practical_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["everyday"]})["intent_type"] == "practical"

    def test_resolve_high_price_sensitivity_infers_budget(self, adapter):
        assert adapter.resolve_intent({"keywords": [], "price_sensitivity": 0.9})["intent_type"] == "budget"

    def test_resolve_high_quality_priority_infers_premium(self, adapter):
        assert adapter.resolve_intent({"keywords": [], "quality_priority": 0.9})["intent_type"] == "premium"

    # --- compute_multipliers ---

    def test_premium_intent_favors_quality(self, adapter):
        good = _product(quality_score=0.9)
        poor = _product(quality_score=0.1)
        intent = _intent("premium", quality_priority=0.8)
        assert adapter.compute_multipliers(good, intent).urgency > \
            adapter.compute_multipliers(poor, intent).urgency

    def test_price_sensitivity_penalizes_expensive(self, adapter):
        cheap = _product(price_tier=1)
        expensive = _product(price_tier=4)
        intent = _intent(price_sensitivity=0.9)
        assert adapter.compute_multipliers(cheap, intent).cost > \
            adapter.compute_multipliers(expensive, intent).cost

    def test_budget_intent_penalizes_expensive_even_without_sensitivity(self, adapter):
        expensive = _product(price_tier=4)
        m = adapter.compute_multipliers(expensive, _intent("budget", price_sensitivity=0.2))
        assert m.cost < 1.0

    def test_gift_intent_boosts_context_and_prophecy(self, adapter):
        giftable = _product(gift_score=0.9)
        m = adapter.compute_multipliers(giftable, _intent("gift"))
        assert m.context > 1.0
        assert m.prophecy > 1.0

    def test_discovery_penalizes_popular(self, adapter):
        popular = _product(popularity=0.9)
        m = adapter.compute_multipliers(popular, _intent("discovery"))
        assert m.prophecy < 1.0

    def test_kids_shopper_blocks_adult_via_multiplier(self, adapter):
        adult = _product(maturity="adult")
        m = adapter.compute_multipliers(adult, _intent(shopper_profile="kids"))
        assert m.profile == 0.0

    def test_kids_shopper_boosts_kids_item(self, adapter):
        kids = _product(maturity="kids")
        m = adapter.compute_multipliers(kids, _intent(shopper_profile="kids"))
        assert m.profile > 1.0

    # --- apply_hard_constraints ---

    def test_maturity_gate_blocks_adult(self, adapter):
        assert adapter.apply_hard_constraints(_product(maturity="adult"), {"maturity_gate": "kids"}) is True

    def test_maturity_gate_passes_family(self, adapter):
        assert adapter.apply_hard_constraints(_product(maturity="family"), {"maturity_gate": "kids"}) is False

    def test_no_constraint_passes(self, adapter):
        assert adapter.apply_hard_constraints(_product(maturity="adult"), {}) is False

    # --- diversity_key ---

    def test_diversity_key_uses_category(self, adapter):
        assert adapter.diversity_key(_product(category="electronics")) == "electronics"
