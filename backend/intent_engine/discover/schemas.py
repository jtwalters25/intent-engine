"""Discover Phase-1 schemas: request, candidate, provenance, feedback.

Reference implementation of the typed contracts in the Discover pilot spec
(sections 6, 7, 7.1, 17). These are pure Pydantic models with validation only —
no providers, retrieval, ranking, or network access — so they are fully
offline-testable and form the foundation every later Discover phase builds on.

Design rules carried from the spec:
- Missing information must remain missing (section 7). Unknown price is NOT free;
  unknown age suitability is NOT "appropriate for all ages". Optional scalar
  fields default to ``None`` and are never coerced.
- Per-attribute provenance is the authoritative evidence record (section 7.1).
  The top-level scalar fields on ``DiscoveryCandidate`` are a convenience/display
  view; ranking, constraints, and explanations must consult ``provenance`` (via
  ``evidence()`` / ``verified_value()``), never a bare scalar.
- All numerical inputs carry sensible validation limits (section 6), and the
  system does not silently infer precise location from a half-specified pair.

Integration seam: ``EvidenceStatus`` and ``AttributeProvenance`` here are the
canonical definitions. ``discover/evaluation/contracts.py`` currently duplicates
them (see its module docstring); a follow-up should make evaluation import from
this module. The definitions here are kept byte-compatible with that copy so the
swap is behavior-preserving.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Evidence provenance (spec section 7.1) — canonical definitions
# ---------------------------------------------------------------------------

class EvidenceStatus(str, Enum):
    """Provenance of a single attribute value (spec section 7.1)."""

    VERIFIED = "VERIFIED"    # copied from a structured provider field
    EXTRACTED = "EXTRACTED"  # inferred from unstructured text / classifier / LLM
    UNKNOWN = "UNKNOWN"      # absent; no value may be asserted


class AttributeProvenance(BaseModel):
    """Where one attribute came from and how trustworthy it is (section 7.1).

    A hard constraint may FAIL only on a VERIFIED attribute; EXTRACTED/UNKNOWN
    route to constraint-state UNKNOWN. An explanation may present an attribute as
    fact only when ``status is VERIFIED``.
    """

    model_config = ConfigDict(extra="forbid")

    value: Optional[Any] = None
    status: EvidenceStatus
    source: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    retrieved_at: datetime
    source_field: Optional[str] = None
    extractor: Optional[str] = None

    @model_validator(mode="after")
    def enforce_status_rules(self) -> "AttributeProvenance":
        if self.status is EvidenceStatus.UNKNOWN:
            if self.value is not None:
                raise ValueError("UNKNOWN attributes must not carry a value")
        else:
            if self.value is None:
                raise ValueError(f"{self.status.value} attributes require a value")
        if self.status is EvidenceStatus.VERIFIED and not self.source_field:
            raise ValueError("VERIFIED attributes require a structured source_field")
        if self.status is EvidenceStatus.EXTRACTED and not self.extractor:
            raise ValueError("EXTRACTED attributes require an extractor id")
        return self

    @property
    def is_fact(self) -> bool:
        """Only VERIFIED attributes may be presented as fact."""
        return self.status is EvidenceStatus.VERIFIED


class ConstraintState(str, Enum):
    """Three-state hard-constraint result (spec section 11).

    Canonical home for the state shared by ``discover.constraints`` (which
    produces it) and ``discover.evaluation`` (which scores against it): FAIL only
    on VERIFIED evidence, UNKNOWN for EXTRACTED/absent evidence, PASS when a
    VERIFIED attribute satisfies the constraint.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ClaimKind(str, Enum):
    """Kind of an atomic explanation claim (spec section 13.1)."""

    MATCH = "match"
    TRADEOFF = "tradeoff"
    CAVEAT = "caveat"


