"""Tests for the Discover evaluation & evidence contracts (spec section 16).

The fixtures stage the pilot's core comparison: a constraint-faithful engine arm
that only asserts what it holds, versus a fluent LLM arm that confidently states
inferred values. The metrics must separate the two on the primary endpoints.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from intent_engine.discover.evaluation import (
    ARM_INTENT_ENGINE,
    ARM_LLM_ONLY,
    ArmResult,
    AssertedFact,
    AttributeProvenance,
    CandidateSnapshot,
    ClaimKind,
    ConstraintState,
    EvaluationSession,
    EvidenceStatus,
    ExplanationClaim,
    GoNoGo,
    GroundTruthLabel,
    HumanRatings,
    MetricReport,
    PriceBasis,
    StatedConstraints,
    candidate_overall,
    compute_arm_report,
    decide,
    pool_fingerprint,
    ranking_fingerprint,
    ranking_reproducibility,
)

TS = datetime(2026, 10, 8, tzinfo=timezone.utc)
V = EvidenceStatus.VERIFIED
E = EvidenceStatus.EXTRACTED
U = EvidenceStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _gt(cid, *, cost=None, within=None, min_age=None, dist=None, **extra):
    return GroundTruthLabel(
        candidate_id=cid,
        verified_price_basis=PriceBasis.TOTAL if cost is not None else PriceBasis.UNKNOWN,
        verified_total_cost=(Decimal(str(cost)) if cost is not None else None),
        verified_within_date_window=within,
        verified_min_age=min_age,
        verified_distance_minutes=dist,
        verified_at=TS,
        verifier="tester",
        verified_attributes=extra,
    )


def _match(attribute, status=V, signal=None):
    return ExplanationClaim(
        text=f"matches {attribute}", kind=ClaimKind.MATCH, attribute=attribute,
        evidence_status=status, signal=signal,
    )


def _fact(cid, attribute, value, status=V):
    return AssertedFact(candidate_id=cid, attribute=attribute, asserted_value=value, asserted_as=status)


STATED = StatedConstraints(
    budget_total=Decimal("100"),
    party_size=5,
    children_ages=[7, 9, 10, 12],
    max_distance_minutes=30,
    date_window_required=True,
)

GROUND_TRUTH = [
    _gt("c1", cost=40, within=True, min_age=5, dist=20),   # PASS
    _gt("c2", cost=80, within=True, min_age=6, dist=25),   # PASS
    _gt("c3", cost=150, within=True, min_age=5, dist=10),  # FAIL (budget)
    _gt("c4", cost=None, within=True, min_age=4, dist=15), # UNKNOWN (budget)
    _gt("c5", cost=30, within=True, min_age=13, dist=10),  # FAIL (age)
    _gt("c6", cost=50, within=True, min_age=3, dist=28),   # PASS
]


def _session():
    engine = ArmResult(
        ranking=["c1", "c2", "c6"],  # confirmed-eligible only; unknowns go elsewhere
        explanations={
            "c1": [_match("within_date_window", signal="schedule_fit"), _match("distance_minutes", signal="distance_fit")],
            "c2": [_match("within_date_window")],
            "c6": [_match("within_date_window")],
        },
        asserted_facts=[
            _fact("c1", "within_date_window", True),
            _fact("c1", "price_total", Decimal("40")),
            _fact("c2", "price_total", Decimal("80")),
        ],
        ranking_fingerprint="fp_engine",
        ratings=HumanRatings(preferred=True, time_to_useful_seconds=60, top5_relevance=4.5),
    )
    llm = ArmResult(
        ranking=["c1", "c3", "c4", "c2", "c6"],  # surfaces a violation (c3) and an unknown (c4)
        explanations={
            "c1": [_match("within_date_window")],
            "c3": [_match("price_total", signal="budget_fit")],  # claims affordable
            "c4": [_match("price_total")],                       # asserts budget fit, no caveat
            "c2": [_match("within_date_window")],
            "c6": [_match("within_date_window")],
        },
        asserted_facts=[
            _fact("c3", "price_total", Decimal("90")),   # ground truth 150 -> contradiction
            _fact("c4", "price_total", Decimal("25")),   # ground truth unknown -> fabrication
            _fact("c1", "within_date_window", True),     # agrees
        ],
        ratings=HumanRatings(preferred=False, time_to_useful_seconds=140, top5_relevance=4.0),
    )
    return EvaluationSession(
        session_id="s1",
        validated_intent={"objective": "family_educational_activity"},
        candidate_pool=[CandidateSnapshot(candidate_id=c) for c in ["c1", "c2", "c3", "c4", "c5", "c6"]],
        stated_constraints=STATED,
        arms={ARM_INTENT_ENGINE: engine, ARM_LLM_ONLY: llm},
        ground_truth=GROUND_TRUTH,
        presentation_order=[ARM_LLM_ONLY, ARM_INTENT_ENGINE],
        engine_version="e1",
        config_version="c1",
    )


# ---------------------------------------------------------------------------
# Constraint resolution
# ---------------------------------------------------------------------------

class TestConstraintResolution:
    def setup_method(self):
        self.gt = {label.candidate_id: label for label in GROUND_TRUTH}

    def test_pass_fail_unknown(self):
        assert candidate_overall(self.gt["c1"], STATED) is ConstraintState.PASS
        assert candidate_overall(self.gt["c3"], STATED) is ConstraintState.FAIL  # over budget
        assert candidate_overall(self.gt["c5"], STATED) is ConstraintState.FAIL  # age
        assert candidate_overall(self.gt["c4"], STATED) is ConstraintState.UNKNOWN  # price unknown

    def test_missing_label_is_unknown_not_pass(self):
        assert candidate_overall(None, STATED) is ConstraintState.UNKNOWN


# ---------------------------------------------------------------------------
# Primary endpoints: the engine must beat the LLM on trust
# ---------------------------------------------------------------------------

class TestPrimaryEndpoints:
    def setup_method(self):
        self.session = _session()
        self.engine = compute_arm_report(self.session, ARM_INTENT_ENGINE)
        self.llm = compute_arm_report(self.session, ARM_LLM_ONLY)

    def test_engine_satisfaction_is_perfect_llm_is_not(self):
        assert self.engine.verified_constraint_satisfaction_rate == 1.0
        assert self.llm.verified_constraint_satisfaction_rate == pytest.approx(0.6)

    def test_engine_has_zero_factual_errors_llm_has_two(self):
        assert self.engine.critical_factual_error_count == 0
        assert self.llm.critical_factual_error_count == 2  # fabricated c4, contradicted c3

    def test_engine_surfaces_no_violations(self):
        assert self.engine.constraint_violation_rate == 0.0
        assert self.llm.constraint_violation_rate == pytest.approx(0.2)

    def test_engine_is_honest_about_unknowns(self):
        # engine surfaces no unknowns in recommendations -> vacuously honest
        assert self.engine.needs_verification_honesty == 1.0
        # llm surfaces c4 (unknown) with no caveat -> dishonest
        assert self.llm.needs_verification_honesty == 0.0

    def test_explanation_accuracy_separates_the_arms(self):
        assert self.engine.explanation_accuracy == 1.0
        assert self.llm.explanation_accuracy == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Reproducibility fingerprint
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_same_inputs_same_fingerprint(self):
        args = dict(validated_intent={"objective": "x"}, pool_fingerprint="p", config_version="c", engine_version="e")
        assert ranking_fingerprint(**args) == ranking_fingerprint(**args)

    def test_different_intent_changes_fingerprint(self):
        a = ranking_fingerprint(validated_intent={"objective": "x"}, pool_fingerprint="p", config_version="c", engine_version="e")
        b = ranking_fingerprint(validated_intent={"objective": "y"}, pool_fingerprint="p", config_version="c", engine_version="e")
        assert a != b

    def test_pool_fingerprint_is_order_independent(self):
        a = CandidateSnapshot(
            candidate_id="a",
            attributes={"price": AttributeProvenance(value=Decimal("10"), status=V, source="tm", source_url="http://x", retrieved_at=TS, source_field="priceRanges")},
        )
        b = CandidateSnapshot(candidate_id="b")
        assert pool_fingerprint([a, b]) == pool_fingerprint([b, a])

    def test_reproducibility_rate(self):
        assert ranking_reproducibility(["f", "f", "f"]) == 1.0
        assert ranking_reproducibility(["f", "f", "g"]) == pytest.approx(2 / 3)
        assert ranking_reproducibility([]) == 1.0


# ---------------------------------------------------------------------------
# Evidence-contract validators (sections 7.1, 13.1)
# ---------------------------------------------------------------------------

class TestEvidenceContracts:
    def _prov(self, **overrides):
        base = dict(status=V, value="x", source="tm", source_url="http://x", retrieved_at=TS, source_field="field")
        base.update(overrides)
        return AttributeProvenance(**base)

    def test_unknown_attribute_must_not_carry_a_value(self):
        with pytest.raises(ValidationError):
            self._prov(status=U, value="something", source_field=None)

    def test_verified_requires_structured_source_field(self):
        with pytest.raises(ValidationError):
            self._prov(status=V, source_field=None)

    def test_extracted_requires_an_extractor(self):
        with pytest.raises(ValidationError):
            self._prov(status=E, source_field=None, extractor=None)

    def test_extracted_with_extractor_is_valid(self):
        prov = self._prov(status=E, source_field=None, extractor="classifier-v1")
        assert prov.is_fact is False

    def test_verified_is_a_fact(self):
        assert self._prov().is_fact is True

    def test_caveat_cannot_rest_on_a_verified_attribute(self):
        with pytest.raises(ValidationError):
            ExplanationClaim(text="x", kind=ClaimKind.CAVEAT, attribute="price_total", evidence_status=V)

    def test_caveat_on_unknown_is_valid(self):
        claim = ExplanationClaim(text="price needs verification", kind=ClaimKind.CAVEAT, attribute="price_total", evidence_status=U)
        assert claim.kind is ClaimKind.CAVEAT


# ---------------------------------------------------------------------------
# Go / no-go decision (section 16.2)
# ---------------------------------------------------------------------------

def _report(arm, *, sat, viol=0.0, err=0, honesty=1.0, expl=1.0, n=5):
    return MetricReport(
        arm=arm, n_ranked=n,
        verified_constraint_satisfaction_rate=sat,
        constraint_violation_rate=viol,
        critical_factual_error_count=err,
        needs_verification_honesty=honesty,
        explanation_accuracy=expl,
    )


class TestGoNoGo:
    def test_continue_when_engine_wins_and_is_preferred(self):
        engine = _report(ARM_INTENT_ENGINE, sat=1.0, err=0)
        llm = _report(ARM_LLM_ONLY, sat=0.6, err=2)
        assert decide(engine, llm, preference_rate=0.8, reproducibility=1.0, median_time_to_useful=60) is GoNoGo.CONTINUE

    def test_improve_when_primaries_met_but_not_preferred(self):
        engine = _report(ARM_INTENT_ENGINE, sat=1.0, err=0)
        llm = _report(ARM_LLM_ONLY, sat=0.6, err=2)
        assert decide(engine, llm, preference_rate=0.5, reproducibility=1.0) is GoNoGo.IMPROVE

    def test_improve_when_not_reproducible(self):
        engine = _report(ARM_INTENT_ENGINE, sat=1.0, err=0)
        llm = _report(ARM_LLM_ONLY, sat=0.6, err=0)
        assert decide(engine, llm, preference_rate=0.9, reproducibility=0.8) is GoNoGo.IMPROVE

    def test_pivot_when_llm_matches_or_beats_both_primaries(self):
        engine = _report(ARM_INTENT_ENGINE, sat=0.9, err=0)
        llm = _report(ARM_LLM_ONLY, sat=0.95, err=0)
        assert decide(engine, llm, preference_rate=0.9, reproducibility=1.0) is GoNoGo.PIVOT

    def test_pivot_when_engine_cannot_reach_zero_errors(self):
        engine = _report(ARM_INTENT_ENGINE, sat=1.0, err=1)
        llm = _report(ARM_LLM_ONLY, sat=0.5, err=3)
        assert decide(engine, llm, preference_rate=0.9, reproducibility=1.0) is GoNoGo.PIVOT


# ---------------------------------------------------------------------------
# End-to-end report shape
# ---------------------------------------------------------------------------

def test_full_session_decides_continue():
    session = _session()
    engine = compute_arm_report(session, ARM_INTENT_ENGINE)
    llm = compute_arm_report(session, ARM_LLM_ONLY)
    decision = decide(engine, llm, preference_rate=0.8, reproducibility=1.0, median_time_to_useful=60)
    assert decision is GoNoGo.CONTINUE
