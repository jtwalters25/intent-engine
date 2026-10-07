"""Tests for the deterministic Phase 2 rule-based intent planner."""

from datetime import datetime, timedelta, timezone
import inspect

import pytest
from pydantic import ValidationError

from intent_engine.agentic import (
    DEFAULT_HORIZON_MINUTES,
    MAX_PLAN_STEPS,
    ConstraintSource,
    ContextInterpretation,
    IntentConstraint,
    IntentPlan,
    IntentPlanner,
    PlanValidator,
    PlanningError,
    RuleBasedIntentPlanner,
    SUPPORTED_OBJECTIVES,
    canonical_plan_json,
)


NOW = datetime(2026, 10, 6, 19, 0, tzinfo=timezone.utc)


def _interpretation(
    objective="wind_down",
    *,
    entities=None,
    inferred_context=None,
    explicit_constraints=None,
    assumptions=None,
    missing_information=None,
    confidence=0.91,
):
    return ContextInterpretation(
        objective=objective,
        entities=(
            {"viewer": "kids", "energy": 0.85}
            if entities is None
            else entities
        ),
        explicit_constraints=(
            [] if explicit_constraints is None else explicit_constraints
        ),
        inferred_context=(
            {"horizon_minutes": 60}
            if inferred_context is None
            else inferred_context
        ),
        assumptions=(
            ["Bedtime is approximately 60 minutes away."]
            if assumptions is None
            else assumptions
        ),
        missing_information=(
            [] if missing_information is None else missing_information
        ),
        confidence=confidence,
    )


def _constraint(
    *,
    constraint_type="maturity_gate",
    value="kids",
    hard=True,
    source=ConstraintSource.SYSTEM,
):
    return IntentConstraint(
        type=constraint_type,
        value=value,
        hard=hard,
        source=source,
    )


@pytest.fixture
def planner():
    return RuleBasedIntentPlanner()


class TestSupportedObjectives:
    @pytest.mark.parametrize(
        "objective,expected_signal,expected_value",
        [
            ("wind_down", "intent_type", "calm"),
            ("focus", "intent_type", "educational"),
            ("family_time", "viewer", "family"),
            ("quick_session", "runtime_preference", "short"),
            ("high_energy", "intent_type", "popular"),
        ],
    )
    def test_each_supported_objective_produces_a_valid_plan(
        self,
        planner,
        objective,
        expected_signal,
        expected_value,
    ):
        plan = planner.create_plan(_interpretation(objective), "streaming", NOW)

        assert isinstance(plan, IntentPlan)
        assert plan.objective == objective
        assert plan.desired_state[expected_signal] == expected_value
        assert PlanValidator().validate(plan, now=NOW) == plan

    def test_declared_objective_set_is_deliberately_small(self):
        assert SUPPORTED_OBJECTIVES == {
            "wind_down",
            "focus",
            "family_time",
            "quick_session",
            "high_energy",
        }

    @pytest.mark.parametrize(
        "alias,canonical",
        [
            ("wind down", "wind_down"),
            ("Family-Time", "family_time"),
            ("quick", "quick_session"),
            ("energetic", "high_energy"),
        ],
    )
    def test_deterministic_objective_aliases(self, planner, alias, canonical):
        plan = planner.create_plan(_interpretation(alias), "streaming", NOW)
        assert plan.objective == canonical

    def test_unknown_objective_fails_closed(self, planner):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan(_interpretation("surprise_me"), "streaming", NOW)

        assert captured.value.code == "unsupported_objective"

    @pytest.mark.parametrize(
        "domain",
        ["music", "ecommerce", "ride_matching", "food_delivery"],
    )
    def test_non_pilot_domain_fails_closed(self, planner, domain):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan(_interpretation(), domain, NOW)

        assert captured.value.code == "unsupported_domain"


