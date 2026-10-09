"""Discover pilot configuration and provider wiring (spec sections 8, 18, 21).

Centralizes environment-based configuration — API keys, per-provider timeout and
result caps (cost controls, §21), and the optional LLM gateway — and builds the
provider list. Missing keys degrade gracefully: a provider with no key is simply
not constructed, so the pilot runs on whatever providers are configured and only
errors when *none* are available (handled upstream as a retrieval error, §18).
Secrets are never logged or echoed.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import List, Optional

from intent_engine.discover.providers.base import HttpTransport, HttpxTransport
from intent_engine.discover.providers.fixtures import FixtureProvider
from intent_engine.discover.providers.google_places import GooglePlacesProvider
from intent_engine.discover.providers.ticketmaster import TicketmasterProvider
from intent_engine.discover.service import SearchProvider

_DEFAULT_TIMEOUT = 5.0
_DEFAULT_MAX_RESULTS = 20
_DEFAULT_RETENTION_DAYS = 30


def _is_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class ConfigError(ValueError):
    """Invalid Discover configuration."""


@dataclass(frozen=True)
class DiscoverConfig:
    ticketmaster_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    provider_timeout_seconds: float = _DEFAULT_TIMEOUT
    max_results: int = _DEFAULT_MAX_RESULTS
    llm_gateway_url: Optional[str] = None
    feedback_retention_days: int = _DEFAULT_RETENTION_DAYS
    demo_mode: bool = False

    @property
    def llm_enabled(self) -> bool:
        """LLM-only evaluation arm is available only with a configured gateway."""
        return bool(self.llm_gateway_url)

    @property
    def configured_providers(self) -> List[str]:
        names = []
        if self.ticketmaster_api_key:
            names.append("ticketmaster")
        if self.google_places_api_key:
            names.append("google_places")
        return names

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "DiscoverConfig":
        env = os.environ if env is None else env

        def _clean(value: Optional[str]) -> Optional[str]:
            value = (value or "").strip()
            return value or None

        timeout_raw = env.get("DISCOVER_PROVIDER_TIMEOUT", str(_DEFAULT_TIMEOUT))
        max_results_raw = env.get("DISCOVER_MAX_RESULTS", str(_DEFAULT_MAX_RESULTS))
        retention_raw = env.get("DISCOVER_FEEDBACK_RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS))
        try:
            timeout = float(timeout_raw)
            max_results = int(max_results_raw)
            retention = int(retention_raw)
        except ValueError as exc:
            raise ConfigError(f"invalid numeric Discover config: {exc}") from exc

        if not math.isfinite(timeout) or timeout <= 0:
            raise ConfigError("DISCOVER_PROVIDER_TIMEOUT must be a finite positive number")
        if not 1 <= max_results <= 200:
            raise ConfigError("DISCOVER_MAX_RESULTS must be between 1 and 200")
        if retention < 0:
            raise ConfigError("DISCOVER_FEEDBACK_RETENTION_DAYS must be >= 0")

        return cls(
            ticketmaster_api_key=_clean(env.get("TICKETMASTER_API_KEY")),
            google_places_api_key=_clean(env.get("GOOGLE_PLACES_API_KEY")),
            provider_timeout_seconds=timeout,
            max_results=max_results,
            llm_gateway_url=_clean(env.get("DISCOVER_LLM_GATEWAY_URL")),
            feedback_retention_days=retention,
            demo_mode=_is_truthy(env.get("DISCOVER_DEMO_MODE")),
        )


def build_providers(
    config: DiscoverConfig, *, transport: Optional[HttpTransport] = None
) -> List[SearchProvider]:
    """Build the provider list.

    In demo mode, return the offline FixtureProvider (no keys/network needed).
    Otherwise construct only the live providers that have a configured API key.
    """
    if config.demo_mode:
        return [FixtureProvider()]
    transport = transport or HttpxTransport()
    providers: List[SearchProvider] = []
    if config.ticketmaster_api_key:
        providers.append(TicketmasterProvider(
            transport=transport, api_key=config.ticketmaster_api_key,
            timeout=config.provider_timeout_seconds, max_results=config.max_results))
    if config.google_places_api_key:
        providers.append(GooglePlacesProvider(
            transport=transport, api_key=config.google_places_api_key,
            timeout=config.provider_timeout_seconds, max_results=config.max_results))
    return providers
