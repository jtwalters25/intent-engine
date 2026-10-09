"""Executable evidence & evaluation contracts for Intent Engine Discover.

Reference implementation of the typed records in the Discover pilot spec
(sections 7.1, 13.1, 16, 16.1). It is deliberately self-contained: the metrics
layer can be built and tested in isolation, with no dependency on providers,
retrieval, or the ranker.

Integration seam: when the Discover module's Phase-1 schemas land
(``discover/schemas.py`` per spec sections 6-7), ``AttributeProvenance`` and
``ExplanationClaim`` here should become the canonical definitions imported from
there rather than duplicated. This module intentionally does NOT define the full
``DiscoveryCandidate``; it uses a minimal ``CandidateSnapshot`` evidence view.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from intent_engine.discover.schemas import (
    AttributeProvenance,
    ConstraintState,
    EvidenceStatus,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
# EvidenceStatus, ConstraintState, and AttributeProvenance are imported from
# discover.schemas (their canonical home) and re-exported here so existing
# ``evaluation.contracts`` / ``evaluation`` import paths keep working.

class ClaimKind(str, Enum):
    MATCH = "match"
    TRADEOFF = "tradeoff"
    CAVEAT = "caveat"


class PriceBasis(str, Enum):
    PER_PERSON = "per_person"
    PER_TICKET = "per_ticket"
    PER_GROUP = "per_group"
    TOTAL = "total"
    UNKNOWN = "unknown"


# Canonical evaluation arm names.
ARM_RELEVANCE = "relevance"
ARM_LLM_ONLY = "llm_only"
ARM_INTENT_ENGINE = "intent_engine"


# ---------------------------------------------------------------------------
# Evidence contracts (sections 7.1, 13.1)
# ---------------------------------------------------------------------------
# AttributeProvenance is imported from discover.schemas (canonical) above.

class CandidateSnapshot(BaseModel):
    """Minimal evidence view of a candidate used by evaluation.

    The full DiscoveryCandidate (spec section 7) lives in discover/schemas.py.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    attributes: Dict[str, AttributeProvenance] = Field(default_factory=dict)


class ExplanationClaim(BaseModel):
    """One atomic, grounded claim within an explanation (section 13.1)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    kind: ClaimKind
    attribute: str = Field(..., min_length=1)
    evidence_status: EvidenceStatus
    signal: Optional[str] = None

    @model_validator(mode="after")
    def caveat_requires_uncertainty(self) -> "ExplanationClaim":
        # A match/tradeoff presented about a VERIFIED attribute is a fact claim;
        # a caveat must rest on something NOT verified (UNKNOWN or EXTRACTED).
        if self.kind is ClaimKind.CAVEAT and self.evidence_status is EvidenceStatus.VERIFIED:
            raise ValueError("a caveat cannot rest on a VERIFIED attribute")
        return self


class AssertedFact(BaseModel):
    """A value an arm presents to the user, with how strongly it is asserted.

    Factual-error scoring (section 16) compares these against ground truth. An
    arm that only asserts VERIFIED facts it actually holds cannot produce a
    critical factual error; an arm that confidently states inferred values can.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    attribute: str = Field(..., min_length=1)
    asserted_value: Any
    asserted_as: EvidenceStatus


# ---------------------------------------------------------------------------
# Ground truth & stated constraints (section 16)
# ---------------------------------------------------------------------------

class StatedConstraints(BaseModel):
    """The evaluable subset of a DiscoveryRequest's hard constraints."""

    model_config = ConfigDict(extra="forbid")

    budget_total: Optional[Decimal] = None
    party_size: Optional[int] = Field(default=None, ge=1)
    children_ages: List[int] = Field(default_factory=list)
    max_distance_minutes: Optional[float] = Field(default=None, ge=0)
    date_window_required: bool = False


