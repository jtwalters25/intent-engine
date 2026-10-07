"""Tests for the pure Phase 3A intent-vocabulary normalization boundary."""

from datetime import datetime, timezone
import inspect

import pytest

from intent_engine.adapters.streaming import StreamingAdapter
from intent_engine.agentic import (
    ConstraintSource,
    ContextInterpretation,
    IntentConstraint,
    NormalizationError,
    NormalizedAdapterInput,
    NormalizedProphecyContext,
    PlanIntentNormalizer,
    ProphecyContextNormalizer,
    RuleBasedIntentPlanner,
    SUPPORTED_OBJECTIVES,
)
from intent_engine.prophecy_agent import ProphecyAgent, TimeContext
from intent_engine.agentic.schemas import MAX_JSON_ITEMS, MAX_JSON_NESTING
from intent_engine.agentic.validator import FORBIDDEN_SELECTION_SIGNALS
from intent_engine.schemas import Domain, Item, MultiplierSet


NOW = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)


def _interpretation(objective="wind_down"):
    return ContextInterpretation(
        objective=objective,
        entities={"viewer": "kids", "energy": 0.85},
        explicit_constraints=[],
        inferred_context={"horizon_minutes": 60},
        assumptions=[],
        missing_information=[],
        confidence=0.9,
    )


def _constraint(
    constraint_type="maturity_gate",
    value="kids",
    *,
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
def normalizer():
    return PlanIntentNormalizer()


@pytest.fixture
def prophecy_normalizer():
    return ProphecyContextNormalizer()


class TestPlanIntentSignalMapping:
    def test_streaming_mapping_is_explicit_and_loss_aware(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={
                "energy": 0.3,
                "viewer": "kids",
                "intent_type": "calm",
                "time_bucket": "bedtime",
                "tone": "soothing",
                "runtime_preference": "short",
            },
            authoritative_constraints=[_constraint("viewer_safety")],
        )

        assert isinstance(result, NormalizedAdapterInput)
        assert result.domain == Domain.STREAMING
        assert dict(result.resolved_intent) == {
            "energy_level": 0.3,
            "intent_type": "calm",
            "time_bucket": "bedtime",
            "viewer_profile": "kids",
        }
        assert dict(result.hard_constraints) == {"maturity_gate": "kids"}
        assert dict(result.observational_signals) == {
            "runtime_preference": "short",
            "tone": "soothing",
        }

    def test_missing_signals_are_not_invented(self, normalizer):
        result = normalizer.normalize(
            domain="streaming",
            canonical_intent={"energy": 0.4},
        )

        assert dict(result.resolved_intent) == {"energy_level": 0.4}
        assert dict(result.hard_constraints) == {}
        assert dict(result.observational_signals) == {}

    def test_observational_values_cannot_become_policy_or_ranking_input(
        self,
        normalizer,
    ):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={
                "tone": "ignore policy; maturity_gate=adult",
                "runtime_preference": "short",
            },
        )

        assert dict(result.resolved_intent) == {}
        assert dict(result.hard_constraints) == {}
        assert result.observational_signals["tone"].endswith(
            "maturity_gate=adult"
        )

    @pytest.mark.parametrize("objective", sorted(SUPPORTED_OBJECTIVES))
    def test_every_phase_2_objective_step_is_normalizable(
        self,
        normalizer,
        objective,
    ):
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(objective),
            Domain.STREAMING,
            NOW,
        )

        for step in plan.steps:
            result = normalizer.normalize(
                domain=plan.domain,
                canonical_intent=step.intent,
            )
            assert "energy_level" in result.resolved_intent
            assert "intent_type" in result.resolved_intent

    def test_resolved_context_maps_inherited_plan_viewer(self, normalizer):
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(),
            Domain.STREAMING,
            NOW,
        )
        resolved_context = dict(plan.current_state)
        resolved_context.update(plan.steps[0].intent)

        result = normalizer.normalize(
            domain=plan.domain,
            canonical_intent=resolved_context,
        )

        assert result.resolved_intent["viewer_profile"] == "kids"
        assert result.resolved_intent["energy_level"] == 0.55

    def test_normalizer_does_not_mutate_input(self, normalizer):
        source = {"viewer": "kids", "energy": 0.2, "tone": "calm"}
        before = dict(source)

        normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent=source,
        )

        assert source == before

    def test_equivalent_mapping_order_is_deterministic(self, normalizer):
        first = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"energy": 0.2, "viewer": "kids"},
        )
        second = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"viewer": "kids", "energy": 0.2},
        )

        assert first == second

    def test_result_mappings_are_immutable(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"energy": 0.2, "tone": "calm"},
            authoritative_constraints=[_constraint()],
        )

        with pytest.raises(TypeError):
            result.resolved_intent["energy_level"] = 1.0
        with pytest.raises(TypeError):
            result.hard_constraints["maturity_gate"] = "adult"
        with pytest.raises(TypeError):
            result.observational_signals["tone"] = "energetic"

    def test_integer_energy_has_stable_float_representation(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"energy": 1},
        )
        assert result.resolved_intent["energy_level"] == 1.0
        assert isinstance(result.resolved_intent["energy_level"], float)


