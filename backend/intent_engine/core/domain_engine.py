"""Domain-agnostic ranking engine using pluggable adapters."""

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
import math
import time as _time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from intent_engine.core.adapter_protocol import DomainAdapter
from intent_engine.schemas import (
    Domain,
    Intent,
    Item,
    LatencyBreakdown,
    MultiplierSet,
    RankedItem,
    RankingMode,
    RankingRequest,
    RankingResponse,
    ScoreBreakdown,
)

DIVERSITY_PENALTY = -0.05  # per prior occurrence of the same key
SUPPORTED_RESOLVED_RANKING_DOMAINS = frozenset({Domain.STREAMING})
_MAX_RESOLVED_INPUT_DEPTH = 64
_MAX_RESOLVED_INPUT_VALUES = 10_000


class DomainRankingEngine:
    """Multiplier-chain ranker that delegates domain logic to adapters."""

    def __init__(self, adapters: Dict[Domain, DomainAdapter]) -> None:
        self._adapters = adapters

    @property
    def registered_domains(self) -> List[Domain]:
        return list(self._adapters.keys())

    def rank(self, request: RankingRequest) -> RankingResponse:
        domain = request.domain
        adapter = self._adapter_for(domain)

        # --- Intent resolution ---
        t0 = _time.perf_counter()
        raw_intent = request.user_context.intent.model_dump()
        if request.intent_text:
            raw_intent["intent_text"] = request.intent_text
        resolved_intent = adapter.resolve_intent(raw_intent)
        t_intent = (_time.perf_counter() - t0) * 1000

        return self._rank_with_resolved_intent(
            domain=domain,
            adapter=adapter,
            candidates=request.items,
            resolved_intent=resolved_intent,
            constraints=request.constraints,
            response_intent=request.user_context.intent,
            mode_used=request.mode,
            intent_parsing_ms=t_intent,
        )

    def rank_resolved(
        self,
        *,
        domain: Domain,
        resolved_intent: Mapping[str, Any],
        constraints: Mapping[str, Any],
        candidates: Sequence[Item],
    ) -> RankingResponse:
        """Rank candidates from already normalized adapter-ready intent.

        This is the additive V4 execution seam.  It deliberately bypasses
        ``DomainAdapter.resolve_intent`` so an orchestrated ``intent_type`` is
        not inferred a second time.  Callers must pass the immutable values
        produced by the in-process orchestration/normalization path; this
        method is not an external authentication boundary.
        """
        try:
            selected_domain = Domain(domain)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported resolved-ranking domain={domain!r}") from exc
        if selected_domain not in SUPPORTED_RESOLVED_RANKING_DOMAINS:
            raise ValueError(
                "Resolved ranking currently supports the streaming domain only"
            )

        adapter = self._adapter_for(selected_domain)
        try:
            adapter_domain = Domain(adapter.domain)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "Resolved-ranking adapter must declare a valid domain"
            ) from exc
        if adapter_domain != selected_domain:
            raise ValueError(
                "Resolved-ranking adapter domain does not match registration"
            )
        checked_intent = self._snapshot_mapping(
            resolved_intent,
            name="resolved_intent",
        )
        checked_constraints = self._snapshot_mapping(
            constraints,
            name="constraints",
        )
        checked_candidates = self._snapshot_candidates(candidates)

        intent_type = checked_intent.get("intent_type", "unknown")
        if not isinstance(intent_type, str) or not intent_type.strip():
            raise ValueError(
                "resolved_intent.intent_type must be a nonblank string"
            )

        return self._rank_with_resolved_intent(
            domain=selected_domain,
            adapter=adapter,
            candidates=checked_candidates,
            resolved_intent=checked_intent,
            constraints=checked_constraints,
            response_intent=Intent(intent_type=intent_type),
            mode_used=RankingMode.ADVANCED,
            intent_parsing_ms=0.0,
            isolate_adapter_inputs=True,
        )

    def _adapter_for(self, domain: Optional[Domain]) -> DomainAdapter:
        if domain is None or domain not in self._adapters:
            raise ValueError(
                f"No adapter registered for domain={domain!r}. "
                f"Registered: {self.registered_domains}"
            )
        return self._adapters[domain]

    @staticmethod
    def _snapshot_mapping(
        value: Mapping[str, Any],
        *,
        name: str,
    ) -> Dict[str, Any]:
        if not isinstance(value, MappingABC):
            raise TypeError(f"{name} must be a mapping")

        active_containers = set()
        visited_values = [0]

        def snapshot_json(current: Any, *, path: str, depth: int) -> Any:
            visited_values[0] += 1
            if visited_values[0] > _MAX_RESOLVED_INPUT_VALUES:
                raise TypeError(
                    f"{name} exceeds {_MAX_RESOLVED_INPUT_VALUES} values"
                )
            if depth > _MAX_RESOLVED_INPUT_DEPTH:
                raise TypeError(
                    f"{name} exceeds {_MAX_RESOLVED_INPUT_DEPTH} nesting levels"
                )

            if current is None or isinstance(current, (str, bool, int)):
                return current
            if isinstance(current, float):
                if not math.isfinite(current):
                    raise TypeError(f"{path} must be finite")
                return current

            if isinstance(current, MappingABC):
                marker = id(current)
                if marker in active_containers:
                    raise TypeError(f"{path} must not contain a cycle")
                active_containers.add(marker)
                try:
                    try:
                        supplied = dict(current)
                    except Exception as exc:
                        raise TypeError(
                            f"{path} could not be snapshotted"
                        ) from exc
                    if any(not isinstance(key, str) for key in supplied):
                        raise TypeError(f"{path} keys must be strings")
                    return {
                        key: snapshot_json(
                            supplied[key],
                            path=f"{path}.{key}",
                            depth=depth + 1,
                        )
                        for key in supplied
                    }
                finally:
                    active_containers.remove(marker)

            if isinstance(current, (list, tuple)):
                marker = id(current)
                if marker in active_containers:
                    raise TypeError(f"{path} must not contain a cycle")
                active_containers.add(marker)
                try:
                    return [
                        snapshot_json(
                            item,
                            path=f"{path}.{index}",
                            depth=depth + 1,
                        )
                        for index, item in enumerate(current)
                    ]
                finally:
                    active_containers.remove(marker)

            raise TypeError(f"{path} must contain JSON-compatible values")

        snapshot = snapshot_json(value, path=name, depth=0)
        return snapshot

    def _snapshot_item(self, candidate: Item, *, path: str) -> Item:
        if not isinstance(candidate, Item):
            raise TypeError("candidates must contain only Item values")
        try:
            payload = candidate.model_dump(mode="python")
            payload["attributes"] = self._snapshot_mapping(
                payload.get("attributes"),
                name=f"{path}.attributes",
            )
            checked = Item.model_validate(payload)
            for field_name in (
                "base_score",
                "price",
                "popularity_score",
                "quality_score",
            ):
                if not math.isfinite(getattr(checked, field_name)):
                    raise ValueError(f"{field_name} must be finite")
            return checked
        except Exception as exc:
            raise TypeError(f"{path} failed Item validation") from exc

    def _snapshot_candidates(self, candidates: Sequence[Item]) -> Sequence[Item]:
        if not isinstance(candidates, SequenceABC) or isinstance(
            candidates,
            (str, bytes),
        ):
            raise TypeError("candidates must be a sequence of Item")
        try:
            snapshot = tuple(candidates)
        except Exception as exc:
            raise TypeError("candidates could not be snapshotted") from exc
        if not snapshot:
            raise ValueError("candidates must contain at least one Item")
        return tuple(
            self._snapshot_item(candidate, path=f"candidates[{index}]")
            for index, candidate in enumerate(snapshot)
        )

    def _rank_with_resolved_intent(
        self,
        *,
        domain: Domain,
        adapter: DomainAdapter,
        candidates: Sequence[Item],
        resolved_intent: Dict[str, Any],
        constraints: Dict[str, Any],
        response_intent: Intent,
        mode_used: RankingMode,
        intent_parsing_ms: float,
        isolate_adapter_inputs: bool = False,
    ) -> RankingResponse:
        # --- Scoring ---
        t1 = _time.perf_counter()
        scored: List[Dict[str, Any]] = []
        for item in candidates:
            adapter_constraints = (
                self._snapshot_mapping(constraints, name="constraints")
                if isolate_adapter_inputs
                else constraints
            )
            adapter_intent = (
                self._snapshot_mapping(
                    resolved_intent,
                    name="resolved_intent",
                )
                if isolate_adapter_inputs
                else resolved_intent
            )
            constraint_item = (
                self._snapshot_item(item, path="candidate")
                if isolate_adapter_inputs
                else item
            )
            multiplier_item = (
                self._snapshot_item(item, path="candidate")
                if isolate_adapter_inputs
                else item
            )
            blocked = adapter.apply_hard_constraints(
                constraint_item,
                adapter_constraints,
            )
            multipliers = adapter.compute_multipliers(
                multiplier_item,
                adapter_intent,
            )
            if isolate_adapter_inputs:
                if not isinstance(blocked, bool):
                    raise TypeError(
                        "adapter hard-constraint result must be a bool"
                    )
                if not isinstance(multipliers, MultiplierSet):
                    raise TypeError(
                        "adapter multiplier result must be a MultiplierSet"
                    )
                try:
                    multipliers = MultiplierSet.model_validate(
                        multipliers.model_dump(mode="python")
                    )
                except Exception as exc:
                    raise TypeError(
                        "adapter multiplier result failed validation"
                    ) from exc
                for field_name in (
                    "context",
                    "profile",
                    "urgency",
                    "cost",
                    "prophecy",
                ):
                    value = getattr(multipliers, field_name)
                    if not math.isfinite(value) or value < 0:
                        raise TypeError(
                            "adapter multipliers must be finite and nonnegative"
                        )

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
                if isolate_adapter_inputs and not math.isfinite(raw_score):
                    raise ValueError("resolved ranking score must be finite")
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
            diversity_item = (
                self._snapshot_item(entry["item"], path="candidate")
                if isolate_adapter_inputs
                else entry["item"]
            )
            key = adapter.diversity_key(diversity_item)
            if isolate_adapter_inputs and not isinstance(key, str):
                raise TypeError("adapter diversity key must be a string")
            count = seen_keys.get(key, 0)
            penalty = DIVERSITY_PENALTY * count if count > 0 else 0.0
            final_score = max(0.0, entry["final_score"] + penalty)
            if isolate_adapter_inputs and not math.isfinite(final_score):
                raise ValueError("resolved ranking score must be finite")
            entry["final_score"] = final_score
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

            explanation_item = (
                self._snapshot_item(item, path="candidate")
                if isolate_adapter_inputs
                else item
            )
            explanation_multipliers = (
                MultiplierSet.model_validate(mults.model_dump(mode="python"))
                if isolate_adapter_inputs
                else mults
            )
            explanation = adapter.explain(
                explanation_item,
                explanation_multipliers,
            )
            if isolate_adapter_inputs and not isinstance(explanation, str):
                raise TypeError("adapter explanation must be a string")

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

        total_ms = intent_parsing_ms + t_ranking + t_diversity
        latency = LatencyBreakdown(
            total_ms=total_ms,
            intent_parsing_ms=intent_parsing_ms,
            ranking_ms=t_ranking,
            diversity_check_ms=t_diversity,
        )

        return RankingResponse(
            ranked_items=ranked_items,
            latency=latency,
            intent=response_intent,
            domain=domain,
            mode_used=mode_used,
        )
