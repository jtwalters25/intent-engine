"""Candidate normalization / deduplication tests (spec section 9)."""

from datetime import datetime, timezone

from intent_engine.discover.normalization import (
    deduplicate_candidates,
    normalize_title,
)
from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    EvidenceStatus,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _prov(value, source_field="field"):
    return AttributeProvenance(
        value=value, status=EvidenceStatus.VERIFIED, source="test",
        source_url="https://example.com/e", retrieved_at=NOW, source_field=source_field,
    )


def _candidate(cid, provider="p1", title="The Science Museum", provenance=None, **scalars):
    base = dict(
        candidate_id=cid, provider=provider, provider_id=cid,
        title=title, source_url="https://example.com/e", retrieved_at=NOW,
    )
    base.update(scalars)
    cand = DiscoveryCandidate(**base)
    if provenance:
        cand.provenance = provenance
    return cand


def test_normalize_title_collapses_case_punct_space():
    assert normalize_title("  The  SCIENCE-Museum!! ") == "the science museum"


def test_exact_id_duplicate_collapses():
    a = _candidate("dup", latitude=47.6, longitude=-122.3)
    b = _candidate("dup", latitude=47.6, longitude=-122.3)
    result = deduplicate_candidates([a, b])
    assert len(result) == 1


def test_cross_provider_merge_adds_missing_verified_attribute():
    # Same title + same coarse coords, no date. Both mergeable.
    a = _candidate(
        "p1:1", provider="p1", latitude=47.600, longitude=-122.300,
        location_name="123 Main St",
        provenance={
            "latitude": _prov(47.600), "longitude": _prov(-122.300),
            "location_name": _prov("123 Main St"),
        },
    )
    b = _candidate(
        "p2:9", provider="p2", latitude=47.6004, longitude=-122.3001,
        category="museum",
        provenance={
            "latitude": _prov(47.6004), "longitude": _prov(-122.3001),
            "category": _prov("museum"),
        },
    )
    result = deduplicate_candidates([a, b])

    assert len(result) == 1
    primary = result[0]
    # Tie on verified count (3 each) -> provider "p1" wins deterministically.
    assert primary.candidate_id == "p1:1"
    # The verified category from p2 is lifted onto the primary, with its own provenance.
    assert primary.category == "museum"
    assert primary.provenance["category"].source == "test"
    assert primary.attributes["merged_from"] == ["p2:9"]


def test_merge_never_overwrites_verified_value():
    a = _candidate(
        "p1:1", provider="p1", latitude=47.6, longitude=-122.3, category="aquarium",
        provenance={
            "latitude": _prov(47.6), "longitude": _prov(-122.3),
            "category": _prov("aquarium"),
        },
    )
    b = _candidate(
        "p2:2", provider="p2", latitude=47.6, longitude=-122.3, category="museum",
        provenance={
            "latitude": _prov(47.6), "longitude": _prov(-122.3),
            "category": _prov("museum"),
        },
    )
    result = deduplicate_candidates([a, b])
    assert len(result) == 1
    assert result[0].category == "aquarium"  # primary's verified value preserved


def test_distinct_titles_not_merged():
    a = _candidate("p1:1", title="Science Museum", latitude=47.6, longitude=-122.3,
                   provenance={"latitude": _prov(47.6)})
    b = _candidate("p1:2", title="Art Museum", latitude=47.6, longitude=-122.3,
                   provenance={"latitude": _prov(47.6)})
    assert len(deduplicate_candidates([a, b])) == 2


def test_title_only_collision_not_merged():
    # No date and no coords -> not safely mergeable even with identical titles.
    a = _candidate("p1:1")
    b = _candidate("p2:2", provider="p2")
    assert len(deduplicate_candidates([a, b])) == 2


def test_same_title_different_date_not_merged():
    d1 = datetime(2026, 10, 10, 19, tzinfo=timezone.utc)
    d2 = datetime(2026, 10, 11, 19, tzinfo=timezone.utc)
    a = _candidate("p1:1", start_time=d1, provenance={"start_time": _prov(d1)})
    b = _candidate("p1:2", start_time=d2, provenance={"start_time": _prov(d2)})
    assert len(deduplicate_candidates([a, b])) == 2


def test_dedupe_is_order_preserving_and_idempotent():
    a = _candidate("p1:1", title="Alpha", latitude=1.0, longitude=1.0,
                   provenance={"latitude": _prov(1.0)})
    b = _candidate("p1:2", title="Beta", latitude=2.0, longitude=2.0,
                   provenance={"latitude": _prov(2.0)})
    once = deduplicate_candidates([a, b])
    twice = deduplicate_candidates(once)
    assert [c.candidate_id for c in once] == ["p1:1", "p1:2"]
    assert [c.candidate_id for c in twice] == [c.candidate_id for c in once]
