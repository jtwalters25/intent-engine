"""Tests for the deterministic Phase 3B orchestration boundary."""

from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import inspect

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 compatibility
    ZoneInfo = None

import pytest

import intent_engine.agentic.orchestrator as orchestrator_module
from intent_engine.agentic import (
    DEFAULT_DOMAIN_CAPABILITIES,
    ActivePlanStep,
    ConstraintSource,
    ContextInterpretation,
    DomainCapabilities,
    IntentConstraint,
    IntentOrchestrator,
    NormalizationError,
    NormalizedAdapterInput,
    OrchestrationError,
    PlanValidator,
    PlanValidationError,
    PreparedPlanExecution,
    RuleBasedIntentPlanner,
    ValueKind,
    ValueRule,
)
from intent_engine.schemas import Domain


NOW = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)


def _interpretation(*, viewer="kids", energy=0.85):
    return ContextInterpretation(
        objective="wind_down",
        entities={"viewer": viewer, "energy": energy},
        explicit_constraints=[],
        inferred_context={"horizon_minutes": 60},
        assumptions=[],
        missing_information=[],
        confidence=0.91,
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


def _plan(*, viewer="kids", constraints=()):
    return RuleBasedIntentPlanner().create_plan(
        _interpretation(viewer=viewer),
        Domain.STREAMING,
        NOW,
        authoritative_constraints=constraints,
    )


class _ChangingConstraintSequence(Sequence):
    """Yield a constraint once, then go empty to expose double consumption."""

    def __init__(self, constraint):
        self.constraint = constraint
        self.iterations = 0

    def __len__(self):
        return 1

    def __getitem__(self, index):
        if index == 0:
            return self.constraint
        raise IndexError

    def __iter__(self):
        self.iterations += 1
        if self.iterations == 1:
            return iter((self.constraint,))
        return iter(())


class _BrokenConstraintSequence(Sequence):
    def __len__(self):
        return 1

    def __getitem__(self, index):
        raise RuntimeError("sequence changed while reading")

    def __iter__(self):
        raise RuntimeError("sequence changed while reading")


@pytest.fixture
def orchestrator():
    return IntentOrchestrator()


class TestTrustedTimeStepSelection:
    @pytest.mark.parametrize(
        "elapsed,step_index,energy",
        [
            (timedelta(0), 0, 0.55),
            (timedelta(minutes=24, seconds=59), 0, 0.55),
            (timedelta(minutes=25), 1, 0.30),
            (timedelta(minutes=49, seconds=59), 1, 0.30),
            (timedelta(minutes=50), 2, 0.10),
            (timedelta(minutes=59, seconds=59), 2, 0.10),
        ],
    )
    def test_latest_started_step_is_active_at_exact_boundaries(
        self,
        orchestrator,
        elapsed,
        step_index,
        energy,
    ):
        plan = _plan()

        result = orchestrator.prepare_execution(
            plan,
            now=NOW + elapsed,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert result.active_step.step_id == plan.steps[step_index].step_id
        assert result.active_step.offset_minutes == plan.steps[step_index].offset_minutes
        assert result.canonical_intent["energy"] == energy
        assert result.normalized_input.resolved_intent["energy_level"] == energy

    def test_subminute_time_does_not_round_into_next_step(self, orchestrator):
        plan = _plan()

        result = orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25) - timedelta(microseconds=1),
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert result.active_step.step_id == plan.steps[0].step_id

    def test_pre_start_plan_fails_closed(self, orchestrator):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW - timedelta(microseconds=1),
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "plan_not_started"
        assert captured.value.path == "now"

    def test_plan_with_no_started_step_fails_closed(self, orchestrator):
        plan = _plan()
        shifted_steps = [
            step.model_copy(update={"offset_minutes": offset})
            for step, offset in zip(plan.steps, (5, 25, 50))
        ]
        shifted_plan = plan.model_copy(update={"steps": shifted_steps})

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                shifted_plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "no_active_step"
        assert captured.value.path == "steps"

    @pytest.mark.parametrize(
        "elapsed",
        [timedelta(minutes=60), timedelta(minutes=61)],
    )
    def test_expired_plan_is_stopped(self, orchestrator, elapsed):
        with pytest.raises(PlanValidationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW + elapsed,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert "expired_plan" in {issue.code for issue in captured.value.issues}

    def test_just_before_expiry_remains_active(self, orchestrator):
        result = orchestrator.prepare_execution(
            _plan(),
            now=NOW + timedelta(minutes=60) - timedelta(microseconds=1),
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert result.active_step.offset_minutes == 50

    def test_timezone_mismatch_fails_closed(self, orchestrator):
        with pytest.raises(PlanValidationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW.replace(tzinfo=None),
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert "timezone_mismatch" in {
            issue.code for issue in captured.value.issues
        }

    def test_created_at_timezone_is_checked_without_expiry(self, orchestrator):
        plan = _plan().model_copy(update={"expires_at": None})

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW.replace(tzinfo=None),
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "timezone_mismatch"

    @pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo is unavailable")
    def test_fall_back_fold_uses_elapsed_instant_time(self, orchestrator):
        pacific = ZoneInfo("America/Los_Angeles")
        created_at = datetime(2026, 11, 1, 1, 30, tzinfo=pacific, fold=0)
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(),
            Domain.STREAMING,
            created_at,
        )
        actual_t_plus_15 = datetime(2026, 11, 1, 1, 45, tzinfo=pacific, fold=0)
        actual_t_plus_45 = datetime(2026, 11, 1, 1, 15, tzinfo=pacific, fold=1)

        first = orchestrator.prepare_execution(
            plan,
            now=actual_t_plus_15,
            active_profile_context={},
            authoritative_constraints=(),
        )
        result = orchestrator.prepare_execution(
            plan,
            now=actual_t_plus_45,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert first.active_step.offset_minutes == 0
        assert result.active_step.offset_minutes == 25
        assert (
            plan.expires_at.astimezone(timezone.utc)
            - plan.created_at.astimezone(timezone.utc)
        ) == timedelta(minutes=60)

    @pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo is unavailable")
    def test_spring_forward_gap_uses_elapsed_instant_time(self, orchestrator):
        pacific = ZoneInfo("America/Los_Angeles")
        created_at = datetime(2026, 3, 8, 1, 30, tzinfo=pacific)
        plan = RuleBasedIntentPlanner().create_plan(
            _interpretation(),
            Domain.STREAMING,
            created_at,
        )
        actual_t_plus_30 = datetime(2026, 3, 8, 3, 0, tzinfo=pacific)

        result = orchestrator.prepare_execution(
            plan,
            now=actual_t_plus_30,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert result.active_step.offset_minutes == 25
        assert (
            plan.expires_at.astimezone(timezone.utc)
            - plan.created_at.astimezone(timezone.utc)
        ) == timedelta(minutes=60)

    @pytest.mark.parametrize("value", [None, "now", 0, object()])
    def test_now_must_be_an_explicit_datetime(self, orchestrator, value):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=value,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "invalid_now"


class TestContextPrecedence:
    def test_active_step_overrides_ordinary_current_state(self, orchestrator):
        plan = _plan()

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert plan.current_state["energy"] == 0.85
        assert plan.steps[0].intent["energy"] == 0.55
        assert result.canonical_intent["energy"] == 0.55

    def test_step_wins_when_same_ordinary_signal_exists_in_state(
        self,
        orchestrator,
    ):
        plan = _plan()
        current_state = dict(plan.current_state)
        current_state["intent_type"] = "popular"
        changed = plan.model_copy(update={"current_state": current_state})

        result = orchestrator.prepare_execution(
            changed,
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert result.canonical_intent["intent_type"] == "calm"

    def test_plan_viewer_is_inherited_when_step_omits_it(self, orchestrator):
        plan = _plan(viewer="family")

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert "viewer" not in plan.steps[0].intent
        assert result.canonical_intent["viewer"] == "family"
        assert result.normalized_input.resolved_intent["viewer_profile"] == "family"

    def test_trusted_profile_wins_over_plan_state(self, orchestrator):
        trusted_gate = _constraint()
        plan = _plan(viewer="adult", constraints=[trusted_gate])

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=[trusted_gate],
        )

        assert plan.current_state["viewer"] == "adult"
        assert result.canonical_intent["viewer"] == "kids"
        assert result.normalized_input.resolved_intent["viewer_profile"] == "kids"
        assert result.normalized_input.hard_constraints["maturity_gate"] == "kids"

    def test_trusted_profile_wins_over_active_step_impersonation(
        self,
        orchestrator,
    ):
        gate = _constraint()
        plan = _plan(constraints=[gate])
        first_intent = dict(plan.steps[0].intent)
        first_intent["viewer"] = "adult"
        changed_step = plan.steps[0].model_copy(update={"intent": first_intent})
        changed = plan.model_copy(
            update={"steps": [changed_step] + list(plan.steps[1:])}
        )

        result = orchestrator.prepare_execution(
            changed,
            now=NOW,
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=[gate],
        )

        assert result.active_step.intent["viewer"] == "adult"
        assert result.canonical_intent["viewer"] == "kids"
        assert result.normalized_input.resolved_intent["viewer_profile"] == "kids"

    @pytest.mark.parametrize("value", [None, [], "kids", 7])
    def test_active_profile_context_must_be_a_mapping(
        self,
        orchestrator,
        value,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context=value,
                authoritative_constraints=(),
            )

        assert captured.value.code == "invalid_active_profile_context"

    def test_non_string_profile_key_fails_closed(self, orchestrator):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={1: "kids"},
                authoritative_constraints=(),
            )

        assert captured.value.code == "invalid_active_profile_context"

    @pytest.mark.parametrize(
        "profile",
        [
            {"energy": 0.1},
            {"viewer_profile": "kids"},
            {"candidate_id": "bluey"},
            {"viewer": "kids", "role": "admin"},
        ],
    )
    def test_non_profile_signals_cannot_enter_the_trusted_channel(
        self,
        orchestrator,
        profile,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context=profile,
                authoritative_constraints=(),
            )

        assert captured.value.code == "unknown_active_profile_signal"

    @pytest.mark.parametrize(
        "viewer",
        [None, True, 1, "", "child", "KIDS"],
    )
    def test_invalid_trusted_viewer_fails_closed(
        self,
        orchestrator,
        viewer,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={"viewer": viewer},
                authoritative_constraints=(),
            )

        assert captured.value.code == "invalid_active_profile_value"
        assert captured.value.path == "active_profile_context.viewer"

    def test_trusted_kids_profile_requires_matching_safety_gate(
        self,
        orchestrator,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={"viewer": "kids"},
                authoritative_constraints=(),
            )

        assert captured.value.code == "missing_profile_safety_constraint"

    def test_profile_validation_uses_injected_capabilities(self):
        base = DEFAULT_DOMAIN_CAPABILITIES[Domain.STREAMING]
        signals = dict(base.signals)
        signals["viewer"] = ValueRule(
            ValueKind.STRING,
            allowed_values=frozenset({"kids"}),
        )
        validator = PlanValidator(
            capabilities={
                Domain.STREAMING: DomainCapabilities(
                    signals=signals,
                    constraints=base.constraints,
                )
            }
        )
        orchestrator = IntentOrchestrator(validator=validator)

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={"viewer": "adult"},
                authoritative_constraints=(),
            )

        assert captured.value.code == "invalid_active_profile_value"


class TestAuthorityBoundary:
    def test_separate_authoritative_constraint_reaches_normalizer(
        self,
        orchestrator,
    ):
        trusted_gate = _constraint("viewer_safety")
        plan = _plan(constraints=[trusted_gate])

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=[trusted_gate],
        )

        assert dict(result.normalized_input.hard_constraints) == {
            "maturity_gate": "kids"
        }

    def test_plan_source_label_without_trusted_corroboration_is_rejected(
        self,
        orchestrator,
    ):
        labelled_gate = _constraint(source=ConstraintSource.SYSTEM)
        plan = _plan(constraints=[labelled_gate])

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "untrusted_plan_constraint_authority"

    def test_new_authoritative_constraint_must_be_preserved_in_plan(
        self,
        orchestrator,
    ):
        with pytest.raises(PlanValidationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={"viewer": "kids"},
                authoritative_constraints=[_constraint()],
            )

        assert "hard_constraint_weakened" in {
            issue.code for issue in captured.value.issues
        }

    def test_soft_authoritative_constraint_fails_closed(self, orchestrator):
        soft = _constraint(hard=False, source=ConstraintSource.USER)
        plan = _plan().model_copy(update={"constraints": [soft]})

        with pytest.raises(NormalizationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=[soft],
            )

        assert captured.value.code == "invalid_authoritative_constraint"

    def test_inferred_authoritative_constraint_fails_closed(self, orchestrator):
        inferred = _constraint(source=ConstraintSource.INFERRED)
        plan = _plan().model_copy(update={"constraints": [inferred]})

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=[inferred],
            )

        assert captured.value.code == "untrusted_plan_constraint_authority"

    @pytest.mark.parametrize(
        "source",
        [ConstraintSource.SYSTEM, ConstraintSource.DOMAIN],
    )
    def test_soft_plan_constraint_cannot_claim_privileged_source(
        self,
        orchestrator,
        source,
    ):
        soft = _constraint(hard=False, source=source)
        plan = _plan().model_copy(update={"constraints": [soft]})

        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert captured.value.code == "untrusted_plan_constraint_authority"

    def test_malformed_authoritative_constraint_fails_validation(
        self,
        orchestrator,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={},
                authoritative_constraints=["maturity_gate"],
            )

        assert captured.value.code == "invalid_authoritative_constraint"
        assert captured.value.path == "authoritative_constraints.0"

    @pytest.mark.parametrize("constraints", [None, "maturity_gate", object()])
    def test_authoritative_constraints_must_be_an_explicit_sequence(
        self,
        orchestrator,
        constraints,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={},
                authoritative_constraints=constraints,
            )

        assert captured.value.code == "invalid_authoritative_constraints"

    def test_constraint_sequence_is_snapshotted_once(self, orchestrator):
        gate = _constraint()
        plan = _plan(constraints=[gate])
        changing = _ChangingConstraintSequence(gate)

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=changing,
        )

        assert changing.iterations == 1
        assert result.normalized_input.hard_constraints["maturity_gate"] == "kids"

    def test_constraint_sequence_iteration_failure_is_structured(
        self,
        orchestrator,
    ):
        with pytest.raises(OrchestrationError) as captured:
            orchestrator.prepare_execution(
                _plan(),
                now=NOW,
                active_profile_context={},
                authoritative_constraints=_BrokenConstraintSequence(),
            )

        assert captured.value.code == "invalid_authoritative_constraints"


