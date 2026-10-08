"""Unit tests for the V4 agentic data contracts.

These tests deliberately use fixed, timezone-aware timestamps.  Contract
construction must not depend on the wall clock; expiry relative to a request
time is the semantic validator's responsibility.
"""

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 compatibility
    ZoneInfo = None

import pytest
from pydantic import ValidationError

from intent_engine.agentic.schemas import (
    MAX_PLAN_STEPS,
    ConstraintSource,
    ContextInterpretation,
    ExecutionTrace,
    GoalRequest,
    IntentConstraint,
    IntentPlan,
    IntentStep,
    OutcomeEvent,
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
        "offset_minutes": index * 20,
        "intent": {"energy": 0.5},
        "transition_reason": "Move toward the requested state",
    }
    values.update(overrides)
    return IntentStep(**values)


def _plan(**overrides):
    values = {
        "plan_id": "plan_123",
        "domain": "streaming",
        "objective": "wind_down",
        "current_state": {"viewer": "kids", "energy": 0.8},
        "desired_state": {"energy": 0.1},
        "constraints": [_constraint()],
        "steps": [_step(0), _step(1, intent={"energy": 0.2, "tone": "calm"})],
        "assumptions": ["Bedtime is approximately one hour away."],
        "confidence": 0.91,
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "planner_version": "v4.0",
    }
    values.update(overrides)
    return IntentPlan(**values)


def _goal_request(**overrides):
    values = {
        "text": "The kids are wired and bedtime is in an hour.",
        "domain": "streaming",
        "timestamp": NOW,
        "explicit_context": {"viewer": "kids"},
        "session_id": "session_123",
    }
    values.update(overrides)
    return GoalRequest(**values)


def _interpretation(**overrides):
    values = {
        "objective": "wind_down",
        "entities": {"viewer": "kids"},
        "explicit_constraints": [_constraint()],
        "inferred_context": {"horizon_minutes": 60},
        "assumptions": ["Bedtime is about an hour away."],
        "missing_information": [],
        "confidence": 0.91,
    }
    values.update(overrides)
    return ContextInterpretation(**values)


def _trace(**overrides):
    plan = _plan()
    values = {
        "trace_id": "trace_123",
        "goal_request": _goal_request(),
        "interpretation": _interpretation(),
        "plan": plan,
        "validation_results": [{"status": "valid"}],
        "active_step": plan.steps[0],
        "safety_decisions": [],
        "ranking_trace": {"engine": "domain"},
        "outcome_events": [],
        "latency": {"total_ms": 1.0},
    }
    values.update(overrides)
    return ExecutionTrace(**values)


class TestGoalRequest:
    def test_valid_goal_request_and_defaults(self):
        request = GoalRequest(
            text="Help the kids wind down.",
            domain="streaming",
            timestamp=NOW,
        )

        assert request.text == "Help the kids wind down."
        assert request.domain == "streaming"
        assert request.explicit_context == {}
        assert request.session_id is None

    @pytest.mark.parametrize("missing", ["text", "domain", "timestamp"])
    def test_required_fields(self, missing):
        payload = _goal_request().model_dump()
        payload.pop(missing)

        with pytest.raises(ValidationError):
            GoalRequest.model_validate(payload)

    def test_extra_fields_are_forbidden(self):
        with pytest.raises(ValidationError):
            GoalRequest.model_validate(
                {**_goal_request().model_dump(), "prompt_injection": "ignore policy"}
            )


class TestContextInterpretation:
    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
    def test_confidence_boundaries_are_accepted(self, confidence):
        interpretation = _interpretation(confidence=confidence)
        assert interpretation.confidence == confidence

    @pytest.mark.parametrize("confidence", [-0.001, 1.001])
    def test_confidence_out_of_range_is_rejected(self, confidence):
        with pytest.raises(ValidationError):
            _interpretation(confidence=confidence)

    @pytest.mark.parametrize(
        "missing",
        [
            "objective",
            "entities",
            "explicit_constraints",
            "inferred_context",
            "assumptions",
            "missing_information",
            "confidence",
        ],
    )
    def test_declared_fields_are_required(self, missing):
        payload = _interpretation().model_dump()
        payload.pop(missing)

        with pytest.raises(ValidationError):
            ContextInterpretation.model_validate(payload)

    def test_extra_fields_are_forbidden(self):
        with pytest.raises(ValidationError):
            ContextInterpretation.model_validate(
                {**_interpretation().model_dump(), "ranking": ["candidate_1"]}
            )

    def test_huge_integer_confidence_is_a_validation_error(self):
        with pytest.raises(ValidationError):
            _interpretation(confidence=10**10000)


