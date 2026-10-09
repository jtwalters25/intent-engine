"""Three-state hard constraints and eligibility filtering (spec sections 11, 12).

Hard constraints run before ranking. Each (candidate, constraint) resolves to
PASS / FAIL / UNKNOWN:

- FAIL  — a VERIFIED attribute contradicts a stated hard constraint. Excluded.
- PASS  — a VERIFIED attribute satisfies it. Eligible.
- UNKNOWN — the evidence is EXTRACTED/UNKNOWN, or a total cannot be established.
  Never a silent pass and never a confirmed violation.

A candidate is excluded if any check FAILs. Otherwise it is eligible; if any
*stated* check is UNKNOWN it is surfaced separately as "needs verification"
rather than mixed into fully verified recommendations (spec section 11).

Budget (spec section 12): a price range is not a family total. A total is only
established from a VERIFIED price together with a VERIFIED price basis (and party
size for per-person/per-ticket). If the total cannot be established, the budget
check is UNKNOWN — the system never claims an option fits the budget on a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from intent_engine.discover.schemas import (
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)


class ConstraintState(str, Enum):
    """Three-state hard-constraint result (spec section 11).

    Same semantics as ``evaluation.contracts.ConstraintState`` (dedup follow-up:
    both should import one canonical enum once the evaluation suite is touched).
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


# Price-basis values that mean "per participant" (need party size for a total).
_PER_HEAD_BASES = frozenset({"per_person", "per_ticket"})
# Values that already express a group/total figure.
_TOTAL_BASES = frozenset({"total", "per_group"})
# Verified availability values that mean the activity cannot be booked.
_UNAVAILABLE = frozenset({"unavailable", "cancelled", "canceled", "sold_out", "offsale"})


class ConstraintCheck(BaseModel):
    """One hard constraint's result for one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    state: ConstraintState
    stated: bool  # True when the user actually requested this constraint
    detail: str
    evidence_status: Optional[EvidenceStatus] = None


class CandidateConstraintResult(BaseModel):
    """All hard-constraint checks for a single candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    checks: List[ConstraintCheck]

    @property
    def excluded(self) -> bool:
        return any(c.state is ConstraintState.FAIL for c in self.checks)

    @property
    def needs_verification(self) -> bool:
        if self.excluded:
            return False
        return any(
            c.stated and c.state is ConstraintState.UNKNOWN for c in self.checks
        )

    @property
    def fully_verified(self) -> bool:
        if self.excluded:
            return False
        return all(
            c.state is ConstraintState.PASS
            for c in self.checks
            if c.stated
        )

    def failed(self) -> List[ConstraintCheck]:
        return [c for c in self.checks if c.state is ConstraintState.FAIL]


# ---------------------------------------------------------------------------
# Individual constraint checks. Each returns None when not applicable.
# ---------------------------------------------------------------------------

def _verified_value(candidate: DiscoveryCandidate, attribute: str):
    """Return (value) only if the attribute is VERIFIED, else None, plus status."""
    prov = candidate.evidence(attribute)
    if prov is None:
        return None, None
    if prov.status is EvidenceStatus.VERIFIED:
        return prov.value, EvidenceStatus.VERIFIED
    return None, prov.status


