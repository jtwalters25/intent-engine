"""End-to-end Discover pipeline through the real provider adapters (spec §19).

Unlike test_service.py (which hand-builds candidates), this drives realistic
Ticketmaster/Google Places JSON fixtures through the actual provider parsing,
normalization, constraints, ranking, and explanation — with a mocked transport,
no live calls. It is the full-stack faithfulness check: verified structured
prices become VERIFIED evidence, Google's price_level is never turned into a
dollar amount, and budget stays UNKNOWN without a verified price basis.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from intent_engine.discover.providers.base import HttpResponse, ProviderResponseError
from intent_engine.discover.providers.google_places import GooglePlacesProvider
from intent_engine.discover.providers.ticketmaster import TicketmasterProvider
from intent_engine.discover.schemas import DiscoveryRequest
from intent_engine.discover.service import RetrievalError, discover

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

TICKETMASTER_PAYLOAD = {
    "_embedded": {
        "events": [{
            "id": "E1",
            "name": "Family Science Night",
            "url": "https://www.ticketmaster.com/event/E1",
            "info": "A hands-on evening of experiments for all ages.",
            "dates": {"start": {"dateTime": "2026-10-10T19:00:00Z"}},
            "classifications": [{"genre": {"name": "Science"}}],
            "priceRanges": [{"currency": "USD", "min": 20.0, "max": 45.0}],
            "_embedded": {"venues": [{
                "name": "Pacific Science Center",
                "location": {"latitude": "47.6190", "longitude": "-122.3500"},
            }]},
        }]
    }
}

GOOGLE_PLACES_PAYLOAD = {
    "status": "OK",
    "results": [{
        "place_id": "P1",
        "name": "City Art Museum",
        "formatted_address": "123 1st Ave, Seattle, WA",
        "geometry": {"location": {"lat": 47.6080, "lng": -122.3400}},
        "types": ["museum", "point_of_interest"],
        "price_level": 2,
        "business_status": "OPERATIONAL",
    }]
}


class RoutingTransport:
    """Returns a fixture payload keyed by a substring of the request URL."""

    def __init__(self, routes):
        self._routes = routes  # {host_substring: payload | int status | Exception}

    async def get(self, url, *, params, timeout):
        for marker, outcome in self._routes.items():
            if marker in url:
                if isinstance(outcome, Exception):
                    raise outcome
                if isinstance(outcome, int):
                    return HttpResponse(status_code=outcome, payload=None)
                return HttpResponse(status_code=200, payload=outcome)
        return HttpResponse(status_code=404, payload=None)


def _providers(transport):
    return [
        TicketmasterProvider(transport=transport, api_key="tm-key", clock=lambda: NOW),
        GooglePlacesProvider(transport=transport, api_key="gp-key", clock=lambda: NOW),
    ]


def _run(request, routes):
    return asyncio.run(discover(request, _providers(RoutingTransport(routes))))


REQUEST = DiscoveryRequest(
    query="museum science", location="Seattle, WA",
    start_date=date(2026, 10, 9), end_date=date(2026, 10, 11),
    budget_total=Decimal("100"),
)
ROUTES = {"ticketmaster.com": TICKETMASTER_PAYLOAD, "googleapis.com": GOOGLE_PLACES_PAYLOAD}


def test_full_pipeline_through_real_adapters():
    resp = _run(REQUEST, ROUTES)
    assert resp.warnings == []
    assert {r.candidate_id for r in resp.results} == {"ticketmaster:E1", "google_places:P1"}

    tm = next(r for r in resp.results if r.candidate_id == "ticketmaster:E1")
    gp = next(r for r in resp.results if r.candidate_id == "google_places:P1")

    # Ticketmaster: structured price range -> VERIFIED scalar price.
    assert tm.price_min == Decimal("20.00") or float(tm.price_min) == 20.0
    assert tm.currency == "USD"
    # Google: price_level is NOT money -> price stays absent (no fabrication).
    assert gp.price_min is None

    # Verified event date within the requested window -> PASS; a place has no date.
    assert tm.constraints["date_window"] == "PASS"
    assert gp.constraints["date_window"] == "UNKNOWN"

    # Faithfulness: a verified price range without a verified basis never claims
    # budget fit — budget is UNKNOWN for both, so both are "needs verification".
    assert tm.constraints["budget"] == "UNKNOWN"
    assert gp.constraints["budget"] == "UNKNOWN"
    assert tm.needs_verification and gp.needs_verification
    assert set(resp.needs_verification_ids) == {"ticketmaster:E1", "google_places:P1"}


def test_pipeline_grounds_explanations_end_to_end():
    resp = _run(REQUEST, ROUTES)
    tm = next(r for r in resp.results if r.candidate_id == "ticketmaster:E1")

    # A verified PASS surfaces as a fact; the unknown budget surfaces as a caveat.
    kinds = {(c.attribute, c.kind, c.evidence_status) for c in tm.explanation.claims}
    assert ("date_window", "match", "VERIFIED") in kinds
    assert any(attr == "budget" and kind == "caveat" and status == "UNKNOWN"
               for (attr, kind, status) in kinds)


def test_pipeline_is_deterministic():
    a = _run(REQUEST, ROUTES)
    b = _run(REQUEST, ROUTES)
    assert a.ranking_fingerprint == b.ranking_fingerprint
    assert [r.candidate_id for r in a.results] == [r.candidate_id for r in b.results]


def test_partial_provider_failure_still_returns_results():
    # Google returns HTTP 500 -> ProviderResponseError; Ticketmaster succeeds.
    resp = _run(REQUEST, {"ticketmaster.com": TICKETMASTER_PAYLOAD, "googleapis.com": 500})
    assert [r.candidate_id for r in resp.results] == ["ticketmaster:E1"]
    assert any("google_places" in w for w in resp.warnings)


def test_all_providers_failing_raises():
    with pytest.raises(RetrievalError):
        _run(REQUEST, {"ticketmaster.com": 503, "googleapis.com": 500})