class TestExecutionTimeRevalidation:
    def test_nested_plan_mutation_is_rejected(self, orchestrator):
        plan = _plan()
        plan.current_state["unknown_signal"] = "injected"

        with pytest.raises(PlanValidationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert "unknown_signal" in {issue.code for issue in captured.value.issues}

    def test_candidate_selection_mutation_is_rejected(self, orchestrator):
        plan = _plan()
        plan.steps[0].intent["selected_candidate_id"] = "bluey"

        with pytest.raises(PlanValidationError) as captured:
            orchestrator.prepare_execution(
                plan,
                now=NOW,
                active_profile_context={},
                authoritative_constraints=(),
            )

        assert "candidate_selection_forbidden" in {
            issue.code for issue in captured.value.issues
        }

    def test_orchestration_does_not_mutate_any_input(self, orchestrator):
        gate = _constraint()
        plan = _plan(constraints=[gate])
        profile = {"viewer": "kids"}
        before_plan = plan.model_dump(mode="python")
        before_gate = gate.model_dump(mode="python")
        before_profile = dict(profile)

        orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25),
            active_profile_context=profile,
            authoritative_constraints=[gate],
        )

        assert plan.model_dump(mode="python") == before_plan
        assert gate.model_dump(mode="python") == before_gate
        assert profile == before_profile