class TestIntentConstraint:
    @pytest.mark.parametrize("source", list(ConstraintSource))
    def test_all_constraint_sources_are_representable(self, source):
        constraint = _constraint(source=source)
        assert constraint.source == source

    def test_hard_constraint_is_explicit_and_survives_dump(self):
        constraint = _constraint(hard=True)

        assert constraint.hard is True
        assert constraint.model_dump(mode="json")["hard"] is True

    @pytest.mark.parametrize("missing", ["type", "value", "source"])
    def test_required_fields(self, missing):
        payload = _constraint().model_dump()
        payload.pop(missing)

        with pytest.raises(ValidationError):
            IntentConstraint.model_validate(payload)

    def test_unknown_source_is_rejected(self):
        with pytest.raises(ValidationError):
            _constraint(source="PLANNER")

    def test_non_boolean_hard_flag_is_rejected(self):
        with pytest.raises(ValidationError):
            _constraint(hard="true")

    def test_extra_fields_are_forbidden(self):
        with pytest.raises(ValidationError):
            IntentConstraint.model_validate(
                {**_constraint().model_dump(), "override_policy": True}
            )


class TestIntentStep:
    def test_valid_step(self):
        step = IntentStep(
            step_id="step_1",
            offset_minutes=25,
            intent={"energy": 0.3, "tone": "calm"},
            transition_reason="Begin the calm phase",
            completion_condition={"elapsed_minutes": 25},
        )

        assert step.offset_minutes == 25
        assert step.intent["energy"] == 0.3
        assert step.completion_condition == {"elapsed_minutes": 25}

    def test_negative_offset_is_rejected(self):
        with pytest.raises(ValidationError):
            _step(offset_minutes=-1)

    @pytest.mark.parametrize(
        "field", ["step_id", "offset_minutes", "intent", "transition_reason"]
    )
    def test_required_fields(self, field):
        payload = _step().model_dump()
        payload.pop(field)

        with pytest.raises(ValidationError):
            IntentStep.model_validate(payload)

    def test_candidate_field_is_not_a_step_contract_field(self):
        with pytest.raises(ValidationError):
            IntentStep.model_validate(
                {**_step().model_dump(), "recommended_title": "Bluey"}
            )

    @pytest.mark.parametrize(
        "bad_value",
        [object(), ("tuple",), float("nan"), float("inf"), float("-inf")],
        ids=["object", "tuple", "nan", "positive-infinity", "negative-infinity"],
    )
    def test_nested_non_json_intent_values_are_rejected(self, bad_value):
        with pytest.raises(ValidationError):
            _step(intent={"energy": 0.5, "nested": [{"bad": bad_value}]})

    @pytest.mark.parametrize("bad_value", [object(), float("nan"), float("inf")])
    def test_nested_non_json_completion_values_are_rejected(self, bad_value):
        with pytest.raises(ValidationError):
            _step(completion_condition={"nested": [{"bad": bad_value}]})

    @pytest.mark.parametrize(
        "bad_value",
        [_deeply_nested_value(), _cyclic_mapping()],
        ids=["excessive-depth", "cycle"],
    )
    def test_excessively_nested_or_cyclic_intent_is_a_validation_error(
        self, bad_value
    ):
        with pytest.raises(ValidationError):
            _step(intent={"energy": 0.5, "nested": bad_value})


