"""Deterministic Discover ranking (spec sections 12, 13).

A narrowly-scoped ranker for the Discover domain. It mirrors the house
multiplier-chain shape — ``final_score = base_relevance × ∏ signal_multipliers``
with a diversity penalty and stable tie-breaking — but operates on
``DiscoveryCandidate`` and the six evidence-based signals (`signals.py`) rather
than the legacy ``Item``/``MultiplierSet``. It deliberately does not register a
new ``Domain`` or touch ``core/``: the candidate shape and evidence-based signals
do not fit the fixed five-slot ``MultiplierSet``, and §12 permits "the existing
ranking engine OR its supported extension points".

Guarantees:
- Hard constraints run first (`constraints.filter_candidates`); a FAIL is
  excluded and no soft signal can resurrect it (spec §12).
- No LLM-generated scores; every number is a deterministic function of the
  candidate evidence, the request, and the config/engine version.
- Identical (request, candidate pool, config, engine version) → identical
  ``ranking_fingerprint`` and identical ordering/scores (spec §12 determinism;
  aligns with the §16.1 reproducibility contract, whose ledger wiring is Phase 7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from intent_engine.discover.constraints import filter_candidates
from intent_engine.discover.schemas import DiscoveryCandidate, DiscoveryRequest
from intent_engine.discover.signals import SIGNAL_NAMES, SignalResult, compute_signals

ENGINE_VERSION = "discover-ranker-0.1.0"
DIVERSITY_WEIGHT = 0.05
_ROUND = 10  # decimal places for score stability in output and fingerprint


def _signal_multiplier(value: float) -> float:
    """Map a 0–1 fit onto a multiplier around 1.0 (neutral at fit 0.5)."""
    return 0.5 + value


def _base_relevance(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> float:
    """Deterministic query-term overlap over title/category/description.

    Range [0.5, 1.0]: 0.5 when no query terms match, 1.0 when all do. Kept simple
    and transparent; this is the engine arm's base, distinct from the Phase 7
    relevance *baseline* arm.
    """
    terms = {t for t in request.query.lower().split() if len(t) > 2}
    if not terms:
        return 1.0
    haystack = " ".join(
        part for part in (candidate.title, candidate.category, candidate.description)
        if isinstance(part, str)
    ).lower()
    hits = sum(1 for term in terms if term in haystack)
    return 0.5 + 0.5 * (hits / len(terms))


def _diversity_key(candidate: DiscoveryCandidate) -> str:
    if isinstance(candidate.category, str) and candidate.category.strip():
        return candidate.category.strip().lower()
    return candidate.provider


@dataclass(frozen=True)
class RankedCandidate:
    candidate_id: str
    rank: int
    base_relevance: float
    signals: Dict[str, float]
    signal_details: Dict[str, SignalResult]
    multiplier_product: float
    diversity_penalty: float
    final_score: float
    status: str  # "boosted" | "neutral" | "demoted"
    needs_verification: bool
    constraint_states: Dict[str, str]


@dataclass(frozen=True)
class DiscoveryRankingResult:
    ranked: List[RankedCandidate] = field(default_factory=list)
    needs_verification_ids: List[str] = field(default_factory=list)
    excluded_ids: List[str] = field(default_factory=list)
    fingerprint: str = ""
    engine_version: str = ENGINE_VERSION
    config_version: str = "default"


def _status(final: float, base: float) -> str:
    if final > base:
        return "boosted"
    if final < base * 0.9:
        return "demoted"
    return "neutral"


def _fingerprint(
    request: DiscoveryRequest,
    ordered: List[Dict[str, Any]],
    config_version: str,
) -> str:
    payload = {
        "intent": request.model_dump(mode="json"),
        "config_version": config_version,
        "engine_version": ENGINE_VERSION,
        "ranking": [
            {
                "candidate_id": e["candidate_id"],
                "final_score": round(e["final"], _ROUND),
                "base": round(e["base"], _ROUND),
                "signals": {n: round(e["signals"][n], _ROUND) for n in SIGNAL_NAMES},
            }
            for e in ordered
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def rank_candidates(
    candidates: List[DiscoveryCandidate],
    request: DiscoveryRequest,
    *,
    config_version: str = "default",
) -> DiscoveryRankingResult:
    """Rank eligible candidates deterministically against the request."""
    filtered = filter_candidates(candidates, request)
    needs_ids = {c.candidate_id for c in filtered.needs_verification}

    scored: List[Dict[str, Any]] = []
    for candidate in filtered.eligible:
        sigs = compute_signals(candidate, request)
        product = 1.0
        for name in SIGNAL_NAMES:
            product *= _signal_multiplier(sigs[name].value)
        base = _base_relevance(candidate, request)
        scored.append({
            "candidate_id": candidate.candidate_id,
            "base": base,
            "product": product,
            "raw": base * product,
            "signals": {n: sigs[n].value for n in SIGNAL_NAMES},
            "details": sigs,
            "dkey": _diversity_key(candidate),
        })

    # Order by raw score, deterministic tie-break on candidate_id.
    scored.sort(key=lambda s: (-s["raw"], s["candidate_id"]))

    # Diversity: demote each repeat of a key by prior global occurrences.
    seen: Dict[str, int] = {}
    for entry in scored:
        prior = seen.get(entry["dkey"], 0)
        penalty = -DIVERSITY_WEIGHT * prior * entry["raw"]
        entry["penalty"] = penalty
        entry["final"] = max(0.0, entry["raw"] + penalty)
        seen[entry["dkey"]] = prior + 1

    # Final order after penalties, same deterministic tie-break.
    scored.sort(key=lambda s: (-s["final"], s["candidate_id"]))

    evaluations = filtered.evaluations
    ranked: List[RankedCandidate] = []
    for rank, entry in enumerate(scored, start=1):
        result = evaluations.get(entry["candidate_id"])
        constraint_states = (
            {c.name: c.state.value for c in result.checks} if result else {}
        )
        ranked.append(RankedCandidate(
            candidate_id=entry["candidate_id"],
            rank=rank,
            base_relevance=round(entry["base"], _ROUND),
            signals={n: round(entry["signals"][n], _ROUND) for n in SIGNAL_NAMES},
            signal_details=entry["details"],
            multiplier_product=round(entry["product"], _ROUND),
            diversity_penalty=round(entry["penalty"], _ROUND),
            final_score=round(entry["final"], _ROUND),
            status=_status(entry["final"], entry["base"]),
            needs_verification=entry["candidate_id"] in needs_ids,
            constraint_states=constraint_states,
        ))

    return DiscoveryRankingResult(
        ranked=ranked,
        needs_verification_ids=[c.candidate_id for c in filtered.needs_verification],
        excluded_ids=[c.candidate_id for c in filtered.excluded],
        fingerprint=_fingerprint(request, scored, config_version),
        engine_version=ENGINE_VERSION,
        config_version=config_version,
    )
