"""Tests for the deterministic V4 streaming context interpreter."""

from datetime import datetime, timezone
import inspect
import json

import pytest

from intent_engine.agentic import (
    ConstraintSource,
    ContextInterpretation,
    ContextInterpreter,
    GoalRequest,
    InterpretationError,
    RuleBasedContextInterpreter,
)
from intent_engine.schemas import Domain


NOW = datetime(2026, 10, 8, 19, 0, tzinfo=timezone.utc)


def _goal(text="Bedtime.", *, domain=Domain.STREAMING, context=None):
    return GoalRequest(
        text=text,
        domain=domain,
        timestamp=NOW,
        explicit_context={} if context is None else context,
    )


@pytest.fixture
def interpreter():
    return RuleBasedContextInterpreter()


class TestCanonicalRules:
    @pytest.mark.parametrize(
        "text,objective",
        [
            ("Bedtime.", "wind_down"),
            ("Please wind them down.", "wind_down"),
            ("Keep it calm.", "wind_down"),
            ("Family movie night.", "family_time"),
            ("Help me focus.", "focus"),
            ("Something educational.", "focus"),
            ("A quick session.", "quick_session"),
            ("Keep it under 30 minutes.", "quick_session"),
            ("Something high-energy.", "high_energy"),
        ],
    )
    def test_canonical_pilot_phrases_map_to_planner_objectives(
        self,
        interpreter,
        text,
        objective,
    ):
        result = interpreter.interpret(_goal(text))

        assert isinstance(result, ContextInterpretation)
        assert result.objective == objective

    def test_bedtime_example_extracts_only_canonical_planning_context(
        self,
        interpreter,
    ):
        result = interpreter.interpret(
            _goal("The kids are wired and bedtime is in an hour. Keep it calm.")
        )

        assert result.objective == "wind_down"
        assert result.entities == {"viewer": "kids", "energy": 0.9}
        assert result.inferred_context == {"horizon_minutes": 60}
        assert result.missing_information == []
        assert [
            constraint.model_dump(mode="json")
            for constraint in result.explicit_constraints
        ] == [
            {
                "type": "viewer_maturity",
                "value": "kids",
                "hard": False,
                "source": "INFERRED",
            }
        ]

    def test_explicit_context_uses_canonical_types_and_user_provenance(
        self,
        interpreter,
    ):
        context = {
            "viewer": " KIDS ",
            "energy": 1,
            "horizon_minutes": 45,
        }

        result = interpreter.interpret(_goal("Wind down.", context=context))

        assert context == {
            "viewer": " KIDS ",
            "energy": 1,
            "horizon_minutes": 45,
        }
        assert result.entities == {"viewer": "kids", "energy": 1.0}
        assert result.inferred_context == {"horizon_minutes": 45}
        assert result.explicit_constraints[0].source == ConstraintSource.USER
        assert result.explicit_constraints[0].hard is False

    def test_explicit_context_takes_precedence_over_text_inference(
        self,
        interpreter,
    ):
        result = interpreter.interpret(
            _goal(
                "The kids are wired at bedtime in an hour.",
                context={
                    "viewer": "adult",
                    "energy": 0.4,
                    "horizon_minutes": 75,
                },
            )
        )

        assert result.entities == {"viewer": "adult", "energy": 0.4}
        assert result.inferred_context == {"horizon_minutes": 75}

    @pytest.mark.parametrize(
        "text,expected_minutes",
        [
            ("A quick show under 20 minutes.", 20),
            ("A quick session for 2 hours.", 120),
            ("A quick session in half an hour.", 30),
            ("A 25 minute session, please.", 25),
        ],
    )
    def test_numeric_horizons_are_parsed_deterministically(
        self,
        interpreter,
        text,
        expected_minutes,
    ):
        result = interpreter.interpret(_goal(text))

        assert result.inferred_context == {"horizon_minutes": expected_minutes}

    def test_negated_objective_word_does_not_create_false_ambiguity(
        self,
        interpreter,
    ):
        result = interpreter.interpret(_goal("Bedtime: calm, not exciting."))

        assert result.objective == "wind_down"

    def test_missing_safe_context_is_declared_in_stable_order(
        self,
        interpreter,
    ):
        result = interpreter.interpret(_goal("Family movie night."))

        assert result.missing_information == [
            "energy",
            "viewer",
            "horizon_minutes",
        ]


