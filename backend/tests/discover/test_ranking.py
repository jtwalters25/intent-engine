"""Deterministic Discover ranking tests (spec sections 12, 13)."""

from datetime import datetime, timezone
from decimal import Decimal

from intent_engine.discover.ranking import ENGINE_VERSION, rank_candidates
from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _prov(value, status=EvidenceStatus.VERIFIED, source_field="field"):
    kwargs = dict(value=value, status=status, source="test",
                  source_url="https://example.com/e", retrieved_at=NOW)
    if status is EvidenceStatus.VERIFIED:
        kwargs["source_field"] = source_field
    return AttributeProvenance(**kwargs)


def _candidate(cid, title="Activity", provider="p", category=None, provenance=None, **scalars):
    base = dict(candidate_id=cid, provider=provider, provider_id=cid, title=title,
                source_url="https://example.com/e", retrieved_at=NOW)
    if category is not None:
        base["category"] = category
    base.update(scalars)
    cand = DiscoveryCandidate(**base)
    prov = dict(provenance or {})
    if category is not None and "category" not in prov:
        prov["category"] = _prov(category)
    if prov:
        cand.provenance = prov
    return cand


def test_family_friendly_outranks_unfriendly():
    req = DiscoveryRequest(query="something to do")
    museum = _candidate("c-museum", category="Museum")
    club = _candidate("c-club", category="Nightclub")
    result = rank_candidates([club, museum], req)
    assert [r.candidate_id for r in result.ranked][0] == "c-museum"
    assert result.ranked[0].status == "boosted"
    assert result.ranked[-1].candidate_id == "c-club"


def test_hard_fail_is_excluded_not_ranked():
    # Event before the requested window -> hard FAIL -> excluded.
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 11).date())
    dt = datetime(2026, 10, 1, 19, tzinfo=timezone.utc)
    bad = _candidate("c-old", start_time=dt, provenance={"start_time": _prov(dt)})
    ok_dt = datetime(2026, 10, 12, 19, tzinfo=timezone.utc)
    good = _candidate("c-new", start_time=ok_dt, provenance={"start_time": _prov(ok_dt)})
    result = rank_candidates([bad, good], req)
    ids = [r.candidate_id for r in result.ranked]
    assert "c-old" not in ids
    assert "c-old" in result.excluded_ids
    assert "c-new" in ids


def test_needs_verification_flagged_but_ranked():
    # Budget stated but price basis unknown -> UNKNOWN -> needs verification.
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate("c1", category="Museum", provenance={
        "category": _prov("Museum"),
        "price_min": _prov(Decimal("20")),
        "price_basis": _prov(None, status=EvidenceStatus.UNKNOWN),
    })
    result = rank_candidates([cand], req)
    assert result.ranked[0].needs_verification is True
    assert "c1" in result.needs_verification_ids
    assert result.ranked[0].constraint_states["budget"] == "UNKNOWN"


def test_all_unknown_signals_are_neutral():
    req = DiscoveryRequest(query="zzz")  # no query-term overlap, no preferences
    cand = _candidate("c1")  # no category, no evidence
    result = rank_candidates([cand], req)
    r = result.ranked[0]
    assert r.multiplier_product == 1.0  # six neutral signals
    assert r.status == "neutral"


def test_diversity_demotes_repeated_category():
    req = DiscoveryRequest(query="x")
    # Three museums (same diversity key) + one park.
    cands = [
        _candidate("m1", category="Museum"),
        _candidate("m2", category="Museum"),
        _candidate("m3", category="Museum"),
        _candidate("p1", category="Park"),
    ]
    result = rank_candidates(cands, req)
    museums = [r for r in result.ranked if r.candidate_id.startswith("m")]
    # First museum has no penalty; later museums are penalized.
    assert museums[0].diversity_penalty == 0.0
    assert museums[1].diversity_penalty < 0.0
    assert museums[2].diversity_penalty < museums[1].diversity_penalty


def test_deterministic_tie_break_by_candidate_id():
    req = DiscoveryRequest(query="x")
    # Identical evidence -> identical scores -> order by candidate_id.
    a = _candidate("b-id", category="Museum")
    b = _candidate("a-id", category="Museum")
    result = rank_candidates([a, b], req)
    ids = [r.candidate_id for r in result.ranked]
    assert ids == ["a-id", "b-id"]


def test_fingerprint_is_reproducible_and_input_sensitive():
    req = DiscoveryRequest(query="x")
    cands = [_candidate("c1", category="Museum"), _candidate("c2", category="Park")]
    first = rank_candidates(cands, req)
    second = rank_candidates(list(reversed(cands)), req)  # order-independent inputs
    assert first.fingerprint == second.fingerprint
    assert first.engine_version == ENGINE_VERSION

    # A different config version changes the fingerprint.
    other = rank_candidates(cands, req, config_version="v2")
    assert other.fingerprint != first.fingerprint


def test_contiguous_ranks():
    req = DiscoveryRequest(query="x")
    cands = [_candidate(f"c{i}", category="Museum") for i in range(5)]
    result = rank_candidates(cands, req)
    assert [r.rank for r in result.ranked] == [1, 2, 3, 4, 5]
