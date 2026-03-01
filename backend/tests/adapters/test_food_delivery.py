"""Tests for the food delivery domain adapter."""

import pytest

from intent_engine.adapters.food_delivery import FoodDeliveryAdapter
from intent_engine.schemas import Domain, Item, MultiplierSet


def _food(prep_time=20, health_score=0.5, price_tier=2, cuisine="mexican",
          reorder_rate=0.3, base_score=0.7, allergens=None):
    attrs = {
        "prep_time_minutes": prep_time,
        "health_score": health_score,
        "price_tier": price_tier,
        "cuisine_type": cuisine,
        "reorder_rate": reorder_rate,
    }
    if allergens is not None:
        attrs["allergens"] = allergens
    return Item(
        item_id="food1",
        title="Test Dish",
        base_score=base_score,
        attributes=attrs,
    )


@pytest.fixture
def adapter():
    return FoodDeliveryAdapter()


class TestFoodDeliveryAdapter:
    def test_domain_property(self, adapter):
        assert adapter.domain == Domain.FOOD_DELIVERY

    # --- resolve_intent ---

    def test_resolve_comfort_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["comfort", "cozy"]})
        assert result["intent_type"] == "comfort"

    def test_resolve_healthy_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["healthy"]})
        assert result["intent_type"] == "healthy"

    def test_resolve_fast_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["quick"]})
        assert result["intent_type"] == "fast"

    def test_resolve_high_hunger_infers_fast(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "hunger_urgency": 0.9})
        assert result["intent_type"] == "fast"

    def test_resolve_high_health_priority(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "health_priority": 0.8})
        assert result["intent_type"] == "healthy"

    def test_resolve_late_night_comfort(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "time_bucket": "late_night"})
        assert result["intent_type"] == "comfort"

    # --- compute_multipliers ---

    def test_fast_intent_favors_low_prep(self, adapter):
        quick = _food(prep_time=10)
        slow = _food(prep_time=40)
        intent = {"intent_type": "fast", "hunger_urgency": 0.9, "price_sensitivity": 0.5,
                  "health_priority": 0.5, "time_bucket": "evening", "comfort_preference": 0.5}

        quick_m = adapter.compute_multipliers(quick, intent)
        slow_m = adapter.compute_multipliers(slow, intent)
        assert quick_m.urgency > slow_m.urgency

    def test_healthy_intent_favors_health_score(self, adapter):
        healthy = _food(health_score=0.9)
        unhealthy = _food(health_score=0.1)
        intent = {"intent_type": "healthy", "hunger_urgency": 0.5, "price_sensitivity": 0.5,
                  "health_priority": 0.8, "time_bucket": "morning", "comfort_preference": 0.5}

        h_m = adapter.compute_multipliers(healthy, intent)
        u_m = adapter.compute_multipliers(unhealthy, intent)
        assert h_m.profile > u_m.profile

    def test_price_sensitivity_penalizes_expensive(self, adapter):
        cheap = _food(price_tier=1)
        expensive = _food(price_tier=4)
        intent = {"intent_type": "unknown", "hunger_urgency": 0.5, "price_sensitivity": 0.9,
                  "health_priority": 0.5, "time_bucket": "evening", "comfort_preference": 0.5}

        cheap_m = adapter.compute_multipliers(cheap, intent)
        exp_m = adapter.compute_multipliers(expensive, intent)
        assert cheap_m.cost > exp_m.cost

    def test_habitual_boosts_reorder(self, adapter):
        frequent = _food(reorder_rate=0.8)
        intent = {"intent_type": "habitual", "hunger_urgency": 0.5, "price_sensitivity": 0.5,
                  "health_priority": 0.5, "time_bucket": "evening", "comfort_preference": 0.5}

        m = adapter.compute_multipliers(frequent, intent)
        assert m.prophecy > 1.0

    def test_discovery_penalizes_familiar(self, adapter):
        familiar = _food(reorder_rate=0.9)
        intent = {"intent_type": "discovery", "hunger_urgency": 0.5, "price_sensitivity": 0.5,
                  "health_priority": 0.5, "time_bucket": "evening", "comfort_preference": 0.5}

        m = adapter.compute_multipliers(familiar, intent)
        assert m.prophecy < 1.0

    # --- apply_hard_constraints ---

    def test_allergen_blocks(self, adapter):
        item = _food(allergens=["peanuts", "gluten"])
        assert adapter.apply_hard_constraints(item, {"allergens": ["peanuts"]}) is True

    def test_allergen_case_insensitive(self, adapter):
        item = _food(allergens=["Peanuts"])
        assert adapter.apply_hard_constraints(item, {"allergens": ["peanuts"]}) is True

    def test_allergen_passes(self, adapter):
        item = _food(allergens=["gluten"])
        assert adapter.apply_hard_constraints(item, {"allergens": ["peanuts"]}) is False

    def test_no_allergen_constraint_passes(self, adapter):
        item = _food(allergens=["peanuts"])
        assert adapter.apply_hard_constraints(item, {}) is False

    # --- diversity_key ---

    def test_diversity_key_uses_cuisine(self, adapter):
        item = _food(cuisine="thai")
        assert adapter.diversity_key(item) == "thai"