class ExplanationClaim(BaseModel):
    """One atomic, grounded claim within an explanation (spec section 13.1).

    Canonical home shared by the product explainer (`discover.explain`) and the
    evaluation harness (`discover.evaluation`). A claim whose supporting
    attribute is not VERIFIED may not be presented as fact; a caveat must rest on
    something NOT verified (UNKNOWN or EXTRACTED).
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    kind: ClaimKind
    attribute: str = Field(..., min_length=1)
    evidence_status: EvidenceStatus
    signal: Optional[str] = None

    @model_validator(mode="after")
    def caveat_requires_uncertainty(self) -> "ExplanationClaim":
        if self.kind is ClaimKind.CAVEAT and self.evidence_status is EvidenceStatus.VERIFIED:
            raise ValueError("a caveat cannot rest on a VERIFIED attribute")
        return self


# ---------------------------------------------------------------------------
# Discovery request (spec section 6)
# ---------------------------------------------------------------------------

# Sensible validation limits (section 6): numbers are bounded, not open-ended.
_MAX_QUERY_LEN = 500
_MAX_PARTY_SIZE = 50
_MAX_CHILDREN = 20
_MAX_CHILD_AGE = 17
_MAX_DURATION_MINUTES = 1440  # a single day
_MAX_BUDGET_TOTAL = Decimal("1000000.00")


class DiscoveryRequest(BaseModel):
    """A validated user request for discovery (spec section 6).

    Translated downstream into validated V4 intent. Location is accepted as a
    free-text string and/or an explicit lat/long pair; the system never infers a
    precise coordinate from the string alone, and a half-specified coordinate
    (one of lat/long) is rejected rather than silently completed.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=_MAX_QUERY_LEN)
    location: Optional[str] = Field(default=None, max_length=200)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_total: Optional[Decimal] = Field(default=None, ge=0, le=_MAX_BUDGET_TOTAL)
    party_size: Optional[int] = Field(default=None, ge=1, le=_MAX_PARTY_SIZE)
    children_ages: List[int] = Field(default_factory=list)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=_MAX_DURATION_MINUTES)
    request_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @field_validator("children_ages")
    @classmethod
    def children_ages_in_range(cls, ages: List[int]) -> List[int]:
        if len(ages) > _MAX_CHILDREN:
            raise ValueError(f"at most {_MAX_CHILDREN} children ages may be given")
        for age in ages:
            if age < 0 or age > _MAX_CHILD_AGE:
                raise ValueError(f"child age {age} outside 0..{_MAX_CHILD_AGE}")
        return ages

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "DiscoveryRequest":
        # Do not silently infer precise location: require both coords or neither.
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must not be before start_date")
        return self

    @property
    def has_precise_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


# ---------------------------------------------------------------------------
# Unified candidate (spec sections 7, 7.1)
# ---------------------------------------------------------------------------

class DiscoveryCandidate(BaseModel):
    """A provider result normalized into Discover's common representation.

    The scalar fields (``price_min``, ``age_min``, ...) are a convenience/display
    view and may be missing. The authoritative, ranking-relevant record is
    ``provenance`` (section 7.1): downstream phases must read evidence via
    ``evidence()`` / ``verified_value()`` and must never treat a missing scalar
    as a default (free, all-ages, open, etc.).
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    provider_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    retrieved_at: datetime

    description: Optional[str] = None
    category: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    price_min: Optional[Decimal] = Field(default=None, ge=0)
    price_max: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    age_min: Optional[int] = Field(default=None, ge=0, le=120)
    age_max: Optional[int] = Field(default=None, ge=0, le=120)

    # Opaque provider extras (section 7). Free-form; NOT evidence.
    attributes: Dict[str, Any] = Field(default_factory=dict)
    # Authoritative per-attribute evidence (section 7.1).
    provenance: Dict[str, AttributeProvenance] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ranges(self) -> "DiscoveryCandidate":
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_max < self.price_min
        ):
            raise ValueError("price_max must not be below price_min")
        if (
            self.age_min is not None
            and self.age_max is not None
            and self.age_max < self.age_min
        ):
            raise ValueError("age_max must not be below age_min")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError("end_time must not be before start_time")
        return self

    def evidence(self, attribute: str) -> Optional[AttributeProvenance]:
        """Authoritative provenance for an attribute, or None if absent."""
        return self.provenance.get(attribute)

    def is_verified(self, attribute: str) -> bool:
        """True only when the attribute has VERIFIED provenance."""
        prov = self.provenance.get(attribute)
        return prov is not None and prov.status is EvidenceStatus.VERIFIED

    def verified_value(self, attribute: str) -> Optional[Any]:
        """The value of an attribute only if VERIFIED; otherwise None.

        Callers that need to distinguish "verified absent" from "unknown" must
        use ``evidence()`` directly — this helper deliberately collapses every
        non-VERIFIED state to None so a bare value can never leak as a fact.
        """
        prov = self.provenance.get(attribute)
        if prov is not None and prov.status is EvidenceStatus.VERIFIED:
            return prov.value
        return None


# ---------------------------------------------------------------------------
# Feedback telemetry (spec section 17)
# ---------------------------------------------------------------------------

class Helpfulness(str, Enum):
    """Coarse, non-identifying helpfulness rating (spec section 17)."""

    VERY_HELPFUL = "very_helpful"
    SOMEWHAT_HELPFUL = "somewhat_helpful"
    NOT_HELPFUL = "not_helpful"


class DiscoveryFeedback(BaseModel):
    """Minimal, account-free feedback on a recommendation (spec section 17).

    Tracks only what the experiment needs. ``request_id`` is an opaque identifier
    that does not expose identity; free text must not be relied on to carry PII.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(..., min_length=1, max_length=128)
    selected_candidate_id: Optional[str] = Field(default=None, max_length=256)
    helpfulness: Helpfulness
    would_use_again: Optional[bool] = None
    feedback_text: Optional[str] = Field(default=None, max_length=2000)