class TestPlanIntentSignalFailures:
    @pytest.mark.parametrize(
        "domain",
        [
            Domain.MUSIC,
            Domain.ECOMMERCE,
            Domain.RIDE_MATCHING,
            Domain.FOOD_DELIVERY,
            "not-a-domain",
        ],
    )
    def test_unsupported_domain_fails_closed(self, normalizer, domain):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(domain=domain, canonical_intent={"energy": 0.5})

        assert captured.value.code == "unsupported_domain"

    @pytest.mark.parametrize("value", [None, [], "energy", 4])
    def test_non_mapping_intent_fails_closed(self, normalizer, value):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent=value,
            )

        assert captured.value.code == "invalid_canonical_intent"

    def test_non_string_signal_name_fails_closed(self, normalizer):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={1: "energy"},
            )

        assert captured.value.code == "invalid_canonical_intent"

    @pytest.mark.parametrize(
        "name",
        sorted(FORBIDDEN_SELECTION_SIGNALS)
        + ["Candidate_ID", "FINAL_SCORE", "Selected_Candidate_ID"],
    )
    def test_candidate_selection_signals_receive_specific_failure(
        self,
        normalizer,
        name,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={name: "attacker-controlled"},
            )

        assert captured.value.code == "candidate_selection_forbidden"

    def test_unknown_signal_fails_closed(self, normalizer):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={"ranking_multiplier": 100},
            )

        assert captured.value.code == "unknown_signal"

    @pytest.mark.parametrize(
        "energy",
        [-0.1, 1.1, "0.5", True, float("nan"), float("inf"), 10**10000],
        ids=[
            "below-range",
            "above-range",
            "string",
            "boolean",
            "nan",
            "infinity",
            "huge-int",
        ],
    )
    def test_invalid_energy_fails_closed(self, normalizer, energy):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={"energy": energy},
            )

        assert captured.value.code == "invalid_signal_value"

    @pytest.mark.parametrize("viewer", ["", "children", 1, True])
    def test_invalid_viewer_fails_closed(self, normalizer, viewer):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={"viewer": viewer},
            )

        assert captured.value.code == "invalid_signal_value"

    @pytest.mark.parametrize("intent_type", ["focus", "CALM", "", 4])
    def test_invalid_intent_type_fails_closed(
        self,
        normalizer,
        intent_type,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={"intent_type": intent_type},
            )

        assert captured.value.code == "invalid_signal_value"

    @pytest.mark.parametrize("time_bucket", ["midday", "BEDTIME", "", 4])
    def test_invalid_time_bucket_fails_closed(
        self,
        normalizer,
        time_bucket,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={"time_bucket": time_bucket},
            )

        assert captured.value.code == "invalid_signal_value"


