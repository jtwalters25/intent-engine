"""Discover config + provider-wiring tests (spec sections 8, 18, 21)."""

import pytest

from intent_engine.discover.config import (
    ConfigError,
    DiscoverConfig,
    build_providers,
)


def test_from_env_reads_keys_and_limits():
    cfg = DiscoverConfig.from_env({
        "TICKETMASTER_API_KEY": "tm-key",
        "GOOGLE_PLACES_API_KEY": "gp-key",
        "DISCOVER_PROVIDER_TIMEOUT": "3.5",
        "DISCOVER_MAX_RESULTS": "10",
        "DISCOVER_LLM_GATEWAY_URL": "https://gw.example.com",
    })
    assert cfg.provider_timeout_seconds == 3.5
    assert cfg.max_results == 10
    assert cfg.llm_enabled is True
    assert cfg.configured_providers == ["ticketmaster", "google_places"]


def test_defaults_when_env_empty():
    cfg = DiscoverConfig.from_env({})
    assert cfg.max_results == 20
    assert cfg.llm_enabled is False
    assert cfg.configured_providers == []


def test_blank_keys_are_treated_as_absent():
    cfg = DiscoverConfig.from_env({"TICKETMASTER_API_KEY": "   "})
    assert cfg.ticketmaster_api_key is None
    assert cfg.configured_providers == []


@pytest.mark.parametrize("env", [
    {"DISCOVER_PROVIDER_TIMEOUT": "0"},
    {"DISCOVER_PROVIDER_TIMEOUT": "-1"},
    {"DISCOVER_PROVIDER_TIMEOUT": "nan"},
    {"DISCOVER_MAX_RESULTS": "0"},
    {"DISCOVER_MAX_RESULTS": "500"},
    {"DISCOVER_MAX_RESULTS": "abc"},
    {"DISCOVER_FEEDBACK_RETENTION_DAYS": "-1"},
])
def test_invalid_config_rejected(env):
    with pytest.raises(ConfigError):
        DiscoverConfig.from_env(env)


def test_build_providers_only_for_configured_keys():
    class FakeTransport:
        async def get(self, url, *, params, timeout):  # pragma: no cover
            raise AssertionError("not called in this test")

    transport = FakeTransport()
    both = build_providers(DiscoverConfig(ticketmaster_api_key="a",
                                          google_places_api_key="b"), transport=transport)
    assert [p.name for p in both] == ["ticketmaster", "google_places"]

    one = build_providers(DiscoverConfig(ticketmaster_api_key="a"), transport=transport)
    assert [p.name for p in one] == ["ticketmaster"]

    none = build_providers(DiscoverConfig(), transport=transport)
    assert none == []


def test_build_providers_passes_limits():
    class FakeTransport:
        async def get(self, url, *, params, timeout):  # pragma: no cover
            raise AssertionError("not called")

    providers = build_providers(
        DiscoverConfig(ticketmaster_api_key="a", provider_timeout_seconds=2.0, max_results=7),
        transport=FakeTransport())
    assert providers[0]._timeout == 2.0
    assert providers[0]._max_results == 7
