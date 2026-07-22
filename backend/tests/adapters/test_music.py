"""Tests for the music domain adapter."""

import pytest

from intent_engine.adapters.music import MusicAdapter
from intent_engine.schemas import Domain, Item


def _track(calm_score=0.5, energy=None, focus_friendly=0.5, maturity="family",
           genre="pop", base_score=0.7, explicit=None):
    attrs = {
        "calm_score": calm_score,
        "focus_friendly": focus_friendly,
        "maturity": maturity,
        "genre": genre,
    }
    if energy is not None:
        attrs["energy"] = energy
    if explicit is not None:
        attrs["explicit"] = explicit
    return Item(
        item_id="track1",
        title="Test Track",
        base_score=base_score,
        attributes=attrs,
    )


@pytest.fixture
def adapter():
    return MusicAdapter()


def _intent(intent_type="unknown", energy_level=0.5, time_bucket="afternoon",
            listener_profile="family"):
    return {
        "intent_type": intent_type,
        "energy_level": energy_level,
        "time_bucket": time_bucket,
        "listener_profile": listener_profile,
    }


class TestMusicAdapter:
    def test_domain_property(self, adapter):
        assert adapter.domain == Domain.MUSIC

    # --- resolve_intent ---

    def test_resolve_focus_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["focus", "study"]})["intent_type"] == "focus"

    def test_resolve_calm_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["relax"]})["intent_type"] == "calm"

    def test_resolve_upbeat_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["workout"]})["intent_type"] == "upbeat"

    def test_resolve_discovery_keyword(self, adapter):
        assert adapter.resolve_intent({"keywords": ["discover"]})["intent_type"] == "discovery"

    def test_resolve_late_night_infers_calm(self, adapter):
        assert adapter.resolve_intent({"keywords": [], "time_bucket": "late_night"})["intent_type"] == "calm"

    def test_resolve_high_energy_infers_upbeat(self, adapter):
        assert adapter.resolve_intent({"keywords": [], "energy_level": 0.9})["intent_type"] == "upbeat"

    def test_resolve_low_energy_infers_calm(self, adapter):
        assert adapter.resolve_intent({"keywords": [], "energy_level": 0.1})["intent_type"] == "calm"

    # --- compute_multipliers ---

    def test_calm_intent_favors_calm_score(self, adapter):
        calm = _track(calm_score=0.9)
        loud = _track(calm_score=0.1)
        intent = _intent("calm")
        assert adapter.compute_multipliers(calm, intent).urgency > \
            adapter.compute_multipliers(loud, intent).urgency

    def test_upbeat_intent_favors_energy(self, adapter):
        high = _track(calm_score=0.1, energy=0.9)
        low = _track(calm_score=0.9, energy=0.1)
        intent = _intent("upbeat", energy_level=0.9)
        assert adapter.compute_multipliers(high, intent).urgency > \
            adapter.compute_multipliers(low, intent).urgency

    def test_focus_intent_favors_focus_friendly(self, adapter):
        friendly = _track(focus_friendly=0.9)
        distracting = _track(focus_friendly=0.1)
        intent = _intent("focus")
        assert adapter.compute_multipliers(friendly, intent).urgency > \
            adapter.compute_multipliers(distracting, intent).urgency

    def test_bedtime_context_boosts_calm(self, adapter):
        calm = _track(calm_score=0.9)
        loud = _track(calm_score=0.1)
        intent = _intent("calm", time_bucket="bedtime")
        assert adapter.compute_multipliers(calm, intent).context > \
            adapter.compute_multipliers(loud, intent).context

    def test_kids_profile_blocks_adult_via_multiplier(self, adapter):
        adult = _track(maturity="adult")
        m = adapter.compute_multipliers(adult, _intent(listener_profile="kids"))
        assert m.profile == 0.0

    def test_kids_profile_boosts_kids_content(self, adapter):
        kids = _track(maturity="kids")
        m = adapter.compute_multipliers(kids, _intent(listener_profile="kids"))
        assert m.profile > 1.0

    # --- apply_hard_constraints ---

    def test_maturity_gate_blocks_adult(self, adapter):
        assert adapter.apply_hard_constraints(_track(maturity="adult"), {"maturity_gate": "kids"}) is True

    def test_maturity_gate_passes_family(self, adapter):
        assert adapter.apply_hard_constraints(_track(maturity="family"), {"maturity_gate": "kids"}) is False

    def test_block_explicit_blocks(self, adapter):
        assert adapter.apply_hard_constraints(_track(explicit=True), {"block_explicit": True}) is True

    def test_no_constraint_passes(self, adapter):
        assert adapter.apply_hard_constraints(_track(maturity="adult"), {}) is False

    # --- diversity_key ---

    def test_diversity_key_uses_genre(self, adapter):
        assert adapter.diversity_key(_track(genre="jazz")) == "jazz"
