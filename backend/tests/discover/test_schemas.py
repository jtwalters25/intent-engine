"""Phase-1 schema validation tests (spec sections 6, 7, 7.1, 17).

Contract-focused: assert the validation rules and the "missing stays missing"
evidence discipline, not incidental representation details.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryFeedback,
    DiscoveryRequest,
    EvidenceStatus,
    Helpfulness,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# DiscoveryRequest (section 6)
# ---------------------------------------------------------------------------

def test_minimal_request_is_valid():
    req = DiscoveryRequest(query="something fun for the kids")
    assert req.query == "something fun for the kids"
    assert req.children_ages == []
    assert req.has_precise_location is False


def test_full_request_example_from_spec():
    req = DiscoveryRequest(
        query="Find something educational and fun for my kids this Saturday",
        location="Seattle, WA",
        budget_total=Decimal("100.00"),
        party_size=5,
        children_ages=[7, 9, 10, 12],
        duration_minutes=180,
    )
    assert req.budget_total == Decimal("100.00")
    assert req.party_size == 5


def test_query_must_not_be_blank():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="   ")


def test_query_required():
    with pytest.raises(ValidationError):
        DiscoveryRequest()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "lat,lon",
    [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
)
def test_out_of_range_coordinates_rejected(lat, lon):
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", latitude=lat, longitude=lon)


def test_half_specified_location_rejected():
    # Do not silently infer precise location (section 6).
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", latitude=47.6)
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", longitude=-122.3)


def test_both_coordinates_ok():
    req = DiscoveryRequest(query="x", latitude=47.6, longitude=-122.3)
    assert req.has_precise_location is True


def test_negative_budget_rejected():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", budget_total=Decimal("-1"))


def test_party_size_must_be_positive():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", party_size=0)


def test_children_age_out_of_range_rejected():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", children_ages=[5, 25])


def test_end_date_before_start_date_rejected():
    with pytest.raises(ValidationError):
        DiscoveryRequest(
            query="x",
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 9),
        )


def test_duration_must_be_positive():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", duration_minutes=0)


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        DiscoveryRequest(query="x", smuggled="value")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# AttributeProvenance (section 7.1)
# ---------------------------------------------------------------------------

def test_verified_requires_source_field():
    with pytest.raises(ValidationError):
        AttributeProvenance(
            value=Decimal("25.00"),
            status=EvidenceStatus.VERIFIED,
            source="ticketmaster",
            source_url="https://example.com/e",
            retrieved_at=NOW,
        )


def test_verified_with_source_field_ok():
    prov = AttributeProvenance(
        value=Decimal("25.00"),
        status=EvidenceStatus.VERIFIED,
        source="ticketmaster",
        source_url="https://example.com/e",
        retrieved_at=NOW,
        source_field="priceRanges",
    )
    assert prov.is_fact is True


def test_extracted_requires_extractor():
    with pytest.raises(ValidationError):
        AttributeProvenance(
            value="kid friendly",
            status=EvidenceStatus.EXTRACTED,
            source="google_places",
            source_url="https://example.com/p",
            retrieved_at=NOW,
        )


def test_extracted_is_not_fact():
    prov = AttributeProvenance(
        value="kid friendly",
        status=EvidenceStatus.EXTRACTED,
        source="google_places",
        source_url="https://example.com/p",
        retrieved_at=NOW,
        extractor="classifier-v1",
    )
    assert prov.is_fact is False


def test_unknown_must_not_carry_value():
    with pytest.raises(ValidationError):
        AttributeProvenance(
            value="anything",
            status=EvidenceStatus.UNKNOWN,
            source="google_places",
            source_url="https://example.com/p",
            retrieved_at=NOW,
        )


def test_non_unknown_requires_value():
    with pytest.raises(ValidationError):
        AttributeProvenance(
            value=None,
            status=EvidenceStatus.VERIFIED,
            source="ticketmaster",
            source_url="https://example.com/e",
            retrieved_at=NOW,
            source_field="priceRanges",
        )


# ---------------------------------------------------------------------------
# DiscoveryCandidate (sections 7, 7.1)
# ---------------------------------------------------------------------------

def _candidate(**overrides) -> DiscoveryCandidate:
    base = dict(
        candidate_id="c1",
        provider="ticketmaster",
        provider_id="TM123",
        title="Family Science Experience",
        source_url="https://example.com/event/TM123",
        retrieved_at=NOW,
    )
    base.update(overrides)
    return DiscoveryCandidate(**base)


def test_minimal_candidate_is_valid():
    cand = _candidate()
    assert cand.title == "Family Science Experience"
    assert cand.attributes == {}
    assert cand.provenance == {}


def test_missing_price_stays_missing_not_free():
    # Unknown price must not be coerced to 0/free (section 7).
    cand = _candidate()
    assert cand.price_min is None
    assert cand.price_max is None
    assert cand.verified_value("price_total") is None
    assert cand.evidence("price_total") is None


def test_missing_age_is_not_all_ages():
    cand = _candidate()
    assert cand.age_min is None
    assert cand.is_verified("min_age") is False


def test_price_max_below_min_rejected():
    with pytest.raises(ValidationError):
        _candidate(price_min=Decimal("50"), price_max=Decimal("10"))


def test_age_max_below_min_rejected():
    with pytest.raises(ValidationError):
        _candidate(age_min=10, age_max=5)


def test_end_time_before_start_time_rejected():
    with pytest.raises(ValidationError):
        _candidate(
            start_time=datetime(2026, 10, 10, 18, tzinfo=timezone.utc),
            end_time=datetime(2026, 10, 10, 17, tzinfo=timezone.utc),
        )


def test_verified_value_returns_only_verified():
    verified = AttributeProvenance(
        value=Decimal("25.00"),
        status=EvidenceStatus.VERIFIED,
        source="ticketmaster",
        source_url="https://example.com/e",
        retrieved_at=NOW,
        source_field="priceRanges",
    )
    extracted = AttributeProvenance(
        value=8,
        status=EvidenceStatus.EXTRACTED,
        source="google_places",
        source_url="https://example.com/p",
        retrieved_at=NOW,
        extractor="classifier-v1",
    )
    cand = _candidate(provenance={"price_total": verified, "min_age": extracted})

    assert cand.verified_value("price_total") == Decimal("25.00")
    assert cand.is_verified("price_total") is True
    # EXTRACTED must not surface as a verified fact.
    assert cand.verified_value("min_age") is None
    assert cand.is_verified("min_age") is False
    assert cand.evidence("min_age").status is EvidenceStatus.EXTRACTED


def test_source_url_required():
    with pytest.raises(ValidationError):
        DiscoveryCandidate(
            candidate_id="c1",
            provider="ticketmaster",
            provider_id="TM123",
            title="x",
            retrieved_at=NOW,
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# DiscoveryFeedback (section 17)
# ---------------------------------------------------------------------------

def test_feedback_valid():
    fb = DiscoveryFeedback(
        request_id="req-abc",
        selected_candidate_id="c1",
        helpfulness=Helpfulness.VERY_HELPFUL,
        would_use_again=True,
    )
    assert fb.helpfulness is Helpfulness.VERY_HELPFUL


def test_feedback_helpfulness_required():
    with pytest.raises(ValidationError):
        DiscoveryFeedback(request_id="req-abc")  # type: ignore[call-arg]


def test_feedback_rejects_unknown_helpfulness():
    with pytest.raises(ValidationError):
        DiscoveryFeedback(request_id="req-abc", helpfulness="kinda")  # type: ignore[arg-type]