class GroundTruthLabel(BaseModel):
    """Human-verified truth for one candidate, resolved against its source URL."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    verified_price_basis: PriceBasis = PriceBasis.UNKNOWN
    verified_total_cost: Optional[Decimal] = None
    verified_within_date_window: Optional[bool] = None
    verified_min_age: Optional[int] = None
    verified_distance_minutes: Optional[float] = None
    verified_at: datetime
    verifier: str = Field(..., min_length=1)
    # Extensible: other verified attributes (e.g. {"age_appropriate": true}).
    verified_attributes: Dict[str, Any] = Field(default_factory=dict)

    def truth_for(self, attribute: str) -> "tuple[bool, Any]":
        """Return (has_opinion, value) for an attribute name used in assertions."""
        specific = {
            "price_total": self.verified_total_cost,
            "within_date_window": self.verified_within_date_window,
            "min_age": self.verified_min_age,
            "distance_minutes": self.verified_distance_minutes,
        }
        if attribute in specific:
            value = specific[attribute]
            return (value is not None, value)
        if attribute in self.verified_attributes:
            return (True, self.verified_attributes[attribute])
        return (False, None)


# ---------------------------------------------------------------------------
# Arm result and session (section 16.1 evidence ledger)
# ---------------------------------------------------------------------------

class HumanRatings(BaseModel):
    """Human-collected secondary endpoints for one arm in one session."""

    model_config = ConfigDict(extra="forbid")

    top5_relevance: Optional[float] = Field(default=None, ge=1, le=5)
    preferred: Optional[bool] = None
    time_to_useful_seconds: Optional[float] = Field(default=None, ge=0)


class ArmResult(BaseModel):
    """One ranking arm's output for one session."""

    model_config = ConfigDict(extra="forbid")

    ranking: List[str] = Field(default_factory=list)
    explanations: Dict[str, List[ExplanationClaim]] = Field(default_factory=dict)
    asserted_facts: List[AssertedFact] = Field(default_factory=list)
    ranking_fingerprint: Optional[str] = None
    ratings: Optional[HumanRatings] = None
    metrics: Dict[str, float] = Field(default_factory=dict)


class EvaluationSession(BaseModel):
    """Immutable per-session evidence ledger (spec section 16.1)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1)
    validated_intent: Dict[str, Any] = Field(default_factory=dict)
    candidate_pool: List[CandidateSnapshot] = Field(default_factory=list)
    stated_constraints: StatedConstraints = Field(default_factory=StatedConstraints)
    arms: Dict[str, ArmResult] = Field(default_factory=dict)
    ground_truth: List[GroundTruthLabel] = Field(default_factory=list)
    presentation_order: List[str] = Field(default_factory=list)
    engine_version: str = "unknown"
    config_version: str = "unknown"
    created_at: Optional[datetime] = None

    def ground_truth_by_id(self) -> Dict[str, GroundTruthLabel]:
        return {label.candidate_id: label for label in self.ground_truth}

    @property
    def pool_fingerprint(self) -> str:
        return pool_fingerprint(self.candidate_pool)


# ---------------------------------------------------------------------------
# Deterministic fingerprints (section 16.1)
# ---------------------------------------------------------------------------

def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,  # Decimal / datetime -> stable string form
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pool_fingerprint(pool: List[CandidateSnapshot]) -> str:
    """Stable hash of the normalized candidate pool (order-independent)."""
    normalized = sorted(
        (candidate.model_dump(mode="json") for candidate in pool),
        key=lambda item: item["candidate_id"],
    )
    return _sha256(_canonical_json(normalized))


def ranking_fingerprint(
    *,
    validated_intent: Dict[str, Any],
    pool_fingerprint: str,
    config_version: str,
    engine_version: str,
) -> str:
    """Hash over the inputs that MUST reproduce an identical ranking.

    Excludes latency, trace_id, wall-clock timestamps, and presentation order,
    matching the V4 determinism contract and the security plan's replay set.
    """
    return _sha256(
        _canonical_json(
            {
                "validated_intent": validated_intent,
                "pool_fingerprint": pool_fingerprint,
                "config_version": config_version,
                "engine_version": engine_version,
            }
        )
    )
