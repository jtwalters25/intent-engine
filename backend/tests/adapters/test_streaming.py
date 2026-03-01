"""Tests for the streaming domain adapter."""

import pytest

from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.schemas import Domain, Item, MultiplierSet, StreamingIntent


def _item(calm_score=0.5, maturity="family", genre="animation", base_score=0.7):
    return Item(
        item_id="test",
        title="Test Show",
        base_score=base_score,
        attributes={
            "calm_score": calm_score,
            "maturity": maturity,
            "genre": genre,
            "complexity": 0.5,
        },
    )


@pytest.fixture
def adapter():
    return StreamingAdapter()


class TestStreamingAdapter:
    def test_domain_property(self, adapter):
        assert adapter.domain == Domain.STREAMING

    # --- resolve_intent ---

    def test_resolve_calm_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["bedtime", "calm"]})
        assert result["intent_type"] == "calm"

    def test_resolve_educational_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["learning", "science"]})
        assert result["intent_type"] == "educational"

    def test_resolve_popular_keyword(self, adapter):
        result = adapter.resolve_intent({"keywords": ["trending"]})
        assert result["intent_type"] == "popular"

    def test_resolve_from_intent_text(self, adapter):
        result = adapter.resolve_intent({"intent_text": "something calm for bedtime"})
        assert result["intent_type"] == "calm"

    def test_resolve_unknown_defaults_from_time(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "time_bucket": "bedtime"})
        assert result["intent_type"] == "calm"

    def test_resolve_unknown_with_low_energy(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "energy_level": 0.1})
        assert result["intent_type"] == "calm"

    def test_resolve_unknown_neutral(self, adapter):
        result = adapter.resolve_intent({"keywords": [], "energy_level": 0.5, "time_bucket": "afternoon"})
        assert result["intent_type"] == "unknown"

    # --- compute_multipliers ---

    def test_calm_intent_boosts_calm_items(self, adapter):
        calm_item = _item(calm_score=0.9)
        active_item = _item(calm_score=0.1)
        intent = {"intent_type": "calm", "energy_level": 0.2, "time_bucket": "bedtime", "viewer_profile": "family"}

        calm_mults = adapter.compute_multipliers(calm_item, intent)
        active_mults = adapter.compute_multipliers(active_item, intent)

        # Calm item should get higher multipliers overall
        calm_product = calm_mults.context * calm_mults.urgency * calm_mults.prophecy
        active_product = active_mults.context * active_mults.urgency * active_mults.prophecy
        assert calm_product > active_product

    def test_kids_profile_blocks_adult(self, adapter):
        adult_item = _item(maturity="adult")
        intent = {"intent_type": "unknown", "energy_level": 0.5, "time_bucket": "afternoon", "viewer_profile": "kids"}
        mults = adapter.compute_multipliers(adult_item, intent)
        assert mults.profile == 0.0

    def test_kids_profile_boosts_kids_content(self, adapter):
        kids_item = _item(maturity="kids")
        intent = {"intent_type": "unknown", "energy_level": 0.5, "time_bucket": "afternoon", "viewer_profile": "kids"}
        mults = adapter.compute_multipliers(kids_item, intent)
        assert mults.profile > 1.0

    def test_cost_always_one(self, adapter):
        item = _item()
        intent = {"intent_type": "calm", "energy_level": 0.5, "time_bucket": "afternoon", "viewer_profile": "family"}
        mults = adapter.compute_multipliers(item, intent)
        assert mults.cost == 1.0

    # --- apply_hard_constraints ---

    def test_maturity_gate_blocks_adult(self, adapter):
        adult_item = _item(maturity="adult")
        assert adapter.apply_hard_constraints(adult_item, {"maturity_gate": "kids"}) is True

    def test_maturity_gate_passes_kids(self, adapter):
        kids_item = _item(maturity="kids")
        assert adapter.apply_hard_constraints(kids_item, {"maturity_gate": "kids"}) is False

    def test_no_constraint_passes(self, adapter):
        adult_item = _item(maturity="adult")
        assert adapter.apply_hard_constraints(adult_item, {}) is False

    # --- explain ---

    def test_explain_blocked(self, adapter):
        item = _item(maturity="adult")
        mults = MultiplierSet(profile=0.0)
        explanation = adapter.explain(item, mults)
        assert "blocked" in explanation.lower()

    def test_explain_neutral(self, adapter):
        item = _item()
        mults = MultiplierSet()
        explanation = adapter.explain(item, mults)
        assert item.title in explanation

    # --- diversity_key ---

    def test_diversity_key_uses_genre(self, adapter):
        item = _item(genre="comedy")
        assert adapter.diversity_key(item) == "comedy"
