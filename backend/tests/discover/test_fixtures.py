"""Fixture provider + demo-mode tests (offline, no keys)."""

import asyncio
from datetime import datetime, timezone

from intent_engine.discover.config import DiscoverConfig, build_providers
from intent_engine.discover.providers.fixtures import FixtureProvider, demo_candidates
from intent_engine.discover.schemas import DiscoveryRequest, EvidenceStatus
from intent_engine.discover.service import discover

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _run(request):
    return asyncio.run(discover(request, [FixtureProvider(clock=lambda: NOW)]))


def test_demo_mode_config_selects_fixture_provider():
    cfg = DiscoverConfig.from_env({"DISCOVER_DEMO_MODE": "true"})
    assert cfg.demo_mode is True
    providers = build_providers(cfg)
    assert [p.name for p in providers] == ["fixture"]


def test_demo_mode_needs_no_api_keys():
    # Demo mode wins even with no keys configured (would otherwise be empty).
    cfg = DiscoverConfig.from_env({"DISCOVER_DEMO_MODE": "1"})
    assert build_providers(cfg)  # non-empty


def test_fixture_candidates_keep_provenance_discipline():
    cands = {c.candidate_id: c for c in demo_candidates(NOW)}
    science = cands["ticketmaster:TM-SCI"]
    assert science.evidence("price_min").status is EvidenceStatus.VERIFIED
    assert science.evidence("price_basis").status is EvidenceStatus.UNKNOWN  # honest unknown
    assert science.evidence("description").status is EvidenceStatus.EXTRACTED
    comedy = cands["ticketmaster:TM-COM"]
    assert comedy.evidence("age_min").status is EvidenceStatus.VERIFIED
    assert comedy.verified_value("age_min") == 18


def test_demo_pipeline_excludes_age_gated_event_for_children():
    resp = _run(DiscoveryRequest(query="family museum", children_ages=[6]))
    ids = [r.candidate_id for r in resp.results]
    assert "ticketmaster:TM-COM" not in ids           # 18+ fails the min-age gate
    assert resp.excluded_count >= 1


def test_demo_pipeline_includes_age_gated_event_without_children():
    resp = _run(DiscoveryRequest(query="comedy"))
    assert "ticketmaster:TM-COM" in [r.candidate_id for r in resp.results]


def test_demo_pipeline_is_ranked_explained_and_deterministic():
    a = _run(DiscoveryRequest(query="science museum"))
    b = _run(DiscoveryRequest(query="science museum"))
    assert a.ranking_fingerprint == b.ranking_fingerprint
    assert [r.rank for r in a.results] == list(range(1, len(a.results) + 1))
    assert all(r.explanation.text for r in a.results)
