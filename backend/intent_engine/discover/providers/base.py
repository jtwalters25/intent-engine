"""Provider adapter foundation (spec sections 8, 9, 18).

Deterministic provider adapters that turn an external API response into
``DiscoveryCandidate`` objects with correct per-attribute provenance. Every
provider shares one template: validate config, issue a single bounded HTTP call,
translate transport/status failures into typed errors, then parse — skipping
malformed items so a partial response still yields safe results.

Transport is injected (``HttpTransport``) so the standard test suite never makes
a live call (spec section 19). ``HttpxTransport`` is the real implementation; it
is intentionally not exercised by the offline suite.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, List, Mapping, Optional, Protocol, Tuple

from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)

logger = logging.getLogger("intent_engine.discover.providers")


# ---------------------------------------------------------------------------
# Typed provider errors (spec section 18)
# ---------------------------------------------------------------------------

class ProviderError(RuntimeError):
    """Base class for all provider failures."""


class ProviderConfigError(ProviderError):
    """Missing/invalid configuration, e.g. an absent API key."""


class ProviderTimeout(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderRateLimited(ProviderError):
    """The provider rejected the call with a rate-limit status (429)."""


class ProviderResponseError(ProviderError):
    """The provider returned an error status or an unparseable body."""


# ---------------------------------------------------------------------------
# Transport seam
# ---------------------------------------------------------------------------

@dataclass
class HttpResponse:
    """Minimal, transport-agnostic view of a completed HTTP response."""

    status_code: int
    payload: Any


class HttpTransport(Protocol):
    """Issues a GET and returns an :class:`HttpResponse`.

    Implementations must raise :class:`TimeoutError` on timeout and
    :class:`ProviderResponseError` when no response can be obtained at all
    (connection/transport failure). A completed response — including 4xx/5xx —
    is returned so the provider owns status-code semantics.
    """

    async def get(
        self, url: str, *, params: Mapping[str, Any], timeout: float
    ) -> HttpResponse: ...


class HttpxTransport:
    """Real httpx-backed transport. Not covered by the offline test suite."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    async def get(
        self, url: str, *, params: Mapping[str, Any], timeout: float
    ) -> HttpResponse:
        import httpx  # lazy: keeps httpx off the import path for offline tests

        try:
            if self._client is not None:
                resp = await self._client.get(url, params=dict(params), timeout=timeout)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=dict(params), timeout=timeout)
        except httpx.TimeoutException as exc:  # pragma: no cover - needs network
            raise TimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - needs network
            raise ProviderResponseError(f"transport error: {exc}") from exc

        try:
            payload = resp.json()
        except Exception:  # pragma: no cover - defensive
            payload = None
        return HttpResponse(status_code=resp.status_code, payload=payload)


Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """Template for a deterministic external provider adapter."""

    #: Human-readable provider id used in candidate.provider and logs.
    name: str = "provider"
    #: Environment variable holding this provider's API key.
    env_key: str = ""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        api_key: Optional[str] = None,
        timeout: float = 5.0,
        max_results: int = 20,
        clock: Clock = _utcnow,
    ) -> None:
        self._transport = transport
        self._api_key = api_key if api_key is not None else os.environ.get(self.env_key)
        self._timeout = timeout
        self._max_results = max_results
        self._clock = clock

    # -- public API --------------------------------------------------------

    async def search(self, request: DiscoveryRequest) -> List[DiscoveryCandidate]:
        """Return normalized candidates for a request, or raise a typed error."""
        self._require_key()
        url, params = self._build_request(request)
        retrieved_at = self._clock()
        try:
            response = await self._transport.get(url, params=params, timeout=self._timeout)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            logger.warning("provider_timeout provider=%s timeout=%s", self.name, self._timeout)
            raise ProviderTimeout(f"{self.name}: request timed out") from exc

        if response.status_code == 429:
            logger.warning("provider_rate_limited provider=%s", self.name)
            raise ProviderRateLimited(f"{self.name}: rate limited (429)")
        if response.status_code >= 400:
            logger.warning(
                "provider_error provider=%s status=%s", self.name, response.status_code
            )
            raise ProviderResponseError(
                f"{self.name}: error status {response.status_code}"
            )

        candidates = list(self._parse(response.payload, request, retrieved_at))
        if len(candidates) > self._max_results:
            candidates = candidates[: self._max_results]
        logger.info(
            "provider_ok provider=%s candidates=%s", self.name, len(candidates)
        )
        return candidates

    # -- hooks for subclasses ---------------------------------------------

    @abstractmethod
    def _build_request(self, request: DiscoveryRequest) -> Tuple[str, dict]:
        """Return (url, query params) for the external call."""

    @abstractmethod
    def _parse(
        self, payload: Any, request: DiscoveryRequest, retrieved_at: datetime
    ) -> Iterable[DiscoveryCandidate]:
        """Translate a successful payload into candidates."""

    # -- shared helpers ----------------------------------------------------

    def _require_key(self) -> str:
        if not self._api_key:
            raise ProviderConfigError(
                f"{self.name}: missing API key (set {self.env_key})"
            )
        return self._api_key

    def _candidate_id(self, provider_id: str) -> str:
        return f"{self.name}:{provider_id}"

    def _safe_items(
        self,
        raw_items: Any,
        build: Callable[[Any], Optional[DiscoveryCandidate]],
    ) -> Iterable[DiscoveryCandidate]:
        """Yield candidates, skipping any item that fails to parse.

        A non-iterable container is treated as a malformed response. Individual
        bad items are logged and dropped (safe partial results, spec section 9).
        """
        if not isinstance(raw_items, list):
            raise ProviderResponseError(f"{self.name}: malformed response body")
        for index, item in enumerate(raw_items):
            try:
                candidate = build(item)
            except Exception as exc:  # noqa: BLE001 - skip one bad item, keep the rest
                logger.warning(
                    "provider_item_skipped provider=%s index=%s error=%s",
                    self.name,
                    index,
                    exc,
                )
                continue
            if candidate is not None:
                yield candidate

    def _verified(
        self,
        value: Any,
        *,
        source_field: str,
        source_url: str,
        retrieved_at: datetime,
    ) -> AttributeProvenance:
        """Provenance for a value copied from a structured provider field."""
        return AttributeProvenance(
            value=value,
            status=EvidenceStatus.VERIFIED,
            source=self.name,
            source_url=source_url,
            retrieved_at=retrieved_at,
            source_field=source_field,
        )

    def _extracted(
        self,
        value: Any,
        *,
        extractor: str,
        source_url: str,
        retrieved_at: datetime,
    ) -> AttributeProvenance:
        """Provenance for a value inferred from unstructured content."""
        return AttributeProvenance(
            value=value,
            status=EvidenceStatus.EXTRACTED,
            source=self.name,
            source_url=source_url,
            retrieved_at=retrieved_at,
            extractor=extractor,
        )