class TestTrustBoundary:
    def test_interface_accepts_goal_only_and_has_no_candidate_input(self):
        assert isinstance(RuleBasedContextInterpreter(), ContextInterpreter)
        parameters = inspect.signature(
            RuleBasedContextInterpreter.interpret
        ).parameters
        assert list(parameters) == ["self", "goal_request"]

    def test_all_interpreted_constraints_remain_soft_and_untrusted(
        self,
        interpreter,
    ):
        for goal in (
            _goal("Bedtime for kids."),
            _goal("Bedtime.", context={"viewer": "kids"}),
        ):
            result = interpreter.interpret(goal)
            assert result.explicit_constraints
            assert all(not constraint.hard for constraint in result.explicit_constraints)
            assert {
                constraint.source for constraint in result.explicit_constraints
            } <= {ConstraintSource.USER, ConstraintSource.INFERRED}

    @pytest.mark.parametrize(
        "field",
        [
            "candidates",
            "constraints",
            "hard",
            "item_id",
            "normalized_intent",
            "session_id",
            "timestamp",
        ],
    )
    def test_unknown_or_privileged_context_fields_fail_closed(
        self,
        interpreter,
        field,
    ):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal("Bedtime.", context={field: "forged"}))

        assert captured.value.code == "unsupported_context"

    def test_output_never_carries_candidate_selection_data(
        self,
        interpreter,
    ):
        result = interpreter.interpret(
            _goal("Show Bluey at bedtime for the kids.")
        )
        serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)

        for forbidden in ("candidate_id", "item_id", "ranked_items", "score"):
            assert forbidden not in serialized
        assert "Bluey" not in serialized

    def test_mutated_nested_context_is_revalidated(self, interpreter):
        goal = _goal("Bedtime.")
        goal.explicit_context["candidates"] = [{"item_id": "bluey"}]

        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(goal)

        assert captured.value.code == "unsupported_context"


class TestDeterminism:
    def test_identical_goal_produces_identical_interpretation_and_json(
        self,
        interpreter,
    ):
        goal = _goal(
            "The kids are wired and bedtime is in an hour.",
            context={"horizon_minutes": 60},
        )

        first = interpreter.interpret(goal)
        second = interpreter.interpret(goal)

        assert first == second
        assert first.model_dump_json() == second.model_dump_json()

    def test_request_timestamp_does_not_change_interpretation(
        self,
        interpreter,
    ):
        first = interpreter.interpret(_goal("Bedtime."))
        later = _goal("Bedtime.").model_copy(
            update={"timestamp": datetime(2030, 1, 1, tzinfo=timezone.utc)}
        )

        assert interpreter.interpret(later) == first


class TestFailClosedErrors:
    def test_unsupported_goal_has_stable_code(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal("Recommend something interesting."))

        assert captured.value.code == "unsupported_goal"

    def test_composite_goal_has_stable_ambiguous_code(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(
                _goal("Help us focus and then wind down for bedtime.")
            )

        assert captured.value.code == "ambiguous_goal"

    def test_non_streaming_domain_is_rejected(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(
                _goal("Get there quickly.", domain=Domain.RIDE_MATCHING)
            )

        assert captured.value.code == "unsupported_domain"

    @pytest.mark.parametrize(
        "context",
        [
            {"viewer": "children"},
            {"viewer": True},
            {"energy": True},
            {"energy": 1.01},
            {"horizon_minutes": 30.0},
            {"horizon_minutes": True},
        ],
    )
    def test_invalid_explicit_context_has_stable_code(
        self,
        interpreter,
        context,
    ):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal("Bedtime.", context=context))

        assert captured.value.code == "invalid_context"

    def test_contract_invalid_context_is_revalidated_as_invalid_goal(self, interpreter):
        goal = _goal("Bedtime.")
        goal.explicit_context["energy"] = float("nan")

        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(goal)

        assert captured.value.code == "invalid_goal"

    @pytest.mark.parametrize(
        "text,context",
        [
            ("Wind down in 5 minutes.", None),
            ("Wind down in 300 minutes.", None),
            ("A quick session under -5 minutes.", None),
            ("Bedtime.", {"horizon_minutes": 10}),
        ],
    )
    def test_out_of_range_horizon_has_stable_code(
        self,
        interpreter,
        text,
        context,
    ):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal(text, context=context))

        assert captured.value.code == "invalid_horizon"

    def test_conflicting_text_horizons_are_rejected(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(
                _goal("A quick session in 20 minutes, but under 30 minutes.")
            )

        assert captured.value.code == "ambiguous_horizon"

    def test_conflicting_text_viewers_are_rejected(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal("Bedtime for kids and adults."))

        assert captured.value.code == "ambiguous_viewer"

    def test_conflicting_current_energy_is_rejected(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(
                _goal("The kids are wired but they are tired at bedtime.")
            )

        assert captured.value.code == "ambiguous_energy"

    def test_goal_length_is_bounded(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret(_goal("bedtime " + ("x" * 4090)))

        assert captured.value.code == "goal_too_long"

    def test_non_goal_request_is_rejected(self, interpreter):
        with pytest.raises(InterpretationError) as captured:
            interpreter.interpret({"text": "bedtime"})

        assert captured.value.code == "invalid_goal"