class TestAuthoritativeConstraintNormalization:
    @pytest.mark.parametrize(
        "constraint_type",
        ["maturity_gate", "viewer_safety", "viewer_maturity"],
    )
    def test_maturity_aliases_map_to_adapter_gate(
        self,
        normalizer,
        constraint_type,
    ):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={},
            authoritative_constraints=[_constraint(constraint_type)],
        )

        assert dict(result.hard_constraints) == {"maturity_gate": "kids"}

    @pytest.mark.parametrize(
        "source",
        [ConstraintSource.USER, ConstraintSource.SYSTEM, ConstraintSource.DOMAIN],
    )
    def test_separate_authority_channel_accepts_non_inferred_sources(
        self,
        normalizer,
        source,
    ):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={},
            authoritative_constraints=[_constraint(source=source)],
        )
        assert result.hard_constraints["maturity_gate"] == "kids"

    def test_equivalent_aliases_collapse_deterministically(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={},
            authoritative_constraints=[
                _constraint("viewer_safety", source=ConstraintSource.SYSTEM),
                _constraint("maturity_gate", source=ConstraintSource.DOMAIN),
            ],
        )

        assert dict(result.hard_constraints) == {"maturity_gate": "kids"}

    @pytest.mark.parametrize("reverse", [False, True])
    def test_conflicting_aliases_fail_closed(self, normalizer, reverse):
        constraints = [
            _constraint("viewer_safety", "kids"),
            _constraint(
                "maturity_gate",
                "adult",
                source=ConstraintSource.DOMAIN,
            ),
        ]
        if reverse:
            constraints.reverse()

        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=constraints,
            )

        assert captured.value.code == "conflicting_authoritative_constraint"

    def test_exact_duplicate_authority_fails_closed(self, normalizer):
        constraint = _constraint()
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[constraint, constraint],
            )

        assert captured.value.code == "duplicate_authoritative_constraint"

    @pytest.mark.parametrize("value", ["teen", "family", "adult"])
    def test_unimplemented_maturity_semantics_fail_closed(
        self,
        normalizer,
        value,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[_constraint(value=value)],
            )

        assert captured.value.code == "unsupported_constraint_value"

    @pytest.mark.parametrize(
        "constraint",
        [
            _constraint(hard=False),
            _constraint(source=ConstraintSource.INFERRED),
        ],
        ids=["soft", "inferred"],
    )
    def test_non_authoritative_constraint_fails_closed(
        self,
        normalizer,
        constraint,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[constraint],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    @pytest.mark.parametrize("constraints", [None, "kids", 4, {"gate": "kids"}])
    def test_invalid_authoritative_container_fails_closed(
        self,
        normalizer,
        constraints,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=constraints,
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    def test_untyped_constraint_fails_closed(self, normalizer):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[
                    {
                        "type": "maturity_gate",
                        "value": "kids",
                        "hard": True,
                        "source": "SYSTEM",
                    }
                ],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    def test_unknown_constraint_fails_closed(self, normalizer):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[_constraint("disable_safety", True)],
            )

        assert captured.value.code == "unknown_authoritative_constraint"

    @pytest.mark.parametrize("value", ["unknown-audience", ["kids"], 4, True])
    def test_malformed_maturity_value_fails_closed(
        self,
        normalizer,
        value,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={},
                authoritative_constraints=[_constraint(value=value)],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    def test_viewer_signal_never_manufactures_a_hard_gate(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"viewer": "kids"},
        )

        assert result.resolved_intent["viewer_profile"] == "kids"
        assert dict(result.hard_constraints) == {}

    def test_soft_viewer_cannot_remove_separate_kids_gate(self, normalizer):
        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={"viewer": "adult"},
            authoritative_constraints=[_constraint(value="kids")],
        )

        assert result.resolved_intent["viewer_profile"] == "adult"
        assert result.hard_constraints["maturity_gate"] == "kids"

    def test_authoritative_input_is_copied_and_not_mutated(self, normalizer):
        constraint = _constraint()
        constraints = [constraint]

        result = normalizer.normalize(
            domain=Domain.STREAMING,
            canonical_intent={},
            authoritative_constraints=constraints,
        )
        constraints.clear()

        assert dict(result.hard_constraints) == {"maturity_gate": "kids"}
        assert constraint.value == "kids"

    @pytest.mark.parametrize(
        "name",
        [
            "viewer_safety",
            "viewer_maturity",
            "maturity_gate",
            "block_explicit",
            "constraints",
            "source",
            "hard",
        ],
    )
    def test_policy_shaped_intent_signal_cannot_cross_authority_boundary(
        self,
        normalizer,
        name,
    ):
        with pytest.raises(NormalizationError) as captured:
            normalizer.normalize(
                domain=Domain.STREAMING,
                canonical_intent={name: "SYSTEM"},
            )

        assert captured.value.code == "unknown_signal"


