"""Tests for deterministic semantic validation of V4 intent plans."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from intent_engine.agentic.schemas import (
    ConstraintSource,
    IntentConstraint,
    IntentPlan,
    IntentStep,
)
from intent_engine.agentic.validator import (
    PlanValidationError,
    PlanValidator,
    ValidationIssue,
    canonical_plan_json,
)


NOW = datetime(2026, 10, 6, 19, 0, tzinfo=timezone.utc)


def _deeply_nested_value(depth=100):
    value = "leaf"
    for _ in range(depth):
        value = {"next": value}
    return value


def _cyclic_mapping():
    value = {}
    value["self"] = value
    return value


def _constraint(**overrides):
    values = {
        "type": "maturity_gate",
        "value": "kids",
        "hard": True,
        "source": ConstraintSource.USER,
    }
    values.update(overrides)
    return IntentConstraint(**values)


def _step(index=0, **overrides):
    values = {
        "step_id": f"step_{index}",
        "offset_minutes": index * 25,
        "intent": {"energy": round(0.55 - index * 0.2, 2), "tone": "calm"},
        "transition_reason": "Progressively reduce stimulation",
    }
    values.update(overrides)
    return IntentStep(**values)


def _plan(**overrides):
    values = {
        "plan_id": "plan_123",
        "domain": "streaming",
        "objective": "wind_down",
        "current_state": {"viewer": "kids", "energy": 0.85},
        "desired_state": {"energy": 0.1},
        "constraints": [_constraint()],
        "steps": [_step(0), _step(1), _step(2)],
        "assumptions": ["Bedtime is approximately 60 minutes away."],
        "confidence": 0.91,
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "planner_version": "v4.0",
    }
    values.update(overrides)
    return IntentPlan(**values)


@pytest.fixture
def validator():
    return PlanValidator()


class TestPlanValidation:
    def test_valid_plan_is_accepted_and_revalidated(self, validator):
        plan = _plan()

        validated = validator.validate(plan, now=NOW)

        assert isinstance(validated, IntentPlan)
        assert validated == plan

    def test_all_default_streaming_signals_are_supported(self, validator):
        plan = _plan(
            current_state={"energy": 0.8, "viewer": "kids"},
            desired_state={"energy": 0.1},
            steps=[
                _step(
                    0,
                    intent={
                        "energy": 0.5,
                        "viewer": "kids",
                        "tone": "familiar",
                        "runtime_preference": "short",
                        "time_bucket": "bedtime",
                        "intent_type": "calm",
                    },
                )
            ],
        )

        assert validator.validate(plan, now=NOW) == plan

    @pytest.mark.parametrize("energy", [-0.001, 1.001, "high", True])
    def test_invalid_energy_range_or_type_is_rejected(self, validator, energy):
        plan = _plan(steps=[_step(intent={"energy": energy})])

        with pytest.raises(PlanValidationError):
            validator.validate(plan, now=NOW)

    @pytest.mark.parametrize("section", ["current_state", "desired_state", "step"])
    def test_unknown_signal_is_rejected_where_capabilities_are_known(
        self, validator, section
    ):
        overrides = {}
        if section == "current_state":
            overrides["current_state"] = {"viewer": "kids", "hallucinated": 0.7}
        elif section == "desired_state":
            overrides["desired_state"] = {"hallucinated": "value"}
        else:
            overrides["steps"] = [_step(intent={"hallucinated": 0.7})]

        with pytest.raises(PlanValidationError):
            validator.validate(_plan(**overrides), now=NOW)

    @pytest.mark.parametrize(
        "selection_key",
        [
            "candidate_id",
            "selected_candidate_id",
            "recommended_item",
            "recommended_title",
            "ranked_items",
            "score",
        ],
    )
    def test_candidate_selection_and_scoring_keys_are_rejected(
        self, validator, selection_key
    ):
        plan = _plan(steps=[_step(intent={selection_key: "bluey"})])

        with pytest.raises(PlanValidationError):
            validator.validate(plan, now=NOW)

    def test_expired_plan_is_rejected(self, validator):
        # The schema requires expires_at > created_at, so use a later validation
        # time while keeping the plan structurally valid.
        plan = _plan(expires_at=NOW + timedelta(minutes=10))
        with pytest.raises(PlanValidationError):
            validator.validate(plan, now=NOW + timedelta(minutes=10))

    def test_plan_expiring_after_validation_time_is_accepted(self, validator):
        plan = _plan(expires_at=NOW + timedelta(microseconds=1))
        assert validator.validate(plan, now=NOW) == plan

    def test_plan_without_expiry_is_accepted(self, validator):
        plan = _plan(expires_at=None)
        assert validator.validate(plan, now=NOW) == plan

    def test_validation_does_not_mutate_the_input(self, validator):
        plan = _plan()
        before = plan.model_dump(mode="json")

        validator.validate(plan, now=NOW)

        assert plan.model_dump(mode="json") == before

    def test_explicitly_empty_capability_registry_fails_closed(self):
        validator = PlanValidator(capabilities={})

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(_plan(), now=NOW)

        assert any(
            issue.code == "missing_domain_capabilities"
            for issue in captured.value.issues
        )

    def test_huge_integer_signal_is_a_validation_error(self, validator):
        plan = _plan(steps=[_step(intent={"energy": 10**10000})])

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(
            issue.code == "invalid_signal_value" for issue in captured.value.issues
        )

    def test_streaming_rejects_ride_only_commute_time_bucket(self, validator):
        plan = _plan(steps=[_step(intent={"time_bucket": "morning_commute"})])

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(
            issue.code == "invalid_signal_value" for issue in captured.value.issues
        )

    def test_ride_matching_accepts_commute_time_bucket(self, validator):
        plan = _plan(
            domain="ride_matching",
            current_state={"urgency": 0.8},
            desired_state={"urgency": 0.2},
            constraints=[],
            steps=[_step(intent={"time_bucket": "morning_commute"})],
        )

        assert validator.validate(plan, now=NOW) == plan

    @pytest.mark.parametrize(
        "bad_value",
        [_deeply_nested_value(), _cyclic_mapping()],
        ids=["excessive-depth", "cycle"],
    )
    def test_deep_or_cyclic_payload_fails_as_plan_validation_error(
        self, validator, bad_value
    ):
        payload = _plan().model_dump(mode="python")
        payload["steps"][0]["intent"]["nested"] = bad_value

        with pytest.raises(PlanValidationError) as captured:
            validator.validate_payload(payload, now=NOW)

        assert any(
            issue.code == "schema_validation" for issue in captured.value.issues
        )


class TestConstraintValidation:
    @pytest.mark.parametrize(
        "domain,current_state,desired_state,step_intent,constraint",
        [
            (
                "streaming",
                {"energy": 0.8, "viewer": "kids"},
                {"energy": 0.1},
                {"energy": 0.5},
                _constraint(type="maturity_gate", value="unknown-audience"),
            ),
            (
                "ride_matching",
                {"urgency": 0.8},
                {"urgency": 0.2},
                {"urgency": 0.5},
                _constraint(type="surge_cap", value="cheap"),
            ),
            (
                "ride_matching",
                {"urgency": 0.8},
                {"urgency": 0.2},
                {"urgency": 0.5},
                _constraint(type="surge_cap", value=-0.01),
            ),
            (
                "food_delivery",
                {"hunger_urgency": 0.8},
                {"hunger_urgency": 0.2},
                {"hunger_urgency": 0.5},
                _constraint(type="allergens", value="peanuts"),
            ),
            (
                "food_delivery",
                {"hunger_urgency": 0.8},
                {"hunger_urgency": 0.2},
                {"hunger_urgency": 0.5},
                _constraint(type="allergens", value=[]),
            ),
            (
                "music",
                {"energy": 0.8},
                {"energy": 0.2},
                {"energy": 0.5},
                _constraint(type="block_explicit", value="yes"),
            ),
        ],
        ids=[
            "bad-maturity",
            "nonnumeric-surge-cap",
            "negative-surge-cap",
            "allergens-not-list",
            "empty-allergens",
            "explicit-not-boolean",
        ],
    )
    def test_malformed_type_specific_constraint_is_rejected(
        self,
        validator,
        domain,
        current_state,
        desired_state,
        step_intent,
        constraint,
    ):
        plan = _plan(
            domain=domain,
            current_state=current_state,
            desired_state=desired_state,
            steps=[_step(intent=step_intent)],
            constraints=[constraint],
        )

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(issue.code == "malformed_constraint" for issue in captured.value.issues)

    def test_null_constraint_value_fails_schema_validation(self, validator):
        payload = _plan().model_dump(mode="json")
        payload["constraints"][0]["value"] = None

        with pytest.raises(PlanValidationError) as captured:
            validator.validate_payload(payload, now=NOW)

        assert any(issue.code == "schema_validation" for issue in captured.value.issues)

    def test_unknown_constraint_type_is_rejected(self, validator):
        constraint = _constraint(type="disable_safety", value=True)

        with pytest.raises(PlanValidationError):
            validator.validate(_plan(constraints=[constraint]), now=NOW)

    def test_matching_authoritative_hard_constraint_is_preserved(self, validator):
        authoritative = _constraint(source=ConstraintSource.SYSTEM)
        plan = _plan(constraints=[authoritative])

        validated = validator.validate(
            plan,
            now=NOW,
            authoritative_constraints=[authoritative],
        )

        assert authoritative in validated.constraints
        assert validated.constraints[0].hard is True

    def test_missing_authoritative_hard_constraint_is_rejected(self, validator):
        authoritative = _constraint(source=ConstraintSource.SYSTEM)
        plan = _plan(constraints=[])

        with pytest.raises(PlanValidationError):
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

    def test_authoritative_hard_constraint_cannot_be_weakened(self, validator):
        authoritative = _constraint(source=ConstraintSource.SYSTEM, hard=True)
        weakened = _constraint(source=ConstraintSource.SYSTEM, hard=False)
        plan = _plan(constraints=[weakened])

        with pytest.raises(PlanValidationError):
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

    def test_authoritative_hard_constraint_value_cannot_be_changed(self, validator):
        authoritative = _constraint(source=ConstraintSource.SYSTEM, value="kids")
        altered = _constraint(source=ConstraintSource.SYSTEM, value="adult")
        plan = _plan(constraints=[altered])

        with pytest.raises(PlanValidationError):
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

    def test_non_hard_authoritative_constraint_does_not_become_mandatory(
        self, validator
    ):
        advisory = _constraint(source=ConstraintSource.DOMAIN, hard=False)
        plan = _plan(constraints=[])

        assert validator.validate(
            plan, now=NOW, authoritative_constraints=[advisory]
        ) == plan

    @pytest.mark.parametrize(
        "second",
        [
            _constraint(),
            _constraint(value="adult"),
        ],
        ids=["exact-duplicate", "conflicting-value"],
    )
    def test_same_type_and_source_plan_constraints_are_rejected(
        self, validator, second
    ):
        plan = _plan(constraints=[_constraint(), second])

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(
            issue.code == "duplicate_constraint" for issue in captured.value.issues
        )

    def test_exact_authoritative_constraint_plus_conflicting_extra_is_rejected(
        self, validator
    ):
        authoritative = _constraint(source=ConstraintSource.SYSTEM, value="kids")
        conflicting = _constraint(source=ConstraintSource.SYSTEM, value="adult")
        plan = _plan(constraints=[authoritative, conflicting])

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

        assert any(
            issue.code == "duplicate_constraint" for issue in captured.value.issues
        )

    def test_structurally_mutated_authoritative_constraint_is_rejected(
        self, validator
    ):
        authoritative = _constraint(source=ConstraintSource.SYSTEM)
        # Assignment validation protects normal writes; simulate corruption of a
        # retained object to verify that the boundary revalidates it anyway.
        object.__setattr__(authoritative, "type", "")

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(
                _plan(),
                now=NOW,
                authoritative_constraints=[authoritative],
            )

        assert any(
            issue.code == "invalid_authoritative_constraint"
            for issue in captured.value.issues
        )

    def test_nested_mutation_of_authoritative_constraint_is_rejected(self, validator):
        authoritative = IntentConstraint(
            type="allergens",
            value=["peanuts"],
            hard=True,
            source=ConstraintSource.SYSTEM,
        )
        authoritative.value.append(object())
        plan = _plan(
            domain="food_delivery",
            current_state={"hunger_urgency": 0.8},
            desired_state={"hunger_urgency": 0.2},
            constraints=[],
            steps=[_step(intent={"hunger_urgency": 0.5})],
        )

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

        assert any(
            issue.code == "invalid_authoritative_constraint"
            for issue in captured.value.issues
        )

    def test_authoritative_constraint_value_rule_is_enforced(self, validator):
        authoritative = _constraint(
            source=ConstraintSource.SYSTEM,
            value="unknown-audience",
        )

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(
                _plan(),
                now=NOW,
                authoritative_constraints=[authoritative],
            )

        assert any(
            issue.code == "invalid_authoritative_constraint"
            for issue in captured.value.issues
        )

    def test_huge_integer_constraint_is_a_validation_error(self, validator):
        constraint = _constraint(type="surge_cap", value=10**10000)
        plan = _plan(
            domain="ride_matching",
            current_state={"urgency": 0.8},
            desired_state={"urgency": 0.2},
            constraints=[constraint],
            steps=[_step(intent={"urgency": 0.5})],
        )

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(
            issue.code == "malformed_constraint" for issue in captured.value.issues
        )

    def test_conflicting_maturity_aliases_across_sources_are_rejected(
        self, validator
    ):
        authoritative = _constraint(
            type="maturity_gate",
            value="kids",
            hard=True,
            source=ConstraintSource.SYSTEM,
        )
        conflicting = _constraint(
            type="viewer_maturity",
            value="adult",
            hard=False,
            source=ConstraintSource.USER,
        )
        plan = _plan(constraints=[authoritative, conflicting])

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(
                plan,
                now=NOW,
                authoritative_constraints=[authoritative],
            )

        assert any(
            issue.code == "conflicting_constraint"
            for issue in captured.value.issues
        )

    def test_consistent_maturity_aliases_across_sources_are_accepted(
        self, validator
    ):
        authoritative = _constraint(
            type="maturity_gate",
            value="kids",
            hard=True,
            source=ConstraintSource.SYSTEM,
        )
        consistent_alias = _constraint(
            type="viewer_maturity",
            value="kids",
            hard=True,
            source=ConstraintSource.USER,
        )
        plan = _plan(constraints=[authoritative, consistent_alias])

        validated = validator.validate(
            plan,
            now=NOW,
            authoritative_constraints=[authoritative],
        )

        assert validated == plan


class TestPayloadValidation:
    def test_valid_payload_is_parsed_and_validated(self, validator):
        payload = _plan().model_dump(mode="json")

        validated = validator.validate_payload(payload, now=NOW)

        assert isinstance(validated, IntentPlan)
        assert validated.plan_id == "plan_123"

    def test_schema_error_is_exposed_as_plan_validation_error(self, validator):
        payload = _plan().model_dump(mode="json")
        payload.pop("plan_id")

        with pytest.raises(PlanValidationError) as captured:
            validator.validate_payload(payload, now=NOW)

        assert captured.value.issues
        assert all(isinstance(issue, ValidationIssue) for issue in captured.value.issues)

    def test_semantic_error_is_exposed_as_structured_issues(self, validator):
        payload = _plan().model_dump(mode="json")
        payload["steps"][0]["intent"]["unknown_signal"] = 0.5

        with pytest.raises(PlanValidationError) as captured:
            validator.validate_payload(payload, now=NOW)

        assert captured.value.issues
        assert all(isinstance(issue, ValidationIssue) for issue in captured.value.issues)


class TestCanonicalRepresentation:
    def test_canonicalize_is_stable_for_equivalent_mapping_order(self, validator):
        first = _plan(
            current_state={"viewer": "kids", "energy": 0.85},
            desired_state={"energy": 0.1, "tone": "soothing"},
        )
        second = _plan(
            current_state={"energy": 0.85, "viewer": "kids"},
            desired_state={"tone": "soothing", "energy": 0.1},
        )

        first_json = validator.canonicalize(first, now=NOW)
        second_json = validator.canonicalize(second, now=NOW)

        assert first_json == second_json
        assert json.loads(first_json)["plan_id"] == "plan_123"

    def test_module_canonicalizer_is_stable(self):
        first = _plan(current_state={"viewer": "kids", "energy": 0.85})
        second = _plan(current_state={"energy": 0.85, "viewer": "kids"})

        assert canonical_plan_json(first) == canonical_plan_json(second)

    def test_repeated_canonicalization_is_deterministic(self, validator):
        plan = _plan()

        outputs = {validator.canonicalize(plan, now=NOW) for _ in range(5)}

        assert len(outputs) == 1

    @pytest.mark.parametrize("bad_value", [object(), float("nan"), float("inf")])
    def test_module_canonicalizer_revalidates_nested_mutation(self, bad_value):
        plan = _plan()
        plan.steps[0].intent["nested"] = {"bad": bad_value}

        with pytest.raises(ValueError):
            canonical_plan_json(plan)

    def test_validator_rejects_post_construction_cyclic_mutation(self, validator):
        plan = _plan()
        plan.steps[0].intent["cycle"] = _cyclic_mapping()

        with pytest.raises(PlanValidationError) as captured:
            validator.validate(plan, now=NOW)

        assert any(
            issue.code == "schema_validation" for issue in captured.value.issues
        )

    def test_canonicalizer_rejects_post_construction_cyclic_mutation(self):
        plan = _plan()
        plan.steps[0].intent["cycle"] = _cyclic_mapping()

        with pytest.raises(ValueError):
            canonical_plan_json(plan)
