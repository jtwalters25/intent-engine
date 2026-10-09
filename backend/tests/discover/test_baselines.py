"""Evaluation comparison-arm tests (spec section 16)."""

from datetime import datetime, timezone
from decimal import Decimal

from intent_engine.discover.evaluation.baselines import (
    candidate_to_snapshot,
    intent_engine_arm,
    llm_only_arm,
    pool_from_candidates,
    relevance_arm,
    stated_from_request,
    LLMArmOutput,
)
from intent_engine.discover.evaluation.contracts import (
    ArmResult,
    AssertedFact,
    EvaluationSession,
    GroundTruthLabel,
    PriceBasis,
)
from intent_engine.discover.evaluation.metrics import compute_arm_report
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
    kwargs = dict(value=value, status=status, source="t",
                  source_url="https://example.com/e", retrieved_at=NOW)
    if status is EvidenceStatus.VERIFIED:
        kwargs["source_field"] = source_field
    return AttributeProvenance(**kwargs)


def _candidate(cid, title="Science Museum", category="Museum", provenance=None, **scalars):
    cand = DiscoveryCandidate(candidate_id=cid, provider="p", provider_id=cid, title=title,
                              category=category, source_url="https://example.com/e",
                              retrieved_at=NOW, **scalars)
    prov = {"title": _prov(title), "category": _prov(category)}
    prov.update(provenance or {})
    cand.provenance = prov
    return cand


# ---------------------------------------------------------------------------
# Shared-pool helpers
# ---------------------------------------------------------------------------

def test_candidate_to_snapshot_carries_provenance():
    cand = _candidate("c1")
    snap = candidate_to_snapshot(cand)
    assert snap.candidate_id == "c1"
    assert snap.attributes["category"].status is EvidenceStatus.VERIFIED


def test_stated_from_request_maps_date_window():
    req = DiscoveryRequest(query="x", start_date=datetime(2026, 10, 9).date(),
                           budget_total=Decimal("100"), children_ages=[7])
    stated = stated_from_request(req)
    assert stated.date_window_required is True
    assert stated.budget_total == Decimal("100")
    assert stated.children_ages == [7]


# ---------------------------------------------------------------------------
# Arm A — relevance
# ---------------------------------------------------------------------------

def test_relevance_arm_orders_by_overlap_then_popularity_and_asserts_nothing():
    a = _candidate("a", title="Science Museum", provenance={"popularity": _prov(10)})
    b = _candidate("b", title="Science Museum", provenance={"popularity": _prov(99)})
    c = _candidate("c", title="Jazz Bar", category="Bar")
    pool = pool_from_candidates([a, b, c])
    arm = relevance_arm(pool, query="science museum")
    # a and b both match 'science'/'museum'; b wins on popularity; c last.
    assert arm.ranking == ["b", "a", "c"]
    assert arm.asserted_facts == []
    assert arm.explanations == {}


# ---------------------------------------------------------------------------
# Arm B — llm_only (injected client)
# ---------------------------------------------------------------------------

def test_llm_only_arm_packages_client_output():
    class FaithfulClient:
        def rank(self, pool, stated):
            return LLMArmOutput(ranking=[s.candidate_id for s in pool])

    pool = pool_from_candidates([_candidate("a"), _candidate("b")])
    arm = llm_only_arm(pool, stated_from_request(DiscoveryRequest(query="x")),
                       client=FaithfulClient())
    assert arm.ranking == ["a", "b"]
    assert arm.asserted_facts == []


def test_reckless_llm_assertion_is_caught_as_factual_error():
    # A model that asserts an unknown price as fact must score a factual error.
    class RecklessClient:
        def rank(self, pool, stated):
            cid = pool[0].candidate_id
            return LLMArmOutput(
                ranking=[cid],
                asserted_facts=[AssertedFact(candidate_id=cid, attribute="price_total",
                                             asserted_value=Decimal("0"),
                                             asserted_as=EvidenceStatus.VERIFIED)],
            )

    cand = _candidate("a")
    pool = pool_from_candidates([cand])
    arm = llm_only_arm(pool, stated_from_request(DiscoveryRequest(query="x")),
                       client=RecklessClient())
    # Ground truth: price basis unknown -> the arm fabricated a fact.
    gt = {"a": GroundTruthLabel(candidate_id="a", verified_price_basis=PriceBasis.UNKNOWN,
                                verified_at=NOW, verifier="h")}
    session = EvaluationSession(session_id="s", arms={"llm_only": arm},
                                ground_truth=list(gt.values()))
    report = compute_arm_report(session, "llm_only")
    assert report.critical_factual_error_count == 1


# ---------------------------------------------------------------------------
# Arm C — intent engine (faithful)
# ---------------------------------------------------------------------------

def test_intent_engine_arm_asserts_only_verified_and_caveats_unknowns():
    req = DiscoveryRequest(query="museum", budget_total=Decimal("100"))
    # Verified total (basis total) -> engine may assert price_total.
    priced = _candidate("priced", provenance={
        "price_min": _prov(Decimal("40")), "price_basis": _prov("total")})
    # Unknown basis -> engine must NOT assert price; must caveat.
    unknown = _candidate("unknown", provenance={
        "price_min": _prov(Decimal("20")),
        "price_basis": _prov(None, status=EvidenceStatus.UNKNOWN)})

    arm = intent_engine_arm([priced, unknown], req)

    # Asserts price_total only for the verified-total candidate.
    asserted = {(f.candidate_id, f.attribute) for f in arm.asserted_facts}
    assert ("priced", "price_total") in asserted
    assert ("unknown", "price_total") not in asserted

    # The unknown candidate carries a budget caveat.
    unknown_claims = arm.explanations["unknown"]
    assert any(c.kind is ClaimKind.CAVEAT and c.attribute == "budget" for c in unknown_claims)
    assert arm.ranking_fingerprint


def test_engine_scores_zero_factual_errors_against_matching_ground_truth():
    req = DiscoveryRequest(query="museum", budget_total=Decimal("100"))
    priced = _candidate("priced", provenance={
        "price_min": _prov(Decimal("40")), "price_basis": _prov("total")})
    arm = intent_engine_arm([priced], req)
    gt = GroundTruthLabel(candidate_id="priced", verified_price_basis=PriceBasis.TOTAL,
                          verified_total_cost=Decimal("40"), verified_at=NOW, verifier="h")
    session = EvaluationSession(session_id="s", arms={"intent_engine": arm},
                                stated_constraints=stated_from_request(req),
                                ground_truth=[gt])
    report = compute_arm_report(session, "intent_engine")
    assert report.critical_factual_error_count == 0
    assert report.verified_constraint_satisfaction_rate == 1.0
