"""Discover pipeline orchestration (spec sections 9, 14).

Composes the independently-tested stages into one request→response flow:

    retrieve (providers) → deduplicate → hard constraints → rank → explain

Retrieval runs the providers concurrently and tolerates partial failure: if one
provider fails the others' results are returned with a warning; if *every*
provider fails, a ``RetrievalError`` is raised rather than fabricating results
(spec §9, §18). The response is a typed, display-ready view whose grounded
``ExplanationClaim``s carry the evidence (spec §13.1); scalar fields are a
convenience view only.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from intent_engine.discover.constraints import filter_candidates
from intent_engine.discover.explain import explain
from intent_engine.discover.normalization import deduplicate_candidates
from intent_engine.discover.providers.base import ProviderError
from intent_engine.discover.ranking import ENGINE_VERSION, rank_candidates
from intent_engine.discover.schemas import (
    DiscoveryCandidate,
    DiscoveryRequest,
    ExplanationClaim,
)

logger = logging.getLogger("intent_engine.discover.service")


class RetrievalError(RuntimeError):
    """Every provider failed; no candidates could be retrieved (spec §18)."""


class SearchProvider(Protocol):
    name: str

    async def search(self, request: DiscoveryRequest) -> List[DiscoveryCandidate]: ...


# ---------------------------------------------------------------------------
# Response contracts (spec §13, §14)
# ---------------------------------------------------------------------------

class ExplanationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    claims: List[ExplanationClaim]


class DiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    rank: int
    title: str
    source_url: str
    provider: str
    category: Optional[str] = None
    location_name: Optional[str] = None
    start_time: Optional[datetime] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    currency: Optional[str] = None
    final_score: float
    status: str
    needs_verification: bool
    signals: Dict[str, float]
    constraints: Dict[str, str]
    explanation: ExplanationView


class DiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: List[DiscoveryResult] = Field(default_factory=list)
    needs_verification_ids: List[str] = Field(default_factory=list)
    excluded_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    ranking_fingerprint: str = ""
    engine_version: str = ENGINE_VERSION
    config_version: str = "default"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def retrieve_candidates(
    request: DiscoveryRequest, providers: Sequence[SearchProvider]
) -> Tuple[List[DiscoveryCandidate], List[str]]:
    """Gather candidates from all providers concurrently (spec §9).

    Returns (candidates, warnings). Raises ``RetrievalError`` only if every
    provider failed. A provider that raises a non-``ProviderError`` is a bug and
    is propagated.
    """
    if not providers:
        raise RetrievalError("no providers configured")

    outcomes = await asyncio.gather(
        *(provider.search(request) for provider in providers),
        return_exceptions=True,
    )

    candidates: List[DiscoveryCandidate] = []
    warnings: List[str] = []
    failures = 0
    for provider, outcome in zip(providers, outcomes):
        if isinstance(outcome, ProviderError):
            failures += 1
            warnings.append(f"{provider.name}: {type(outcome).__name__}")
            logger.warning("provider_failed provider=%s error=%s",
                           provider.name, type(outcome).__name__)
        elif isinstance(outcome, BaseException):
            raise outcome  # unexpected: surface the bug
        else:
            candidates.extend(outcome)

    if failures == len(providers):
        raise RetrievalError("all providers failed to return candidates")
    return candidates, warnings


async def discover(
    request: DiscoveryRequest,
    providers: Sequence[SearchProvider],
    *,
    config_version: str = "default",
) -> DiscoveryResponse:
    """Run the full Discover pipeline for one request."""
    candidates, warnings = await retrieve_candidates(request, providers)
    deduped = deduplicate_candidates(candidates)
    ranking = rank_candidates(deduped, request, config_version=config_version)
    by_id = {candidate.candidate_id: candidate for candidate in deduped}

    results: List[DiscoveryResult] = []
    for ranked in ranking.ranked:
        candidate = by_id[ranked.candidate_id]
        explanation = explain(ranked)
        results.append(DiscoveryResult(
            candidate_id=ranked.candidate_id,
            rank=ranked.rank,
            title=candidate.title,
            source_url=candidate.source_url,
            provider=candidate.provider,
            category=candidate.category,
            location_name=candidate.location_name,
            start_time=candidate.start_time,
            price_min=candidate.price_min,
            price_max=candidate.price_max,
            currency=candidate.currency,
            final_score=ranked.final_score,
            status=ranked.status,
            needs_verification=ranked.needs_verification,
            signals=ranked.signals,
            constraints=ranked.constraint_states,
            explanation=ExplanationView(text=explanation.text, claims=explanation.claims),
        ))

    return DiscoveryResponse(
        results=results,
        needs_verification_ids=ranking.needs_verification_ids,
        excluded_count=len(ranking.excluded_ids),
        warnings=warnings,
        ranking_fingerprint=ranking.fingerprint,
        engine_version=ranking.engine_version,
        config_version=ranking.config_version,
    )
