"""Evaluation comparison arms (spec section 16).

Three arms are scored on one shared candidate pool with identical provenance:

- A. **relevance** — a simple keyword/popularity ordering. It makes no grounded
  claims and asserts no facts; honest by silence, but it never surfaces an
  unknown as "needs verification" (so it scores 0 on ``needs_verification_honesty``).
- B. **llm_only** — delegates to an injected ``LLMClient``. Evaluation-only; the
  real client is deferred (requires a configured gateway). Whatever the model
  returns (ranking, claims, asserted facts) is scored as-is, so a model that
  asserts an unknown as fact is caught by ``critical_factual_error_count``.
- C. **intent_engine** — the product. It asserts only VERIFIED facts it actually
  used (from PASS hard constraints) and caveats every eligibility-affecting
  unknown, which is what the primary endpoints reward.

All arms produce an ``ArmResult`` consumable by ``metrics.compute_arm_report``.
``candidate_to_snapshot`` derives the shared evidence pool from the same
``DiscoveryCandidate``s the engine ranks, so candidate ids line up across arms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

from intent_engine.discover.constraints import verified_total_range
from intent_engine.discover.explain import explain
from intent_engine.discover.ranking import rank_candidates
from intent_engine.discover.schemas import DiscoveryCandidate, DiscoveryRequest
from intent_engine.discover.evaluation.contracts import (
    ARM_RELEVANCE,
    ArmResult,
    AssertedFact,
    CandidateSnapshot,
    EvidenceStatus,
    ExplanationClaim,
    StatedConstraints,
)

_TOKEN_MIN = 3


# ---------------------------------------------------------------------------
# Shared-pool helpers
# ---------------------------------------------------------------------------

def candidate_to_snapshot(candidate: DiscoveryCandidate) -> CandidateSnapshot:
    """The evidence view of a candidate: its per-attribute provenance map."""
    return CandidateSnapshot(candidate_id=candidate.candidate_id,
                             attributes=dict(candidate.provenance))


def pool_from_candidates(candidates: List[DiscoveryCandidate]) -> List[CandidateSnapshot]:
    return [candidate_to_snapshot(c) for c in candidates]


def stated_from_request(request: DiscoveryRequest) -> StatedConstraints:
    """Map a DiscoveryRequest onto the evaluable hard-constraint subset."""
    return StatedConstraints(
        budget_total=request.budget_total,
        party_size=request.party_size,
        children_ages=list(request.children_ages),
        date_window_required=request.start_date is not None or request.end_date is not None,
    )


def _attr_value(snapshot: CandidateSnapshot, name: str) -> Any:
    prov = snapshot.attributes.get(name)
    return prov.value if prov is not None else None


# ---------------------------------------------------------------------------
# Arm A — relevance baseline
# ---------------------------------------------------------------------------

def relevance_arm(pool: List[CandidateSnapshot], *, query: str) -> ArmResult:
    """Keyword/popularity ordering. No grounded claims, no asserted facts."""
    terms = {t for t in query.lower().split() if len(t) >= _TOKEN_MIN}

    def score(snapshot: CandidateSnapshot) -> tuple:
        title = str(_attr_value(snapshot, "title") or "")
        category = str(_attr_value(snapshot, "category") or "")
        tokens = set(f"{title} {category}".lower().split())
        overlap = len(terms & tokens) / len(terms) if terms else 0.0
        popularity = _attr_value(snapshot, "popularity")
        popularity = float(popularity) if isinstance(popularity, (int, float)) else 0.0
        return (-overlap, -popularity, snapshot.candidate_id)

    ordered = sorted(pool, key=score)
    return ArmResult(ranking=[s.candidate_id for s in ordered])


# ---------------------------------------------------------------------------
# Arm B — LLM-only (injected client)
# ---------------------------------------------------------------------------

@dataclass
class LLMArmOutput:
    ranking: List[str]
    explanations: Dict[str, List[ExplanationClaim]] = field(default_factory=dict)
    asserted_facts: List[AssertedFact] = field(default_factory=list)


class LLMClient(Protocol):
    """Produces a ranking (and any claims/facts) over the shared pool.

    Given the same VERIFIED/EXTRACTED/UNKNOWN provenance as the engine and an
    instruction not to assert unknowns, a faithful model returns no VERIFIED
    assertion it cannot support. The real client is deferred.
    """

    def rank(self, pool: List[CandidateSnapshot], stated: StatedConstraints) -> LLMArmOutput: ...


def llm_only_arm(
    pool: List[CandidateSnapshot], stated: StatedConstraints, *, client: LLMClient
) -> ArmResult:
    out = client.rank(pool, stated)
    return ArmResult(
        ranking=list(out.ranking),
        explanations={cid: list(claims) for cid, claims in out.explanations.items()},
        asserted_facts=list(out.asserted_facts),
    )


# ---------------------------------------------------------------------------
# Arm C — intent engine (the product)
# ---------------------------------------------------------------------------

def intent_engine_arm(
    candidates: List[DiscoveryCandidate],
    request: DiscoveryRequest,
    *,
    config_version: str = "default",
) -> ArmResult:
    """Run the deterministic engine and package it as an evaluation arm.

    Asserts only VERIFIED facts the engine actually used — a value is claimed as
    fact exactly when a hard constraint PASSed on VERIFIED evidence, mapped to the
    ground-truth attribute vocabulary. Unknowns are caveated by `explain`, never
    asserted — which is the faithfulness the primary endpoints measure.
    """
    result = rank_candidates(candidates, request, config_version=config_version)
    by_id = {c.candidate_id: c for c in candidates}

    explanations: Dict[str, List[ExplanationClaim]] = {}
    facts: List[AssertedFact] = []
    for ranked in result.ranked:
        explanations[ranked.candidate_id] = explain(ranked).claims
        candidate = by_id[ranked.candidate_id]
        states = ranked.constraint_states

        if states.get("date_window") == "PASS":
            facts.append(AssertedFact(candidate_id=ranked.candidate_id,
                                      attribute="within_date_window", asserted_value=True,
                                      asserted_as=EvidenceStatus.VERIFIED))
        if states.get("budget") == "PASS":
            min_total, _ = verified_total_range(candidate, request)
            if min_total is not None:
                facts.append(AssertedFact(candidate_id=ranked.candidate_id,
                                          attribute="price_total", asserted_value=min_total,
                                          asserted_as=EvidenceStatus.VERIFIED))
        if states.get("min_age") == "PASS":
            age = candidate.verified_value("age_min")
            if age is not None:
                facts.append(AssertedFact(candidate_id=ranked.candidate_id,
                                          attribute="min_age", asserted_value=age,
                                          asserted_as=EvidenceStatus.VERIFIED))

    return ArmResult(
        ranking=[r.candidate_id for r in result.ranked],
        explanations=explanations,
        asserted_facts=facts,
        ranking_fingerprint=result.fingerprint,
    )
