"""Grounded explanation tests (spec section 13.1)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from intent_engine.discover.explain import explain
from intent_engine.discover.ranking import rank_candidates
from intent_engine.discover.schemas import (
    AttributeProvenance,
    ClaimKind,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
    ExplanationClaim,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _prov(value, status=EvidenceStatus.VERIFIED, source_field="field"):
    kwargs = dict(value=value, status=status, source="test",
                  source_url="https://example.com/e", retrieved_at=NOW)
    if status is EvidenceStatus.VERIFIED:
        kwargs["source_field"] = source_field
    return AttributeProvenance(**kwargs)


def _candidate(cid="c1", title="Activity", category=None, provenance=None, **scalars):
    base = dict(candidate_id=cid, provider="p", provider_id=cid, title=title,
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


def _ranked(candidate, request):
    return rank_candidates([candidate], request).ranked[0]


def test_verified_signal_is_stated_as_fact():
    cand = _candidate(category="Museum")
    ex = explain(_ranked(cand, DiscoveryRequest(query="x")))
    fam = next(c for c in ex.claims if c.signal == "family_friendly")
    assert fam.kind is ClaimKind.MATCH
    assert fam.evidence_status is EvidenceStatus.VERIFIED
    assert ex.text.startswith("Recommended because it")
    assert "appears to" not in ex.text  # VERIFIED claims are not hedged


def test_extracted_signal_is_hedged():
    # No category -> family/educational derived from the title -> EXTRACTED.
    cand = _candidate(title="Kids Science Fair")
    ex = explain(_ranked(cand, DiscoveryRequest(query="x")))
    fam = next(c for c in ex.claims if c.signal == "family_friendly")
    assert fam.kind is ClaimKind.MATCH
    assert fam.evidence_status is EvidenceStatus.EXTRACTED
    assert "appears to match your family suitability" in ex.text


def test_unknown_eligibility_constraint_forces_caveat():
    req = DiscoveryRequest(query="x", budget_total=Decimal("100"))
    cand = _candidate(category="Museum", provenance={
        "category": _prov("Museum"),
        "price_min": _prov(Decimal("20")),
        "price_basis": _prov(None, status=EvidenceStatus.UNKNOWN),
    })
    ex = explain(_ranked(cand, req))
    caveat = next(c for c in ex.claims if c.kind is ClaimKind.CAVEAT)
    assert caveat.attribute == "budget"
    assert caveat.evidence_status is EvidenceStatus.UNKNOWN
    assert caveat.text == "budget needs verification"
    assert "needs verification" in ex.text


def test_pass_constraint_becomes_fact_match():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date(),
                           end_date=datetime(2026, 10, 11).date())
    dt = datetime(2026, 10, 10, 19, tzinfo=timezone.utc)
    cand = _candidate(category="Museum", start_time=dt,
                      provenance={"category": _prov("Museum"), "start_time": _prov(dt)})
    ex = explain(_ranked(cand, req))
    claim = next(c for c in ex.claims if c.attribute == "date_window")
    assert claim.kind is ClaimKind.MATCH
    assert claim.evidence_status is EvidenceStatus.VERIFIED
    assert "date window is satisfied" in ex.text


def test_no_evidence_yields_explicit_fallback():
    # No category/title keywords, no stated constraints -> nothing to claim.
    cand = _candidate(title="Quarterly Meeting")
    ex = explain(_ranked(cand, DiscoveryRequest(query="zzz")))
    assert ex.claims == []
    assert ex.text == "No distinguishing evidence available for this option."


def test_explanation_is_deterministic():
    cand = _candidate(category="Museum")
    req = DiscoveryRequest(query="x")
    a = explain(_ranked(cand, req))
    b = explain(_ranked(cand, req))
    assert a.text == b.text
    assert [(c.text, c.kind, c.evidence_status) for c in a.claims] == \
           [(c.text, c.kind, c.evidence_status) for c in b.claims]


def test_contract_forbids_caveat_on_verified():
    # The §13.1 evidence rule is enforced by the claim contract itself.
    with pytest.raises(ValidationError):
        ExplanationClaim(text="x", kind=ClaimKind.CAVEAT, attribute="price",
                         evidence_status=EvidenceStatus.VERIFIED)
