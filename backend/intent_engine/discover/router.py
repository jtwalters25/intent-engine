"""Discover API endpoints (spec section 14).

A self-contained ``APIRouter`` mounted by the main app with a single
``include_router`` call, mirroring the V4 router. Keeping the surface here (not
in ``api.py``) isolates Discover from the legacy and V4 routes.

Providers are supplied via the ``get_providers`` dependency so tests can inject
mocked providers (no live calls). In production the providers read API keys from
the environment; a missing key surfaces as a retrieval failure, not a crash.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from intent_engine.discover.providers.base import HttpxTransport
from intent_engine.discover.providers.google_places import GooglePlacesProvider
from intent_engine.discover.providers.ticketmaster import TicketmasterProvider
from intent_engine.discover.schemas import DiscoveryFeedback, DiscoveryRequest
from intent_engine.discover.service import (
    DiscoveryResponse,
    RetrievalError,
    SearchProvider,
    discover,
)

logger = logging.getLogger("intent_engine.discover.api")

router = APIRouter(prefix="/discover", tags=["discover"])


def get_providers() -> List[SearchProvider]:
    """Default production providers (real HTTP transport, env-based keys)."""
    transport = HttpxTransport()
    return [
        TicketmasterProvider(transport=transport),
        GooglePlacesProvider(transport=transport),
    ]


@router.post("/search", response_model=DiscoveryResponse)
async def search(
    request: DiscoveryRequest,
    providers: List[SearchProvider] = Depends(get_providers),
) -> DiscoveryResponse:
    try:
        return await discover(request, providers)
    except RetrievalError as exc:
        # No candidates could be retrieved — never fabricate (spec §18).
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/feedback")
async def feedback(payload: DiscoveryFeedback) -> dict:
    # Pilot: validate and log only; no accounts, no PII, no persistence yet (§17).
    logger.info(
        "discover_feedback request_id=%s helpfulness=%s would_use_again=%s",
        payload.request_id, payload.helpfulness.value, payload.would_use_again,
    )
    return {"status": "recorded", "request_id": payload.request_id}
