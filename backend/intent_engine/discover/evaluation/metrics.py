"""Operational metric definitions for the Discover pilot (spec section 16).

Every function here is the executable definition of a metric named in the spec's
metric table. They are pure functions over the evidence ledger in ``contracts``
so a reviewer can reproduce any reported number from the stored session.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
import statistics
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict

from intent_engine.discover.evaluation.contracts import (
    ARM_INTENT_ENGINE,
    ArmResult,
    ClaimKind,
    ConstraintState,
    EvaluationSession,
    EvidenceStatus,
    GroundTruthLabel,
    StatedConstraints,
)


# ---------------------------------------------------------------------------
# Constraint evaluation against ground truth (sections 11, 16)
# ---------------------------------------------------------------------------

def constraint_states(
    label: Optional[GroundTruthLabel],
    stated: StatedConstraints,
) -> Dict[str, ConstraintState]:
    """Resolve each stated hard constraint to PASS / FAIL / UNKNOWN.

    A constraint can only FAIL on a known (verified) value; a missing value is
    UNKNOWN, never a silent pass and never a confirmed violation.
    """
    states: Dict[str, ConstraintState] = {}

    def resolve(known: bool, ok: bool) -> ConstraintState:
        if not known:
            return ConstraintState.UNKNOWN
        return ConstraintState.PASS if ok else ConstraintState.FAIL

    if stated.budget_total is not None:
        cost = label.verified_total_cost if label else None
        states["budget"] = resolve(cost is not None, cost is not None and cost <= stated.budget_total)

    if stated.date_window_required:
        within = label.verified_within_date_window if label else None
        states["date"] = resolve(within is not None, within is True)

    if stated.children_ages:
        youngest = min(stated.children_ages)
        min_age = label.verified_min_age if label else None
        states["age"] = resolve(min_age is not None, min_age is not None and min_age <= youngest)

    if stated.max_distance_minutes is not None:
        dist = label.verified_distance_minutes if label else None
        states["distance"] = resolve(
            dist is not None, dist is not None and dist <= stated.max_distance_minutes
        )

    return states


def candidate_overall(
    label: Optional[GroundTruthLabel],
    stated: StatedConstraints,
) -> ConstraintState:
    """FAIL if any constraint fails; else UNKNOWN if any is unknown; else PASS."""
    states = list(constraint_states(label, stated).values())
    if any(state is ConstraintState.FAIL for state in states):
        return ConstraintState.FAIL
    if any(state is ConstraintState.UNKNOWN for state in states):
        return ConstraintState.UNKNOWN
    return ConstraintState.PASS


# ---------------------------------------------------------------------------
# Value agreement helper
# ---------------------------------------------------------------------------

def _values_agree(a: Any, b: Any, *, rel_tol: float = 1e-9, abs_tol: float = 0.01) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= max(abs_tol, rel_tol * max(abs(fa), abs(fb)))
    return a == b


# ---------------------------------------------------------------------------
# Primary endpoints (section 16: trust, not taste)
# ---------------------------------------------------------------------------

def verified_constraint_satisfaction_rate(
    arm: ArmResult,
    gt_by_id: Dict[str, GroundTruthLabel],
    stated: StatedConstraints,
    k: int = 5,
) -> float:
    """Share of top-k whose VERIFIED attributes satisfy every hard constraint."""
    top = arm.ranking[:k]
    if not top:
        return 0.0
    satisfied = sum(
        1 for cid in top if candidate_overall(gt_by_id.get(cid), stated) is ConstraintState.PASS
    )
    return satisfied / len(top)


def critical_factual_error_count(
    arm: ArmResult,
    gt_by_id: Dict[str, GroundTruthLabel],
) -> int:
    """Count of VERIFIED-asserted facts that ground truth contradicts or cannot confirm.

    Hedged (EXTRACTED) assertions are not fact claims and are never counted. An
    arm that only asserts what it holds from structured sources scores 0.
    """
    errors = 0
    for fact in arm.asserted_facts:
        if fact.asserted_as is not EvidenceStatus.VERIFIED:
            continue
        label = gt_by_id.get(fact.candidate_id)
        if label is None:
            errors += 1  # asserted a fact about an unverifiable candidate
            continue
        has_opinion, truth = label.truth_for(fact.attribute)
        if not has_opinion:
            errors += 1  # ground truth could not confirm -> fabricated fact
        elif not _values_agree(fact.asserted_value, truth):
            errors += 1  # ground truth contradicts the assertion
    return errors


# ---------------------------------------------------------------------------
# Secondary / supporting endpoints
# ---------------------------------------------------------------------------

def constraint_violation_rate(
    arm: ArmResult,
    gt_by_id: Dict[str, GroundTruthLabel],
    stated: StatedConstraints,
    k: int = 5,
) -> float:
    """Share of top-k that are a confirmed hard-constraint FAIL."""
    top = arm.ranking[:k]
    if not top:
        return 0.0
    violations = sum(
        1 for cid in top if candidate_overall(gt_by_id.get(cid), stated) is ConstraintState.FAIL
    )
    return violations / len(top)


def needs_verification_honesty(
    arm: ArmResult,
    gt_by_id: Dict[str, GroundTruthLabel],
    stated: StatedConstraints,
    k: int = 5,
) -> float:
    """Of top-k whose eligibility is UNKNOWN, the share the arm flagged with a caveat.

    A false VERIFIED assertion about such a candidate is separately penalized by
    ``critical_factual_error_count``; this metric isolates "did it surface the
    unknown at all."
    """
    top = arm.ranking[:k]
    unknown_ids = [
        cid for cid in top if candidate_overall(gt_by_id.get(cid), stated) is ConstraintState.UNKNOWN
    ]
    if not unknown_ids:
        return 1.0
    honest = 0
    for cid in unknown_ids:
        claims = arm.explanations.get(cid, [])
        if any(claim.kind is ClaimKind.CAVEAT for claim in claims):
            honest += 1
    return honest / len(unknown_ids)


def explanation_accuracy(
    arm: ArmResult,
    gt_by_id: Dict[str, GroundTruthLabel],
) -> float:
    """Share of claims consistent with ground truth.

    VERIFIED claims must be backed by ground truth and (when an asserted value
    exists) agree with it. EXTRACTED claims are accurate unless contradicted.
    UNKNOWN (caveat) claims are always consistent.
    """
    claims = [(cid, claim) for cid, cl in arm.explanations.items() for claim in cl]
    if not claims:
        return 1.0
    facts_by = {(fact.candidate_id, fact.attribute): fact for fact in arm.asserted_facts}

    ok = 0
    for cid, claim in claims:
        label = gt_by_id.get(cid)
        has_opinion, truth = (label.truth_for(claim.attribute) if label else (False, None))
        fact = facts_by.get((cid, claim.attribute))
        agrees = fact is None or _values_agree(fact.asserted_value, truth)

        if claim.evidence_status is EvidenceStatus.VERIFIED:
            if has_opinion and agrees:
                ok += 1
        elif claim.evidence_status is EvidenceStatus.EXTRACTED:
            if not has_opinion or agrees:
                ok += 1
        else:  # UNKNOWN caveat
            ok += 1
    return ok / len(claims)


def ranking_reproducibility(fingerprints: Sequence[str]) -> float:
    """Share of repeated identical-input runs that reproduced the first fingerprint."""
    if not fingerprints:
        return 1.0
    first = fingerprints[0]
    return sum(1 for fingerprint in fingerprints if fingerprint == first) / len(fingerprints)


# ---------------------------------------------------------------------------
# Cross-session secondary aggregates (human-collected)
# ---------------------------------------------------------------------------

def user_preference_rate(sessions: Sequence[EvaluationSession], arm_name: str) -> float:
    votes = [
        session.arms[arm_name].ratings.preferred
        for session in sessions
        if arm_name in session.arms
        and session.arms[arm_name].ratings is not None
        and session.arms[arm_name].ratings.preferred is not None
    ]
    if not votes:
        return 0.0
    return sum(1 for vote in votes if vote) / len(votes)


def median_time_to_useful_seconds(
    sessions: Sequence[EvaluationSession], arm_name: str
) -> Optional[float]:
    times = [
        session.arms[arm_name].ratings.time_to_useful_seconds
        for session in sessions
        if arm_name in session.arms
        and session.arms[arm_name].ratings is not None
        and session.arms[arm_name].ratings.time_to_useful_seconds is not None
    ]
    return statistics.median(times) if times else None


# ---------------------------------------------------------------------------
# Per-arm report
# ---------------------------------------------------------------------------

class MetricReport(BaseModel):
    """Objective, record-derived metrics for one arm in one session."""

    model_config = ConfigDict(extra="forbid")

    arm: str
    n_ranked: int
    verified_constraint_satisfaction_rate: float
    constraint_violation_rate: float
    critical_factual_error_count: int
    needs_verification_honesty: float
    explanation_accuracy: float


def compute_arm_report(session: EvaluationSession, arm_name: str, k: int = 5) -> MetricReport:
    arm = session.arms[arm_name]
    gt = session.ground_truth_by_id()
    stated = session.stated_constraints
    return MetricReport(
        arm=arm_name,
        n_ranked=len(arm.ranking),
        verified_constraint_satisfaction_rate=verified_constraint_satisfaction_rate(arm, gt, stated, k),
        constraint_violation_rate=constraint_violation_rate(arm, gt, stated, k),
        critical_factual_error_count=critical_factual_error_count(arm, gt),
        needs_verification_honesty=needs_verification_honesty(arm, gt, stated, k),
        explanation_accuracy=explanation_accuracy(arm, gt),
    )


# ---------------------------------------------------------------------------
# Pre-registered go / no-go (section 16.2)
# ---------------------------------------------------------------------------

class GoNoGo(str, Enum):
    CONTINUE = "CONTINUE"
    IMPROVE = "IMPROVE"
    PIVOT = "PIVOT"


def decide(
    engine: MetricReport,
    llm: MetricReport,
    *,
    preference_rate: float,
    reproducibility: float,
    median_time_to_useful: Optional[float] = None,
) -> GoNoGo:
    """Map measured endpoints to the pre-registered decision (spec section 16.2)."""
    # PIVOT: the engine fails its reason for existing, or the LLM matches/beats it
    # on BOTH primary endpoints (same or better) with less complexity.
    engine_cannot_zero = engine.critical_factual_error_count > 0
    llm_matches_or_beats_both = (
        llm.verified_constraint_satisfaction_rate >= engine.verified_constraint_satisfaction_rate
        and llm.critical_factual_error_count <= engine.critical_factual_error_count
    )
    if engine_cannot_zero or llm_matches_or_beats_both:
        return GoNoGo.PIVOT

    primaries_met = (
        engine.verified_constraint_satisfaction_rate >= 0.95
        and engine.critical_factual_error_count == 0
        and reproducibility >= 1.0
    )
    beats_llm_on_a_primary = (
        engine.verified_constraint_satisfaction_rate > llm.verified_constraint_satisfaction_rate
        or engine.critical_factual_error_count < llm.critical_factual_error_count
    )

    if primaries_met and preference_rate >= 0.70 and beats_llm_on_a_primary:
        return GoNoGo.CONTINUE
    return GoNoGo.IMPROVE
