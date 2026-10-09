"""Three-state hard-constraint tests (spec sections 11, 12)."""

from datetime import datetime, timezone
from decimal import Decimal

from intent_engine.discover.constraints import (
    ConstraintState,
    evaluate_candidate,
    filter_candidates,
)
from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
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


def _candidate(cid="c1", provenance=None, **scalars):
    base = dict(
        candidate_id=cid, provider="ticketmaster", provider_id=cid,
        title="Activity", source_url="https://example.com/e", retrieved_at=NOW,
    )
    base.update(scalars)
    cand = DiscoveryCandidate(**base)
    if provenance:
        cand.provenance = provenance
    return cand


def _check(candidate, request, name):
    result = evaluate_candidate(candidate, request)
    return next((c for c in result.checks if c.name == name), None)


# ---------------------------------------------------------------------------
# Date window
# ---------------------------------------------------------------------------

def _event_on(day):
    dt = datetime(2026, 10, day, 19, 0, tzinfo=timezone.utc)
    return _candidate(start_time=dt, provenance={"start_time": _prov(dt)})


def test_date_within_window_passes():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date(),
                           end_date=datetime(2026, 10, 11).date())
    check = _check(_event_on(10), req, "date_window")
    assert check.state is ConstraintState.PASS


def test_date_before_window_fails():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 11).date())
    check = _check(_event_on(10), req, "date_window")
    assert check.state is ConstraintState.FAIL


def test_date_after_window_fails():
    req = DiscoveryRequest(query="x", end_date=datetime(2026, 10, 9).date())
    check = _check(_event_on(10), req, "date_window")
    assert check.state is ConstraintState.FAIL


def test_unverified_date_is_unknown():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date())
    cand = _candidate()  # no start_time evidence
    check = _check(cand, req, "date_window")
    assert check.state is ConstraintState.UNKNOWN


def test_extracted_date_does_not_fail():
    # Only VERIFIED evidence may FAIL; EXTRACTED routes to UNKNOWN.
    dt = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)  # before window
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date())
    cand = _candidate(provenance={"start_time": _prov(dt, status=EvidenceStatus.EXTRACTED)})
    check = _check(cand, req, "date_window")
    assert check.state is ConstraintState.UNKNOWN


# ---------------------------------------------------------------------------
# Budget (spec section 12)
# ---------------------------------------------------------------------------

def test_budget_unknown_when_basis_unverified():
    # Verified price but no verified basis -> total cannot be established.
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"), party_size=4)
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("20")),
        "price_basis": _prov(None, status=EvidenceStatus.UNKNOWN),
    })
    check = _check(cand, req, "budget")
    assert check.state is ConstraintState.UNKNOWN


def test_budget_total_basis_passes():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("40")),
        "price_max": _prov(Decimal("80")),
        "price_basis": _prov("total"),
    })
    check = _check(cand, req, "budget")
    assert check.state is ConstraintState.PASS


def test_budget_per_person_exceeds_fails():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"), party_size=5)
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("30")),  # 30 * 5 = 150 > 100
        "price_max": _prov(Decimal("30")),
        "price_basis": _prov("per_person"),
    })
    check = _check(cand, req, "budget")
    assert check.state is ConstraintState.FAIL


def test_budget_range_straddles_is_unknown():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("80")),
        "price_max": _prov(Decimal("120")),
        "price_basis": _prov("total"),
    })
    check = _check(cand, req, "budget")
    assert check.state is ConstraintState.UNKNOWN


def test_budget_per_person_without_party_is_unknown():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(provenance={
        "price_min": _prov(Decimal("30")),
        "price_basis": _prov("per_person"),
    })
    check = _check(cand, req, "budget")
    assert check.state is ConstraintState.UNKNOWN


# ---------------------------------------------------------------------------
# Minimum age
# ---------------------------------------------------------------------------

def test_min_age_below_requirement_fails():
    req = DiscoveryRequest(query="x", children_ages=[6, 9])
    cand = _candidate(provenance={"age_min": _prov(8)})
    check = _check(cand, req, "min_age")
    assert check.state is ConstraintState.FAIL


def test_min_age_met_passes():
    req = DiscoveryRequest(query="x", children_ages=[6, 9])
    cand = _candidate(provenance={"age_min": _prov(5)})
    check = _check(cand, req, "min_age")
    assert check.state is ConstraintState.PASS


def test_min_age_unknown_is_unknown():
    req = DiscoveryRequest(query="x", children_ages=[6])
    cand = _candidate()  # no age_min evidence
    check = _check(cand, req, "min_age")
    assert check.state is ConstraintState.UNKNOWN


# ---------------------------------------------------------------------------
# Availability (property check, FAIL-only)
# ---------------------------------------------------------------------------

def test_verified_unavailable_fails_and_excludes():
    req = DiscoveryRequest(query="x")
    cand = _candidate(provenance={"availability": _prov(False)})
    result = evaluate_candidate(cand, req)
    assert result.excluded is True


def test_unknown_availability_is_not_needs_verification():
    req = DiscoveryRequest(query="x")  # no stated constraints
    cand = _candidate()
    result = evaluate_candidate(cand, req)
    assert result.needs_verification is False
    assert result.fully_verified is True


# ---------------------------------------------------------------------------
# Aggregation & filtering
# ---------------------------------------------------------------------------

def test_fail_takes_precedence_over_unknown():
    # Date FAIL + budget UNKNOWN -> excluded, not needs_verification.
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 11).date(),
                           budget_total=Decimal("100"), party_size=2)
    cand = _event_on(10)  # before window -> FAIL
    cand.provenance["price_min"] = _prov(Decimal("10"))  # basis still unknown
    result = evaluate_candidate(cand, req)
    assert result.excluded is True
    assert result.needs_verification is False


def test_filter_partitions_and_preserves_order():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date(),
                           end_date=datetime(2026, 10, 11).date())
    verified = _event_on(10)                    # within window -> PASS
    unknown = _candidate(cid="c-unknown")       # no date evidence -> UNKNOWN
    excluded = _event_on(1)                      # before window -> FAIL
    excluded.candidate_id = "c-excluded"

    result = filter_candidates([verified, unknown, excluded], req)

    assert [c.candidate_id for c in result.verified] == ["c1"]
    assert [c.candidate_id for c in result.needs_verification] == ["c-unknown"]
    assert [c.candidate_id for c in result.excluded] == ["c-excluded"]
    assert [c.candidate_id for c in result.eligible] == ["c1", "c-unknown"]


def test_no_stated_constraints_all_verified():
    req = DiscoveryRequest(query="x")
    result = filter_candidates([_candidate(cid="a"), _candidate(cid="b")], req)
    assert len(result.verified) == 2
    assert not result.needs_verification
    assert not result.excluded
