"""Discover API endpoint tests (spec section 14) — mocked providers, no live calls."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from intent_engine.api import app
from intent_engine.discover.providers.base import ProviderTimeout
from intent_engine.discover.router import get_providers
from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    EvidenceStatus,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _candidate(cid="t:1"):
    cand = DiscoveryCandidate(candidate_id=cid, provider="ticketmaster", provider_id=cid,
                              title="Science Museum", category="Museum",
                              source_url="https://example.com/e", retrieved_at=NOW)
    cand.provenance = {"category": AttributeProvenance(
        value="Museum", status=EvidenceStatus.VERIFIED, source="t",
        source_url="https://example.com/e", retrieved_at=NOW, source_field="classifications")}
    return cand


class FakeProvider:
    def __init__(self, name, candidates=None, error=None):
        self.name = name
        self._candidates = candidates or []
        self._error = error

    async def search(self, request):
        if self._error is not None:
            raise self._error
        return list(self._candidates)


def _client(providers):
    app.dependency_overrides[get_providers] = lambda: providers
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_search_returns_results():
    client = _client([FakeProvider("ticketmaster", [_candidate()])])
    resp = client.post("/discover/search", json={"query": "museum"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["title"] == "Science Museum"
    assert body["ranking_fingerprint"]
    assert "explanation" in body["results"][0]


def test_search_all_providers_fail_returns_502():
    client = _client([FakeProvider("ticketmaster", error=ProviderTimeout("x"))])
    resp = client.post("/discover/search", json={"query": "museum"})
    assert resp.status_code == 502


def test_search_rejects_invalid_request():
    client = _client([FakeProvider("ticketmaster", [_candidate()])])
    resp = client.post("/discover/search", json={"query": "   "})  # blank query
    assert resp.status_code == 422


def test_feedback_accepts_valid_payload():
    client = _client([])
    resp = client.post("/discover/feedback", json={
        "request_id": "req-1", "helpfulness": "very_helpful", "would_use_again": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"


def test_feedback_rejects_unknown_helpfulness():
    client = _client([])
    resp = client.post("/discover/feedback", json={
        "request_id": "req-1", "helpfulness": "meh",
    })
    assert resp.status_code == 422