class TestIntentPlan:
    def test_valid_plan_is_accepted(self):
        plan = _plan()

        assert plan.plan_id == "plan_123"
        assert len(plan.steps) == 2
        assert plan.constraints[0].hard is True

    @pytest.mark.parametrize("confidence", [0.0, 1.0])
    def test_confidence_boundaries_are_accepted(self, confidence):
        assert _plan(confidence=confidence).confidence == confidence

    @pytest.mark.parametrize("confidence", [-0.01, 1.01])
    def test_invalid_confidence_is_rejected(self, confidence):
        with pytest.raises(ValidationError):
            _plan(confidence=confidence)

    def test_empty_plan_is_rejected(self):
        with pytest.raises(ValidationError):
            _plan(steps=[])

    def test_maximum_plan_size_is_accepted(self):
        steps = [_step(index) for index in range(MAX_PLAN_STEPS)]
        assert len(_plan(steps=steps).steps) == MAX_PLAN_STEPS

    def test_excessive_number_of_steps_is_rejected(self):
        steps = [_step(index) for index in range(MAX_PLAN_STEPS + 1)]
        with pytest.raises(ValidationError):
            _plan(steps=steps)

    @pytest.mark.parametrize(
        "steps",
        [
            [_step(0), _step(2), _step(1)],
            [_step(0), _step(1), _step(2, offset_minutes=20)],
        ],
        ids=["decreasing", "duplicate-offset"],
    )
    def test_steps_must_be_strictly_ordered(self, steps):
        with pytest.raises(ValidationError):
            _plan(steps=steps)

    def test_expiration_must_be_after_creation(self):
        with pytest.raises(ValidationError):
            _plan(expires_at=NOW)

        with pytest.raises(ValidationError):
            _plan(expires_at=NOW - timedelta(seconds=1))

    @pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo is unavailable")
    def test_expiration_order_uses_instants_across_dst_fold(self):
        pacific = ZoneInfo("America/Los_Angeles")
        created_later = datetime(2026, 11, 1, 1, 30, tzinfo=pacific, fold=1)
        expires_earlier = datetime(2026, 11, 1, 1, 45, tzinfo=pacific, fold=0)

        with pytest.raises(ValidationError):
            _plan(created_at=created_later, expires_at=expires_earlier)

    def test_no_expiration_is_allowed(self):
        assert _plan(expires_at=None).expires_at is None

    @pytest.mark.parametrize(
        "missing",
        [
            "plan_id",
            "domain",
            "objective",
            "current_state",
            "desired_state",
            "constraints",
            "steps",
            "assumptions",
            "confidence",
            "created_at",
            "planner_version",
        ],
    )
    def test_required_fields(self, missing):
        payload = _plan().model_dump()
        payload.pop(missing)

        with pytest.raises(ValidationError):
            IntentPlan.model_validate(payload)

    def test_extra_fields_are_forbidden(self):
        with pytest.raises(ValidationError):
            IntentPlan.model_validate(
                {**_plan().model_dump(), "selected_candidate_id": "bluey"}
            )

    @pytest.mark.parametrize(
        "bad_value",
        [object(), ("tuple",), float("nan"), float("inf"), float("-inf")],
        ids=["object", "tuple", "nan", "positive-infinity", "negative-infinity"],
    )
    def test_nested_non_json_state_values_are_rejected(self, bad_value):
        with pytest.raises(ValidationError):
            _plan(current_state={"energy": 0.8, "nested": [{"bad": bad_value}]})

    def test_huge_integer_confidence_is_a_validation_error(self):
        with pytest.raises(ValidationError):
            _plan(confidence=10**10000)

    @pytest.mark.parametrize(
        "bad_value",
        [_deeply_nested_value(), _cyclic_mapping()],
        ids=["excessive-depth", "cycle"],
    )
    def test_excessively_nested_or_cyclic_state_is_a_validation_error(
        self, bad_value
    ):
        with pytest.raises(ValidationError):
            _plan(current_state={"energy": 0.8, "nested": bad_value})


