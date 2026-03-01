"""Tests for the ride matching domain adapter."""

import pytest

from intent_engine.adapters.ride_matching import RideMatchingAdapter
from intent_engine.schemas import Domain, Item, MultiplierSet


def _ride(eta=5, price_mult=1.0, comfort=0.5, ride_type="standard", base_score=0.7):
    return Item(
        item_id="ride1",
        title="Test Ride",
        base_score=base_score,
        attributes={
            "eta_minutes": eta,
            "price_multiplier": price_mult,
            "comfort_score": comfort,
            "ride_type": ride_type,
        },
    )


@pytest.fixture
def adapter():
    return RideMatchingAdapter()


class TestRideMatchingAdapter:
    def test_domain_property(self, adapter):
        assert adapter.domain == Domain.RIDE_MATCHING

    # --- resolve_intent ---

    def test_resolve_budget_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["cheap", "pool"]})
        assert result["intent_type"] == "budget"

    def test_resolve_premium_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["luxury"]})
        assert result["intent_type"] == "premium"

    def test_resolve_urgent_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["asap"]})
        assert result["intent_type"] == "urgent"

    def test_resolve_commute_time_infers_habitual(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "time_bucket": "morning_commute"})
        assert result["intent_type"] == "habitual"

    def test_high_urgency_overrides(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "urgency": 0.9})
        assert result["intent_type"] == "urgent"

    # --- compute_multipliers ---

    def test_commute_favors_low_eta(self, adapter):
        fast = _ride(eta=3)
        slow = _ride(eta=15)
        intent = {"intent_type": "habitual", "urgency": 0.5, "surge_sensitivity": 0.5,
                  "time_bucket": "morning_commute", "comfort_preference": 0.5}

        fast_m = adapter.compute_multipliers(fast, intent)
        slow_m = adapter.compute_multipliers(slow, intent)
        assert fast_m.context > slow_m.context

    def test_budget_penalizes_premium(self, adapter):
        cheap = _ride(price_mult=1.0)
        expensive = _ride(price_mult=2.5)
        intent = {"intent_type": "budget", "urgency": 0.5, "surge_sensitivity": 0.5,
                  "time_bucket": "afternoon", "comfort_preference": 0.5}

        cheap_m = adapter.compute_multipliers(cheap, intent)
        exp_m = adapter.compute_multipliers(expensive, intent)
        assert cheap_m.profile > exp_m.profile

    def test_urgent_favors_fast_eta(self, adapter):
        fast = _ride(eta=3)
        slow = _ride(eta=15)
        intent = {"intent_type": "urgent", "urgency": 0.9, "surge_sensitivity": 0.3,
                  "time_bucket": "afternoon", "comfort_preference": 0.5}

        fast_m = adapter.compute_multipliers(fast, intent)
        slow_m = adapter.compute_multipliers(slow, intent)
        assert fast_m.urgency > slow_m.urgency

    def test_surge_sensitivity_penalizes_high_price(self, adapter):
        surge = _ride(price_mult=2.5)
        intent = {"intent_type": "comfort", "urgency": 0.5, "surge_sensitivity": 0.9,
                  "time_bucket": "afternoon", "comfort_preference": 0.5}

        m = adapter.compute_multipliers(surge, intent)
        assert m.cost < 1.0

    # --- apply_hard_constraints ---

    def test_surge_cap_blocks(self, adapter):
        ride = _ride(price_mult=2.5)
        assert adapter.apply_hard_constraints(ride, {"surge_cap": 2.0}) is True

    def test_surge_cap_passes(self, adapter):
        ride = _ride(price_mult=1.5)
        assert adapter.apply_hard_constraints(ride, {"surge_cap": 2.0}) is False

    def test_no_constraint_passes(self, adapter):
        ride = _ride(price_mult=3.0)
        assert adapter.apply_hard_constraints(ride, {}) is False

    # --- diversity_key ---

    def test_diversity_key_uses_ride_type(self, adapter):
        ride = _ride(ride_type="pool")
        assert adapter.diversity_key(ride) == "pool"
