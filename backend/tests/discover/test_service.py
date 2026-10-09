"""Discover pipeline tests with mocked providers (spec sections 9, 18)."""

import asyncio
from datetime import datetime, timezone

import pytest

from intent_engine.discover.providers.base import ProviderTimeout
from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)
from intent_engine.discover.service import RetrievalError, discover, retrieve_candidates

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _prov(value, source_field="field"):
    return AttributeProvenance(value=value, status=EvidenceStatus.VERIFIED, source="t",
                              source_url="https://example.com/e", retrieved_at=NOW,
                              source_field=source_field)


def _candidate(cid, provider="ticketmaster", title="Science Museum", category="Museum", **scalars):
    cand = DiscoveryCandidate(candidate_id=cid, provider=provider, provider_id=cid,
                              title=title, category=category,
                              source_url="https://example.com/e", retrieved_at=NOW, **scalars)
    cand.provenance = {"category": _prov(category)}
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


REQ = DiscoveryRequest(query="museum")


def test_happy_path_returns_ranked_results():
    providers = [
        FakeProvider("ticketmaster", [_candidate("t:1")]),
        FakeProvider("google_places", [_candidate("g:1", provider="google_places",
                                                   title="City Park", category="Park")]),
    ]
    resp = asyncio.run(discover(REQ, providers))
    assert len(resp.results) == 2
    assert resp.warnings == []
    assert resp.ranking_fingerprint
    assert resp.results[0].rank == 1
    assert resp.results[0].explanation.text


def test_partial_failure_returns_warning_and_other_results():
    providers = [
        FakeProvider("ticketmaster", [_candidate("t:1")]),
        FakeProvider("google_places", error=ProviderTimeout("slow")),
    ]
    resp = asyncio.run(discover(REQ, providers))
    assert len(resp.results) == 1
    assert any("google_places" in w for w in resp.warnings)


def test_all_providers_fail_raises_retrieval_error():
    providers = [
        FakeProvider("ticketmaster", error=ProviderTimeout("x")),
        FakeProvider("google_places", error=ProviderTimeout("y")),
    ]
    with pytest.raises(RetrievalError):
        asyncio.run(discover(REQ, providers))


def test_no_providers_raises():
    with pytest.raises(RetrievalError):
        asyncio.run(retrieve_candidates(REQ, []))


def test_empty_results_is_not_an_error():
    providers = [FakeProvider("ticketmaster", []), FakeProvider("google_places", [])]
    resp = asyncio.run(discover(REQ, providers))
    assert resp.results == []
    assert resp.warnings == []


def test_cross_provider_duplicates_collapse():
    # Same title + coords, no dates -> mergeable fingerprint across providers.
    a = _candidate("t:1", provider="p1", title="City Zoo", category="Zoo",
                   latitude=47.600, longitude=-122.300)
    b = _candidate("g:1", provider="p2", title="City Zoo", category="Zoo",
                   latitude=47.6004, longitude=-122.3001)
    resp = asyncio.run(discover(DiscoveryRequest(query="zoo"),
                                [FakeProvider("p1", [a]), FakeProvider("p2", [b])]))
    assert len(resp.results) == 1


def test_unexpected_exception_propagates():
    class Boom(FakeProvider):
        async def search(self, request):
            raise ValueError("bug")

    with pytest.raises(ValueError):
        asyncio.run(discover(REQ, [Boom("x")]))