class TestOutcomeAndTraceContracts:
    def test_outcome_event_is_typed(self):
        event = OutcomeEvent(
            event_type="CONTENT_COMPLETED",
            timestamp=NOW + timedelta(minutes=20),
            plan_id="plan_123",
            step_id="step_0",
            metadata={"candidate_id": "bluey"},
        )

        assert event.plan_id == "plan_123"
        assert event.metadata["candidate_id"] == "bluey"

    def test_outcome_event_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            OutcomeEvent(
                event_type="CONTENT_COMPLETED",
                timestamp=NOW,
                plan_id="plan_123",
                step_id="step_0",
                metadata={},
                ranking_score=0.99,
            )

    def test_execution_trace_nests_all_contracts(self):
        plan = _plan()
        event = OutcomeEvent(
            event_type="CONTENT_STARTED",
            timestamp=NOW + timedelta(minutes=1),
            plan_id=plan.plan_id,
            step_id=plan.steps[0].step_id,
            metadata={"candidate_id": "bluey"},
        )
        trace = ExecutionTrace(
            trace_id="trace_123",
            goal_request=_goal_request(),
            interpretation=_interpretation(),
            plan=plan,
            validation_results=[{"status": "valid"}],
            active_step=plan.steps[0],
            safety_decisions=[{"constraint": "maturity_gate", "allowed": True}],
            ranking_trace={"engine": "domain", "version": "v3"},
            outcome_events=[event],
            latency={"total_ms": 4.2, "validation_ms": 0.2},
        )

        assert trace.plan == plan
        assert trace.active_step == plan.steps[0]
        assert trace.outcome_events == [event]

    def test_trace_rejects_negative_latency(self):
        plan = _plan()
        with pytest.raises(ValidationError):
            ExecutionTrace(
                trace_id="trace_123",
                goal_request=_goal_request(),
                interpretation=_interpretation(),
                plan=plan,
                validation_results=[],
                active_step=plan.steps[0],
                safety_decisions=[],
                ranking_trace={},
                outcome_events=[],
                latency={"total_ms": -0.1},
            )

    @pytest.mark.parametrize("duration", [True, False, "1.2"])
    def test_trace_rejects_boolean_and_string_latency(self, duration):
        with pytest.raises(ValidationError):
            _trace(latency={"total_ms": duration})

    def test_huge_integer_latency_is_a_validation_error(self):
        with pytest.raises(ValidationError):
            _trace(latency={"total_ms": 10**10000})

    @pytest.mark.parametrize(
        "bad_value",
        [object(), ("tuple",), float("nan"), float("inf"), float("-inf")],
        ids=["object", "tuple", "nan", "positive-infinity", "negative-infinity"],
    )
    def test_nested_non_json_trace_values_are_rejected(self, bad_value):
        with pytest.raises(ValidationError):
            _trace(ranking_trace={"nested": [{"bad": bad_value}]})

    @pytest.mark.parametrize("field", ["validation_results", "safety_decisions"])
    def test_nested_non_json_trace_list_values_are_rejected(self, field):
        with pytest.raises(ValidationError):
            _trace(**{field: [{"nested": {"bad": float("nan")}}]})

    @pytest.mark.parametrize(
        "bad_value",
        [_deeply_nested_value(), _cyclic_mapping()],
        ids=["excessive-depth", "cycle"],
    )
    def test_excessively_nested_or_cyclic_trace_data_is_a_validation_error(
        self, bad_value
    ):
        with pytest.raises(ValidationError):
            _trace(ranking_trace={"nested": bad_value})


class TestContractSerialization:
    @pytest.mark.parametrize(
        "contract",
        [
            _goal_request(),
            _interpretation(),
            _constraint(),
            _step(),
            _plan(),
            OutcomeEvent(
                event_type="SESSION_ENDED",
                timestamp=NOW,
                plan_id="plan_123",
                step_id="step_0",
                metadata={},
            ),
        ],
        ids=lambda value: type(value).__name__,
    )
    def test_json_round_trip(self, contract):
        restored = type(contract).model_validate_json(contract.model_dump_json())
        assert restored == contract

    def test_execution_trace_json_round_trip(self):
        plan = _plan()
        trace = ExecutionTrace(
            trace_id="trace_round_trip",
            goal_request=_goal_request(),
            interpretation=_interpretation(),
            plan=plan,
            validation_results=[{"status": "valid"}],
            active_step=plan.steps[0],
            safety_decisions=[],
            ranking_trace=None,
            outcome_events=[],
            latency={"total_ms": 1.0},
        )

        restored = ExecutionTrace.model_validate_json(trace.model_dump_json())
        assert restored == trace