def _date_window_check(
    candidate: DiscoveryCandidate, request: DiscoveryRequest
) -> Optional[ConstraintCheck]:
    if request.start_date is None and request.end_date is None:
        return None
    value, status = _verified_value(candidate, "start_time")
    if not isinstance(value, datetime):
        return ConstraintCheck(
            name="date_window",
            state=ConstraintState.UNKNOWN,
            stated=True,
            detail="event date is not verified",
            evidence_status=status,
        )
    event_date = value.date()
    if request.start_date is not None and event_date < request.start_date:
        return ConstraintCheck(
            name="date_window",
            state=ConstraintState.FAIL,
            stated=True,
            detail=f"event {event_date.isoformat()} is before the requested window",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    if request.end_date is not None and event_date > request.end_date:
        return ConstraintCheck(
            name="date_window",
            state=ConstraintState.FAIL,
            stated=True,
            detail=f"event {event_date.isoformat()} is after the requested window",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    return ConstraintCheck(
        name="date_window",
        state=ConstraintState.PASS,
        stated=True,
        detail=f"event {event_date.isoformat()} is within the requested window",
        evidence_status=EvidenceStatus.VERIFIED,
    )


def _party_count(request: DiscoveryRequest) -> Optional[int]:
    if request.party_size is not None:
        return request.party_size
    if request.children_ages:
        return len(request.children_ages)
    return None


def _budget_check(
    candidate: DiscoveryCandidate, request: DiscoveryRequest
) -> Optional[ConstraintCheck]:
    if request.budget_total is None:
        return None
    budget = request.budget_total

    basis_value, basis_status = _verified_value(candidate, "price_basis")
    price_min, price_min_status = _verified_value(candidate, "price_min")

    def unknown(detail: str, status: Optional[EvidenceStatus]) -> ConstraintCheck:
        return ConstraintCheck(
            name="budget",
            state=ConstraintState.UNKNOWN,
            stated=True,
            detail=detail,
            evidence_status=status,
        )

    if not isinstance(basis_value, str) or basis_value == "unknown":
        return unknown("price basis is not verified; total cost unknown", basis_status)
    if not isinstance(price_min, Decimal):
        return unknown("price is not verified; total cost unknown", price_min_status)

    def to_total(amount: Decimal) -> Optional[Decimal]:
        if basis_value in _PER_HEAD_BASES:
            party = _party_count(request)
            if party is None:
                return None
            return amount * party
        if basis_value in _TOTAL_BASES:
            return amount
        return None  # unrecognized basis -> cannot establish a total

    min_total = to_total(price_min)
    if min_total is None:
        return unknown(
            "cannot establish total cost (party size or price basis missing)",
            EvidenceStatus.VERIFIED,
        )

    price_max, _ = _verified_value(candidate, "price_max")
    max_total = to_total(price_max) if isinstance(price_max, Decimal) else min_total
    if max_total is None:
        max_total = min_total

    if min_total > budget:
        return ConstraintCheck(
            name="budget",
            state=ConstraintState.FAIL,
            stated=True,
            detail=f"verified minimum total {min_total} exceeds budget {budget}",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    if max_total <= budget:
        return ConstraintCheck(
            name="budget",
            state=ConstraintState.PASS,
            stated=True,
            detail=f"verified total ({min_total}-{max_total}) fits budget {budget}",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    return ConstraintCheck(
        name="budget",
        state=ConstraintState.UNKNOWN,
        stated=True,
        detail=f"price range ({min_total}-{max_total}) straddles budget {budget}",
        evidence_status=EvidenceStatus.VERIFIED,
    )


def _min_age_check(
    candidate: DiscoveryCandidate, request: DiscoveryRequest
) -> Optional[ConstraintCheck]:
    if not request.children_ages:
        return None
    value, status = _verified_value(candidate, "age_min")
    if not isinstance(value, int) or isinstance(value, bool):
        return ConstraintCheck(
            name="min_age",
            state=ConstraintState.UNKNOWN,
            stated=True,
            detail="minimum age policy is not verified",
            evidence_status=status,
        )
    youngest = min(request.children_ages)
    if youngest < value:
        return ConstraintCheck(
            name="min_age",
            state=ConstraintState.FAIL,
            stated=True,
            detail=f"youngest child ({youngest}) is below the verified minimum age {value}",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    return ConstraintCheck(
        name="min_age",
        state=ConstraintState.PASS,
        stated=True,
        detail=f"all children meet the verified minimum age {value}",
        evidence_status=EvidenceStatus.VERIFIED,
    )


def _availability_check(candidate: DiscoveryCandidate) -> Optional[ConstraintCheck]:
    # Not a user-stated constraint: only a VERIFIED "unavailable" excludes.
    prov = candidate.evidence("availability")
    if prov is None or prov.status is not EvidenceStatus.VERIFIED:
        return None
    value = prov.value
    unavailable = value is False or (
        isinstance(value, str) and value.strip().lower() in _UNAVAILABLE
    )
    if unavailable:
        return ConstraintCheck(
            name="availability",
            state=ConstraintState.FAIL,
            stated=False,
            detail="activity is verified unavailable",
            evidence_status=EvidenceStatus.VERIFIED,
        )
    return ConstraintCheck(
        name="availability",
        state=ConstraintState.PASS,
        stated=False,
        detail="activity is verified available",
        evidence_status=EvidenceStatus.VERIFIED,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_candidate(
    candidate: DiscoveryCandidate, request: DiscoveryRequest
) -> CandidateConstraintResult:
    """Evaluate every applicable hard constraint for one candidate."""
    checks: List[ConstraintCheck] = []
    for check in (
        _date_window_check(candidate, request),
        _budget_check(candidate, request),
        _min_age_check(candidate, request),
        _availability_check(candidate),
    ):
        if check is not None:
            checks.append(check)
    return CandidateConstraintResult(candidate_id=candidate.candidate_id, checks=checks)


@dataclass(frozen=True)
class ConstraintFilterResult:
    """Candidates partitioned by hard-constraint outcome (input order preserved)."""

    verified: List[DiscoveryCandidate] = field(default_factory=list)
    needs_verification: List[DiscoveryCandidate] = field(default_factory=list)
    excluded: List[DiscoveryCandidate] = field(default_factory=list)
    evaluations: Dict[str, CandidateConstraintResult] = field(default_factory=dict)

    @property
    def eligible(self) -> List[DiscoveryCandidate]:
        """Everything not excluded: verified first, then needs-verification."""
        return [*self.verified, *self.needs_verification]


def filter_candidates(
    candidates: List[DiscoveryCandidate], request: DiscoveryRequest
) -> ConstraintFilterResult:
    """Partition candidates into verified / needs-verification / excluded.

    FAILs are excluded by design (spec section 11). The caller ranks only
    ``eligible`` candidates and presents ``needs_verification`` separately.
    """
    verified: List[DiscoveryCandidate] = []
    needs_verification: List[DiscoveryCandidate] = []
    excluded: List[DiscoveryCandidate] = []
    evaluations: Dict[str, CandidateConstraintResult] = {}

    for candidate in candidates:
        result = evaluate_candidate(candidate, request)
        evaluations[candidate.candidate_id] = result
        if result.excluded:
            excluded.append(candidate)
        elif result.needs_verification:
            needs_verification.append(candidate)
        else:
            verified.append(candidate)

    return ConstraintFilterResult(
        verified=verified,
        needs_verification=needs_verification,
        excluded=excluded,
        evaluations=evaluations,
    )
