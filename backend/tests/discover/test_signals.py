"""Discover ranking-signal tests (spec §10): meaning, range, missing-value."""

from datetime import datetime, timezone
from decimal import Decimal

from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)
from intent_engine.discover.signals import (
    NEUTRAL,
    SIGNAL_NAMES,
    compute_signals,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _prov(value, status=EvidenceStatus.VERIFIED, source_field="field", extractor=None):
    kwargs = dict(value=value, status=status, source="test",
                  source_url="https://example.com/e", retrieved_at=NOW)
    if status is EvidenceStatus.VERIFIED:
        kwargs["source_field"] = source_field
    elif status is EvidenceStatus.EXTRACTED:
        kwargs["extractor"] = extractor or "x-v1"
    return AttributeProvenance(**kwargs)


def _candidate(title="Activity", provenance=None, **scalars):
    base = dict(candidate_id="c1", provider="p", provider_id="1", title=title,
                source_url="https://example.com/e", retrieved_at=NOW)
    base.update(scalars)
    cand = DiscoveryCandidate(**base)
    if provenance:
        cand.provenance = provenance
    return cand


def _sig(candidate, request, name):
    return compute_signals(candidate, request)[name]


REQ = DiscoveryRequest(query="x")


# ---------------------------------------------------------------------------
# family_friendly / educational_value (keyword signals)
# ---------------------------------------------------------------------------

def test_family_friendly_from_verified_category():
    cand = _candidate(category="Museum", provenance={"category": _prov("Museum")})
    s = _sig(cand, REQ, "family_friendly")
    assert s.value > 0.5 and s.known and s.evidence_status is EvidenceStatus.VERIFIED


def test_family_unfriendly_category_scores_low():
    cand = _candidate(category="Nightclub", provenance={"category": _prov("Nightclub")})
    s = _sig(cand, REQ, "family_friendly")
    assert s.value < 0.5 and s.known


def test_family_friendly_falls_back_to_title_as_extracted():
    cand = _candidate(title="Kids Science Fair")  # no category evidence
    s = _sig(cand, REQ, "family_friendly")
    assert s.value > 0.5 and s.known
    assert s.evidence_status is EvidenceStatus.EXTRACTED


def test_family_friendly_unknown_when_no_keyword():
    cand = _candidate(title="Quarterly Shareholder Meeting")
    s = _sig(cand, REQ, "family_friendly")
    assert s.value == NEUTRAL and not s.known
    assert s.evidence_status is EvidenceStatus.UNKNOWN


def test_educational_value_from_category():
    cand = _candidate(category="Science", provenance={"category": _prov("Science")})
    s = _sig(cand, REQ, "educational_value")
    assert s.value > 0.5 and s.known


# ---------------------------------------------------------------------------
# budget_fit
# ---------------------------------------------------------------------------

def test_budget_fit_unknown_without_budget():
    cand = _candidate()
    s = _sig(cand, DiscoveryRequest(query="x"), "budget_fit")
    assert s.value == NEUTRAL and not s.known


def test_budget_fit_high_when_well_under_budget():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("10")),
        "price_basis": _prov("total"),
    })
    s = _sig(cand, req, "budget_fit")
    assert s.known and s.evidence_status is EvidenceStatus.VERIFIED
    assert s.value > 0.5


def test_budget_fit_unknown_when_total_not_verified():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("10")),
        "price_basis": _prov(None, status=EvidenceStatus.UNKNOWN),
    })
    s = _sig(cand, req, "budget_fit")
    assert s.value == NEUTRAL and not s.known


# ---------------------------------------------------------------------------
# distance_fit
# ---------------------------------------------------------------------------

def test_distance_fit_unknown_without_location():
    cand = _candidate(latitude=47.6, longitude=-122.3)
    s = _sig(cand, DiscoveryRequest(query="x"), "distance_fit")  # request has no coords
    assert s.value == NEUTRAL and not s.known


def test_distance_fit_near_scores_high_and_is_extracted():
    req = DiscoveryRequest(query="x", latitude=47.6050, longitude=-122.3344)
    cand = _candidate(latitude=47.6060, longitude=-122.3350)  # ~100m away
    s = _sig(cand, req, "distance_fit")
    assert s.known and s.evidence_status is EvidenceStatus.EXTRACTED
    assert s.value > 0.9


def test_distance_fit_far_scores_low():
    req = DiscoveryRequest(query="x", latitude=47.6, longitude=-122.3)
    cand = _candidate(latitude=48.2, longitude=-122.3)  # ~67 km north
    s = _sig(cand, req, "distance_fit")
    assert s.value == 0.0


# ---------------------------------------------------------------------------
# schedule_fit
# ---------------------------------------------------------------------------

def test_schedule_fit_unknown_without_window():
    cand = _candidate()
    s = _sig(cand, DiscoveryRequest(query="x"), "schedule_fit")
    assert s.value == NEUTRAL and not s.known


def test_schedule_fit_within_window():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date(),
                           end_date=datetime(2026, 10, 11).date())
    dt = datetime(2026, 10, 10, 19, tzinfo=timezone.utc)
    cand = _candidate(start_time=dt, provenance={"start_time": _prov(dt)})
    s = _sig(cand, req, "schedule_fit")
    assert s.value == 1.0 and s.known and s.evidence_status is EvidenceStatus.VERIFIED


def test_schedule_fit_unknown_when_time_unverified():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date())
    cand = _candidate()  # no start_time evidence
    s = _sig(cand, req, "schedule_fit")
    assert s.value == NEUTRAL and not s.known


# ---------------------------------------------------------------------------
# duration_fit
# ---------------------------------------------------------------------------

def test_duration_fit_unknown_without_preference():
    cand = _candidate()
    s = _sig(cand, DiscoveryRequest(query="x"), "duration_fit")
    assert s.value == NEUTRAL and not s.known


def test_duration_fit_close_scores_high():
    req = DiscoveryRequest(query="x", duration_minutes=120)
    cand = _candidate(provenance={"duration_minutes": _prov(110)})
    s = _sig(cand, req, "duration_fit")
    assert s.known and s.value > 0.9


def test_duration_fit_unknown_when_not_verified():
    req = DiscoveryRequest(query="x", duration_minutes=120)
    cand = _candidate()  # providers leave duration UNKNOWN
    s = _sig(cand, req, "duration_fit")
    assert s.value == NEUTRAL and not s.known


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------

def test_compute_signals_returns_all_named_signals_in_range():
    cand = _candidate(category="Museum", provenance={"category": _prov("Museum")})
    signals = compute_signals(cand, DiscoveryRequest(query="x"))
    assert set(signals) == set(SIGNAL_NAMES)
    assert all(0.0 <= s.value <= 1.0 for s in signals.values())


def test_signals_are_deterministic():
    req = DiscoveryRequest(query="x", latitude=47.6, longitude=-122.3)
    cand = _candidate(category="Museum", latitude=47.61, longitude=-122.31,
                      provenance={"category": _prov("Museum")})
    first = compute_signals(cand, req)
    second = compute_signals(cand, req)
    assert {k: v.value for k, v in first.items()} == {k: v.value for k, v in second.items()}