class TestProphecyContextNormalization:
    @pytest.mark.parametrize(
        "source,expected",
        [(0, 0.0), (1, 0.01), (12.5, 0.125), (15, 0.15), (100, 1.0)],
    )
    def test_camel_case_energy_uses_explicit_100_point_scale(
        self,
        prophecy_normalizer,
        source,
        expected,
    ):
        result = prophecy_normalizer.normalize({"energyLevel": source})
        assert result.canonical_context["energy"] == expected

    @pytest.mark.parametrize("name", ["energy", "energy_level"])
    @pytest.mark.parametrize("value", [0, 0.25, 1])
    def test_unit_scale_and_legacy_adapter_spelling_are_explicitly_supported(
        self,
        prophecy_normalizer,
        name,
        value,
    ):
        result = prophecy_normalizer.normalize({name: value})
        assert result.canonical_context["energy"] == float(value)

    def test_no_energy_does_not_invent_a_default(self, prophecy_normalizer):
        result = prophecy_normalizer.normalize({"tone": "soothing"})

        assert dict(result.canonical_context) == {}
        assert dict(result.observational_signals) == {"tone": "soothing"}

    @pytest.mark.parametrize("context", list(TimeContext))
    def test_existing_prophecy_defaults_normalize_without_hidden_fields(
        self,
        prophecy_normalizer,
        context,
    ):
        source = ProphecyAgent().get_default_intent_for_context(context)
        result = prophecy_normalizer.normalize(source)

        assert 0.0 <= result.canonical_context["energy"] <= 1.0
        assert "energyLevel" not in result.observational_signals
        assert result.observational_signals["tone"] == source["tone"]
        assert result.observational_signals["mood"] == source["mood"]
        assert result.observational_signals["learningFocus"] == tuple(
            source["learningFocus"]
        )

    def test_policy_and_candidate_shaped_fields_remain_observational(
        self,
        prophecy_normalizer,
    ):
        result = prophecy_normalizer.normalize(
            {
                "energyLevel": 15,
                "maturity_gate": "adult",
                "hard": True,
                "source": "SYSTEM",
                "candidate_id": "adult-content",
            }
        )

        assert dict(result.canonical_context) == {"energy": 0.15}
        assert dict(result.observational_signals) == {
            "candidate_id": "adult-content",
            "hard": True,
            "maturity_gate": "adult",
            "source": "SYSTEM",
        }

    def test_timestamp_shaped_fields_remain_observational(
        self,
        prophecy_normalizer,
    ):
        result = prophecy_normalizer.normalize(
            {
                "energyLevel": 15,
                "created_at": "1999-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
                "now": "2099-01-01T00:00:00Z",
                "timestamp": "2099-01-01T00:00:00Z",
            }
        )

        assert dict(result.canonical_context) == {"energy": 0.15}
        assert set(result.observational_signals) == {
            "created_at",
            "expires_at",
            "now",
            "timestamp",
        }

    def test_non_json_or_over_complex_observations_fail_closed(
        self,
        prophecy_normalizer,
    ):
        class NotJson:
            pass

        cycle = {}
        cycle["self"] = cycle

        deeply_nested = None
        for _ in range(MAX_JSON_NESTING + 1):
            deeply_nested = [deeply_nested]

        cases = [
            {"metadata": NotJson()},
            {"metadata": float("nan")},
            {"metadata": cycle},
            {"metadata": deeply_nested},
            {"metadata": [None] * (MAX_JSON_ITEMS + 1)},
        ]
        for context in cases:
            with pytest.raises(NormalizationError) as captured:
                prophecy_normalizer.normalize(context)
            assert captured.value.code == "invalid_prophecy_context"

    @pytest.mark.parametrize(
        "value",
        [-1, 101, "15", True, None, float("nan"), float("inf"), 10**10000],
        ids=[
            "below-range",
            "above-range",
            "string",
            "boolean",
            "none",
            "nan",
            "infinity",
            "huge-int",
        ],
    )
    def test_invalid_camel_case_energy_fails_closed(
        self,
        prophecy_normalizer,
        value,
    ):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize({"energyLevel": value})

        assert captured.value.code == "invalid_prophecy_energy"

    @pytest.mark.parametrize(
        "name,value",
        [
            ("energy", -0.1),
            ("energy", 1.1),
            ("energy_level", -0.1),
            ("energy_level", 1.1),
            ("energy_level", "0.5"),
            ("energy", True),
        ],
    )
    def test_invalid_unit_scale_energy_fails_closed(
        self,
        prophecy_normalizer,
        name,
        value,
    ):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize({name: value})

        assert captured.value.code == "invalid_prophecy_energy"

    @pytest.mark.parametrize(
        "context",
        [
            {"energy": 0.15, "energyLevel": 15},
            {"energy": 0.15, "energy_level": 0.15},
            {"energyLevel": 15, "energy_level": 0.15},
        ],
    )
    def test_multiple_energy_spellings_are_always_ambiguous(
        self,
        prophecy_normalizer,
        context,
    ):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize(context)

        assert captured.value.code == "ambiguous_energy_scale"

    @pytest.mark.parametrize("value", [None, [], "energy", 4])
    def test_invalid_context_container_fails_closed(
        self,
        prophecy_normalizer,
        value,
    ):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize(value)

        assert captured.value.code == "invalid_prophecy_context"

    def test_non_string_context_key_fails_closed(self, prophecy_normalizer):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize({1: 15})

        assert captured.value.code == "invalid_prophecy_context"

    @pytest.mark.parametrize(
        "domain",
        [Domain.MUSIC, Domain.ECOMMERCE, Domain.RIDE_MATCHING],
    )
    def test_prophecy_normalization_is_streaming_only(
        self,
        prophecy_normalizer,
        domain,
    ):
        with pytest.raises(NormalizationError) as captured:
            prophecy_normalizer.normalize({"energyLevel": 15}, domain=domain)

        assert captured.value.code == "unsupported_domain"

    def test_prophecy_normalization_is_deterministic_and_pure(
        self,
        prophecy_normalizer,
    ):
        learning_focus = ["emotional", "mindfulness"]
        first_input = {
            "energyLevel": 15,
            "tone": "soothing",
            "learningFocus": learning_focus,
        }
        second_input = {
            "learningFocus": ["emotional", "mindfulness"],
            "tone": "soothing",
            "energyLevel": 15,
        }

        first = prophecy_normalizer.normalize(first_input)
        second = prophecy_normalizer.normalize(second_input)
        learning_focus.append("mutated")

        assert isinstance(first, NormalizedProphecyContext)
        assert first == second
        assert first.observational_signals["learningFocus"] == (
            "emotional",
            "mindfulness",
        )

    def test_nested_prophecy_output_is_recursively_immutable(
        self,
        prophecy_normalizer,
    ):
        result = prophecy_normalizer.normalize(
            {"metadata": {"items": ["one", "two"]}}
        )
        metadata = result.observational_signals["metadata"]

        with pytest.raises(TypeError):
            metadata["other"] = "value"
        with pytest.raises(AttributeError):
            metadata["items"].append("three")

    def test_prophecy_result_mappings_are_immutable(self, prophecy_normalizer):
        result = prophecy_normalizer.normalize(
            {"energyLevel": 15, "tone": "soothing"}
        )

        with pytest.raises(TypeError):
            result.canonical_context["energy"] = 1.0
        with pytest.raises(TypeError):
            result.observational_signals["tone"] = "energetic"


