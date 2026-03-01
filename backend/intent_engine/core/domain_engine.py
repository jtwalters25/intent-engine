"""Domain-agnostic ranking engine using pluggable adapters."""

import time as _time
from typing import Any, Dict, List

from intent_engine.core.adapter_protocol import DomainAdapter
from intent_engine.schemas import (
    Domain,
    Item,
    LatencyBreakdown,
    MultiplierSet,
    RankedItem,
    RankingRequest,
    RankingResponse,
    ScoreBreakdown,
)

DIVERSITY_PENALTY = -0.05  # per consecutive duplicate key


class DomainRankingEngine:
    """Multiplier-chain ranker that delegates domain logic to adapters."""

    def __init__(self, adapters: Dict[Domain, DomainAdapter]) -> None:
        self._adapters = adapters

    @property
    def registered_domains(self) -> List[Domain]:
        return list(self._adapters.keys())

    def rank(self, request: RankingRequest) -> RankingResponse:
        domain = request.domain
        if domain is None or domain not in self._adapters:
            raise ValueError(
                f"No adapter registered for domain={domain!r}. "
                f"Registered: {self.registered_domains}"
            )

        adapter = self._adapters[domain]

        # --- Intent resolution ---
        t0 = _time.perf_counter()
        raw_intent = request.user_context.intent.model_dump()
        if request.intent_text:
            raw_intent["intent_text"] = request.intent_text
        resolved_intent = adapter.resolve_intent(raw_intent)
        t_intent = (_time.perf_counter() - t0) * 1000

        # --- Scoring ---
        t1 = _time.perf_counter()
        scored: List[Dict[str, Any]] = []
        for item in request.items:
            blocked = adapter.apply_hard_constraints(item, request.constraints)
            multipliers = adapter.compute_multipliers(item, resolved_intent)

            if blocked:
                breakdown = ScoreBreakdown(
                    base_score=item.base_score,
                    multipliers=multipliers,
                    final_score=0.0,
                    blocked=True,
                    block_reason="Hard constraint violated",
                )
                scored.append({
                    "item": item,
                    "multipliers": multipliers,
                    "breakdown": breakdown,
                    "final_score": 0.0,
                    "blocked": blocked,
                })
            else:
                raw_score = (
                    item.base_score
                    * multipliers.context
                    * multipliers.profile
                    * multipliers.urgency
                    * multipliers.cost
                    * multipliers.prophecy
                )
                scored.append({
                    "item": item,
                    "multipliers": multipliers,
                    "breakdown": None,  # filled after diversity
                    "final_score": raw_score,
                    "blocked": False,
                })
        t_ranking = (_time.perf_counter() - t1) * 1000

        # --- Diversity penalty ---
        t2 = _time.perf_counter()
        # Sort by raw score descending before applying penalties
        scored.sort(key=lambda s: s["final_score"], reverse=True)

        seen_keys: Dict[str, int] = {}
        for entry in scored:
            if entry["blocked"]:
                continue
            key = adapter.diversity_key(entry["item"])
            count = seen_keys.get(key, 0)
            penalty = DIVERSITY_PENALTY * count if count > 0 else 0.0
            entry["final_score"] = max(0.0, entry["final_score"] + penalty)
            entry["diversity_penalty"] = penalty
            seen_keys[key] = count + 1

        # Re-sort after penalties
        scored.sort(key=lambda s: s["final_score"], reverse=True)
        t_diversity = (_time.perf_counter() - t2) * 1000

        # --- Build response ---
        ranked_items: List[RankedItem] = []
        for rank_pos, entry in enumerate(scored, start=1):
            item: Item = entry["item"]
            mults: MultiplierSet = entry["multipliers"]

            if entry["blocked"]:
                breakdown = entry["breakdown"]
                status = "blocked"
            else:
                diversity_pen = entry.get("diversity_penalty", 0.0)
                breakdown = ScoreBreakdown(
                    base_score=item.base_score,
                    multipliers=mults,
                    diversity_penalty=diversity_pen,
                    final_score=entry["final_score"],
                )
                if entry["final_score"] > item.base_score:
                    status = "boosted"
                elif entry["final_score"] < item.base_score * 0.9:
                    status = "demoted"
                else:
                    status = "neutral"

            explanation = adapter.explain(item, mults)

            ranked_items.append(
                RankedItem(
                    item=item,
                    final_score=entry["final_score"],
                    score=entry["final_score"],
                    rank=rank_pos,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    status=status,
                )
            )

        total_ms = t_intent + t_ranking + t_diversity
        latency = LatencyBreakdown(
            total_ms=total_ms,
            intent_parsing_ms=t_intent,
            ranking_ms=t_ranking,
            diversity_check_ms=t_diversity,
        )

        return RankingResponse(
            ranked_items=ranked_items,
            latency=latency,
            intent=request.user_context.intent,
            domain=domain,
            mode_used=request.mode,
        )
