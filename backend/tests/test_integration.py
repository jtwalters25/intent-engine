"""End-to-end integration test through the /rank endpoint.

Exercises both simple and advanced modes with realistic payloads and
verifies response structure, explanations, latency, and ordering changes.
"""

import pytest
from fastapi.testclient import TestClient
from intent_engine.api import app

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ITEMS = [
    {
        "item_id": "calm1",
        "title": "Goodnight Moon Lullaby",
        "category": "stories",
        "price": 0.0,
        "popularity_score": 0.6,
        "quality_score": 0.7,
        "attributes": {
            "category": "stories",
            "mood": "calm",
            "tags": ["sleep", "lullaby", "gentle", "bedtime"],
        },
        "base_score": 0.80,
    },
    {
        "item_id": "stem1",
        "title": "Rocket Science Experiments",
        "category": "stem",
        "price": 0.0,
        "popularity_score": 0.8,
        "quality_score": 0.85,
        "attributes": {
            "category": "stem",
            "mood": "energetic",
            "tags": ["science", "experiment", "space"],
        },
        "base_score": 0.85,
    },
    {
        "item_id": "fun1",
        "title": "Silly Dance Party",
        "category": "music",
        "price": 0.0,
        "popularity_score": 0.7,
        "quality_score": 0.6,
        "attributes": {
            "category": "music",
            "mood": "fun",
            "tags": ["games", "playful", "dance", "active"],
        },
        "base_score": 0.75,
    },
]


def _post_rank(client, *, mode="advanced", intent_text=None):
    """Helper to POST /rank with the shared item set."""
    return client.post("/rank", json={
        "items": ITEMS,
        "user_context": {"user_id": "integration_user"},
        "intent_text": intent_text,
        "use_llm": False,
        "mode": mode,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Single end-to-end integration test class."""

    def setup_method(self):
        self.client = TestClient(app)

    # -- response structure --------------------------------------------------

    def test_advanced_mode_returns_all_items_with_latency(self):
        """Advanced mode: all items returned, latency populated, intent present."""
        resp = _post_rank(self.client, mode="advanced", intent_text="show me popular items")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["ranked_items"]) == len(ITEMS)
        assert data["latency"]["total_ms"] > 0
        assert data["latency"]["intent_parsing_ms"] >= 0
        assert "intent" in data

    def test_simple_mode_returns_all_items_with_explanations(self):
        """Simple mode: all items survive (soft constraint), explanations present."""
        resp = _post_rank(self.client, mode="simple", intent_text="bedtime calm")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["ranked_items"]) == len(ITEMS)

        # Every item must have at least 2 explanation lines
        for ri in data["ranked_items"]:
            assert len(ri["explanations"]) >= 2

    # -- ordering changes with intent ----------------------------------------

    def test_bedtime_vs_weekend_ordering_differs(self):
        """Different intents must produce different top-ranked items."""
        bedtime = _post_rank(self.client, mode="simple", intent_text="bedtime calm").json()
        weekend = _post_rank(self.client, mode="simple", intent_text="fun energetic weekend").json()

        bedtime_top = bedtime["ranked_items"][0]["item"]["item_id"]
        weekend_top = weekend["ranked_items"][0]["item"]["item_id"]

        assert bedtime_top != weekend_top, (
            f"Bedtime and weekend should rank different items first, "
            f"but both returned {bedtime_top}"
        )

    # -- mode defaults -------------------------------------------------------

    def test_default_mode_is_advanced(self):
        """Omitting mode should default to advanced (latency has diversity_check)."""
        resp = self.client.post("/rank", json={
            "items": ITEMS,
            "user_context": {"user_id": "u"},
        })
        assert resp.status_code == 200
        data = resp.json()
        # Advanced mode always populates diversity_check_ms
        assert "diversity_check_ms" in data["latency"]

    # -- integration-level tests ---------------------------------------------

    def test_integration_empty_items(self):
        """Integration-level assertion: empty item list returns 422 and deterministic outcome."""
        from fastapi.testclient import TestClient
        from intent_engine.api import app
        client = TestClient(app)
        resp = client.post("/rank", json={"items": [], "user_context": {"user_id": "u", "intent": {"intent_type": "search"}}, "mode": "simple"})
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["type"] == "too_short"