class TestNormalizationBoundaryShape:
    def test_resolved_vocabulary_is_consumed_by_streaming_scoring(self):
        result = PlanIntentNormalizer().normalize(
            domain=Domain.STREAMING,
            canonical_intent={
                "energy": 0.2,
                "viewer": "kids",
                "intent_type": "calm",
                "time_bucket": "bedtime",
            },
        )
        item = Item(
            item_id="kids-calm",
            title="Kids Calm",
            base_score=0.8,
            attributes={
                "calm_score": 0.9,
                "maturity": "kids",
                "complexity": 0.3,
            },
        )

        multipliers = StreamingAdapter().compute_multipliers(
            item,
            result.resolved_intent,
        )

        assert isinstance(multipliers, MultiplierSet)
        assert multipliers.profile > 1.0
        assert multipliers.urgency > 1.0

    def test_normalized_alias_reaches_existing_streaming_hard_gate(self):
        result = PlanIntentNormalizer().normalize(
            domain=Domain.STREAMING,
            canonical_intent={},
            authoritative_constraints=[_constraint("viewer_safety")],
        )
        adult_item = Item(
            item_id="adult",
            title="Adult",
            base_score=1.0,
            attributes={"maturity": "adult"},
        )

        assert StreamingAdapter().apply_hard_constraints(
            adult_item,
            result.hard_constraints,
        ) is True

    def test_plan_normalizer_has_no_candidate_clock_or_adapter_parameter(self):
        parameters = inspect.signature(PlanIntentNormalizer.normalize).parameters
        assert "candidates" not in parameters
        assert "items" not in parameters
        assert "now" not in parameters
        assert "adapter" not in parameters

    def test_prophecy_normalizer_has_no_authority_output(self):
        fields = set(NormalizedProphecyContext.__dataclass_fields__)
        assert "hard_constraints" not in fields
        assert "authoritative_constraints" not in fields