class TestPreparedExecutionResult:
    def test_result_contains_copy_safe_execution_inputs(self, orchestrator):
        plan = _plan()

        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert isinstance(result, PreparedPlanExecution)
        assert isinstance(result.normalized_input, NormalizedAdapterInput)
        assert result.plan_id == plan.plan_id
        assert result.domain == Domain.STREAMING
        assert result.evaluated_at == NOW

        plan.steps[0].intent["energy"] = 0.99
        assert result.active_step.intent["energy"] == 0.55
        assert result.canonical_intent["energy"] == 0.55
        assert result.normalized_input.resolved_intent["energy_level"] == 0.55

    def test_prepared_canonical_intent_is_immutable(self, orchestrator):
        result = orchestrator.prepare_execution(
            _plan(),
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        with pytest.raises(TypeError):
            result.canonical_intent["energy"] = 1.0

    def test_identical_inputs_produce_identical_preparation(self, orchestrator):
        plan = _plan()

        first = orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25),
            active_profile_context={},
            authoritative_constraints=(),
        )
        second = orchestrator.prepare_execution(
            plan,
            now=NOW + timedelta(minutes=25),
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert first == second
        assert dict(first.canonical_intent) == dict(second.canonical_intent)
        assert first.normalized_input == second.normalized_input


class TestArchitectureBoundary:
    def test_trust_inputs_are_explicit_and_candidates_are_absent(self):
        signature = inspect.signature(IntentOrchestrator.prepare_execution)

        assert "now" in signature.parameters
        assert "active_profile_context" in signature.parameters
        assert "authoritative_constraints" in signature.parameters
        assert "candidates" not in signature.parameters
        assert signature.parameters["active_profile_context"].default is inspect.Parameter.empty
        assert signature.parameters["authoritative_constraints"].default is inspect.Parameter.empty

    def test_module_does_not_import_or_call_execution_components(self):
        source = inspect.getsource(orchestrator_module)

        assert "ranking_engine" not in source
        assert "domain_engine" not in source
        assert "prophecy_agent" not in source
        assert ".rank(" not in source
        assert "datetime.now" not in source
        assert "datetime.utcnow" not in source

    def test_public_method_requires_explicit_trust_channels(self, orchestrator):
        plan = _plan()

        with pytest.raises(TypeError):
            orchestrator.prepare_execution(plan, now=NOW)

    def test_result_active_step_is_an_immutable_contract_snapshot(self, orchestrator):
        plan = _plan()
        result = orchestrator.prepare_execution(
            plan,
            now=NOW,
            active_profile_context={},
            authoritative_constraints=(),
        )

        assert isinstance(result.active_step, ActivePlanStep)
        assert result.active_step.step_id == plan.steps[0].step_id
        assert dict(result.active_step.intent) == plan.steps[0].intent

        with pytest.raises(TypeError):
            result.active_step.intent["energy"] = 1.0
        with pytest.raises(FrozenInstanceError):
            result.active_step.offset_minutes = 25