class TestDeterminismAndTimeTrust:
    def test_identical_inputs_produce_identical_plans(self, planner):
        interpretation = _interpretation()

        first = planner.create_plan(interpretation, "streaming", NOW)
        second = planner.create_plan(interpretation, "streaming", NOW)

        assert first == second
        assert canonical_plan_json(first) == canonical_plan_json(second)
        assert first.plan_id == second.plan_id

    def test_trusted_now_controls_created_at_and_expiry(self, planner):
        plan = planner.create_plan(_interpretation(), "streaming", NOW)

        assert plan.created_at == NOW
        assert plan.expires_at == NOW + timedelta(minutes=60)

    def test_interpreted_timestamps_cannot_control_created_at(self, planner):
        first = _interpretation(
            inferred_context={
                "horizon_minutes": 60,
                "created_at": "1999-01-01T00:00:00Z",
                "timestamp": "2099-01-01T00:00:00Z",
            }
        )
        second = _interpretation(
            inferred_context={
                "horizon_minutes": 60,
                "created_at": "2001-01-01T00:00:00Z",
                "timestamp": "2100-01-01T00:00:00Z",
            }
        )

        first_plan = planner.create_plan(first, "streaming", NOW)
        second_plan = planner.create_plan(second, "streaming", NOW)

        assert first_plan.created_at == NOW
        assert second_plan.created_at == NOW
        assert first_plan == second_plan

    def test_changing_trusted_now_changes_plan_time_and_id(self, planner):
        later = NOW + timedelta(minutes=1)
        first = planner.create_plan(_interpretation(), "streaming", NOW)
        second = planner.create_plan(_interpretation(), "streaming", later)

        assert first.created_at == NOW
        assert second.created_at == later
        assert first.plan_id != second.plan_id

    def test_deterministic_ids_are_derived_from_semantics(self, planner):
        plan = planner.create_plan(_interpretation(), "streaming", NOW)

        assert plan.plan_id.startswith("plan_")
        assert len(plan.plan_id) == 25
        assert [step.step_id for step in plan.steps] == [
            f"{plan.plan_id}_step_{index}"
            for index in range(1, len(plan.steps) + 1)
        ]

    def test_candidate_metadata_is_not_inspected_or_hashed(self, planner):
        base = _interpretation()
        with_candidates = _interpretation(
            entities={
                "viewer": "kids",
                "energy": 0.85,
                "candidates": [
                    {"item_id": "bluey", "score": 1.0},
                    {"item_id": "other", "score": 0.1},
                ],
            }
        )

        assert planner.create_plan(base, "streaming", NOW) == planner.create_plan(
            with_candidates,
            "streaming",
            NOW,
        )


class TestExplicitDefaults:
    def test_missing_safe_values_receive_observable_defaults(self, planner):
        interpretation = _interpretation(
            entities={},
            inferred_context={},
            assumptions=[],
            missing_information=["energy", "viewer", "horizon_minutes"],
        )

        plan = planner.create_plan(interpretation, "streaming", NOW)

        assert plan.current_state == {"energy": 0.5, "viewer": "family"}
        assert plan.expires_at == NOW + timedelta(minutes=60)
        joined = " ".join(plan.assumptions)
        assert "Current energy was not provided" in joined
        assert "Viewer was not provided" in joined
        assert "Plan horizon was not provided" in joined

    @pytest.mark.parametrize("objective", sorted(SUPPORTED_OBJECTIVES))
    def test_each_objective_has_an_explicit_default_horizon(
        self,
        planner,
        objective,
    ):
        plan = planner.create_plan(
            _interpretation(objective, inferred_context={}, assumptions=[]),
            "streaming",
            NOW,
        )

        expected = DEFAULT_HORIZON_MINUTES[objective]
        assert plan.expires_at == NOW + timedelta(minutes=expected)
        assert any(str(expected) in assumption for assumption in plan.assumptions)

    def test_supplied_values_do_not_generate_default_assumptions(self, planner):
        plan = planner.create_plan(
            _interpretation(assumptions=[]),
            "streaming",
            NOW,
        )

        joined = " ".join(plan.assumptions)
        assert "was not provided" not in joined

    def test_explicit_horizon_controls_expiry(self, planner):
        plan = planner.create_plan(
            _interpretation(inferred_context={"horizon_minutes": 75}),
            "streaming",
            NOW,
        )

        assert plan.expires_at == NOW + timedelta(minutes=75)

    def test_missing_field_without_safe_default_fails_closed(self, planner):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan(
                _interpretation(missing_information=["unknown safety policy"]),
                "streaming",
                NOW,
            )

        assert captured.value.code == "unresolved_missing_information"


class TestMalformedInterpretations:
    def test_raw_malformed_interpretation_fails_safely(self, planner):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan({}, "streaming", NOW)

        assert captured.value.code == "invalid_interpretation"

    def test_objective_is_required_and_non_optional(self):
        payload = _interpretation().model_dump(mode="python")
        payload["objective"] = None

        with pytest.raises(ValidationError):
            ContextInterpretation.model_validate(payload)

    @pytest.mark.parametrize(
        "energy",
        [-0.01, 1.01, "high", True, 10**10000],
        ids=["below-range", "above-range", "string", "boolean", "huge-int"],
    )
    def test_invalid_energy_fails_safely(self, planner, energy):
        interpretation = _interpretation(
            entities={"viewer": "kids", "energy": energy}
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "invalid_context"

    @pytest.mark.parametrize("viewer", ["", "children", 3, True])
    def test_invalid_viewer_fails_safely(self, planner, viewer):
        interpretation = _interpretation(
            entities={"viewer": viewer, "energy": 0.5}
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "invalid_context"

    @pytest.mark.parametrize("horizon", [0, 5, 241, 60.5, "60", True])
    def test_invalid_wind_down_horizon_fails_safely(self, planner, horizon):
        interpretation = _interpretation(
            inferred_context={"horizon_minutes": horizon}
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "invalid_horizon"

    def test_conflicting_context_values_fail_closed(self, planner):
        interpretation = _interpretation(
            entities={"viewer": "kids", "energy": 0.8},
            inferred_context={"energy": 0.2, "horizon_minutes": 60},
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "conflicting_context"

    @pytest.mark.parametrize(
        "signal",
        ["energy_level", "energyLevel", "viewer_profile"],
    )
    def test_noncanonical_adapter_vocabulary_fails_explicitly(
        self,
        planner,
        signal,
    ):
        interpretation = _interpretation(
            inferred_context={"horizon_minutes": 60, signal: 0.5}
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "noncanonical_signal"


class TestConstraintTrustBoundary:
    def test_authoritative_constraint_is_preserved_exactly(self, planner):
        authoritative = _constraint()

        plan = planner.create_plan(
            _interpretation(),
            "streaming",
            NOW,
            authoritative_constraints=[authoritative],
        )

        assert plan.constraints == [authoritative]
        assert PlanValidator().validate(
            plan,
            now=NOW,
            authoritative_constraints=[authoritative],
        ) == plan

    def test_trusted_user_constraint_may_be_authoritative(self, planner):
        authoritative = _constraint(source=ConstraintSource.USER)

        plan = planner.create_plan(
            _interpretation(),
            "streaming",
            NOW,
            authoritative_constraints=[authoritative],
        )

        assert plan.constraints[0].source == ConstraintSource.USER
        assert plan.constraints[0].hard is True

    @pytest.mark.parametrize(
        "authoritative",
        [
            _constraint(hard=False),
            _constraint(source=ConstraintSource.INFERRED),
        ],
        ids=["not-hard", "inferred-source"],
    )
    def test_invalid_authoritative_constraint_fails_closed(
        self,
        planner,
        authoritative,
    ):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan(
                _interpretation(),
                "streaming",
                NOW,
                authoritative_constraints=[authoritative],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    def test_untyped_authoritative_constraint_fails_closed(self, planner):
        with pytest.raises(PlanningError) as captured:
            planner.create_plan(
                _interpretation(),
                "streaming",
                NOW,
                authoritative_constraints=[{"type": "maturity_gate"}],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    @pytest.mark.parametrize(
        "constraint",
        [
            _constraint(hard=True, source=ConstraintSource.USER),
            _constraint(hard=True, source=ConstraintSource.INFERRED),
            _constraint(hard=False, source=ConstraintSource.SYSTEM),
            _constraint(hard=False, source=ConstraintSource.DOMAIN),
        ],
        ids=[
            "user-hard",
            "inferred-hard",
            "claimed-system-authority",
            "claimed-domain-authority",
        ],
    )
    def test_interpretation_cannot_create_authority(self, planner, constraint):
        interpretation = _interpretation(explicit_constraints=[constraint])

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(interpretation, "streaming", NOW)

        assert captured.value.code == "untrusted_constraint_authority"

    @pytest.mark.parametrize(
        "source",
        [ConstraintSource.USER, ConstraintSource.INFERRED],
    )
    def test_soft_interpreted_constraint_remains_non_authoritative(
        self,
        planner,
        source,
    ):
        interpreted = _constraint(hard=False, source=source)
        plan = planner.create_plan(
            _interpretation(explicit_constraints=[interpreted]),
            "streaming",
            NOW,
        )

        assert plan.constraints == [interpreted]
        assert plan.constraints[0].hard is False
        assert any("remain non-authoritative" in item for item in plan.assumptions)

    def test_conflicting_interpreted_and_authoritative_constraints_fail(self, planner):
        authoritative = _constraint(value="kids")
        interpreted = _constraint(
            value="adult",
            hard=False,
            source=ConstraintSource.USER,
        )

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(
                _interpretation(explicit_constraints=[interpreted]),
                "streaming",
                NOW,
                authoritative_constraints=[authoritative],
            )

        assert captured.value.code == "plan_validation_failed"


class TestPlanShapeAndValidationBoundary:
    def test_canonical_wind_down_progression_is_monotonic(self, planner):
        plan = planner.create_plan(_interpretation(), "streaming", NOW)
        energies = [step.intent["energy"] for step in plan.steps]

        assert energies == [0.55, 0.3, 0.1]
        assert energies == sorted(energies, reverse=True)
        assert [step.offset_minutes for step in plan.steps] == [0, 25, 50]

    def test_high_energy_progression_is_monotonic(self, planner):
        plan = planner.create_plan(
            _interpretation(
                "high_energy",
                entities={"viewer": "family", "energy": 0.2},
                inferred_context={"horizon_minutes": 45},
            ),
            "streaming",
            NOW,
        )
        energies = [step.intent["energy"] for step in plan.steps]

        assert energies == sorted(energies)
        assert energies[-1] >= 0.9

    @pytest.mark.parametrize("objective", sorted(SUPPORTED_OBJECTIVES))
    def test_plan_step_limit_is_always_respected(self, planner, objective):
        plan = planner.create_plan(_interpretation(objective), "streaming", NOW)
        assert 1 <= len(plan.steps) <= MAX_PLAN_STEPS

    def test_planner_contract_has_no_candidate_parameter(self, planner):
        parameters = inspect.signature(planner.create_plan).parameters
        assert "candidates" not in parameters
        assert "items" not in parameters

    def test_planner_implements_protocol(self, planner):
        assert isinstance(planner, IntentPlanner)

    def test_step_intents_never_contain_candidate_or_scoring_fields(self, planner):
        forbidden = {
            "candidate_id",
            "item_id",
            "recommended_title",
            "score",
            "final_score",
            "rank",
        }

        for objective in SUPPORTED_OBJECTIVES:
            plan = planner.create_plan(_interpretation(objective), "streaming", NOW)
            for step in plan.steps:
                assert forbidden.isdisjoint(step.intent)

    def test_every_returned_plan_crosses_phase_1_validator(self):
        class RecordingValidator(PlanValidator):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def validate(self, *args, **kwargs):
                self.calls += 1
                return super().validate(*args, **kwargs)

        validator = RecordingValidator()
        planner = RuleBasedIntentPlanner(validator=validator)

        planner.create_plan(_interpretation(), "streaming", NOW)

        assert validator.calls == 2

    def test_validator_rejection_is_wrapped_as_planning_error(self):
        planner = RuleBasedIntentPlanner(validator=PlanValidator(capabilities={}))

        with pytest.raises(PlanningError) as captured:
            planner.create_plan(_interpretation(), "streaming", NOW)

        assert captured.value.code == "plan_validation_failed"
