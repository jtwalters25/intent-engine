"""Tests for the Phase 5A server-owned planning application boundary."""

from datetime import datetime, timedelta, timezone

import pytest

from intent_engine.agentic.application import (
    FixedStreamingDemoPolicyResolver,
    InMemoryPlanRegistry,
    PlanCreationError,
    PlanRegistryError,
    StoredPlanRecord,
    TrustedPlanningContext,
    V4PlanningService,
)
from intent_engine.agentic.schemas import ConstraintSource, IntentConstraint
from intent_engine.schemas import Domain


NOW = datetime(2026, 10, 8, 19, 0, tzinfo=timezone.utc)


def _service(*, registry=None, clock=None, policy_resolver=None):
    return V4PlanningService(
        registry=registry,
        clock=(lambda: NOW) if clock is None else clock,
        policy_resolver=policy_resolver,
    )


def _create_wind_down(service, *, context=None):
    return service.create_plan(
        text="The kids are wired and bedtime is in an hour. Keep it calm.",
        domain=Domain.STREAMING,
        explicit_context=(
            {"viewer": "kids", "energy": 0.9}
            if context is None
            else context
        ),
    )


class TestTrustedPlanningBoundary:
    def test_distinct_goal_evidence_has_distinct_registry_identity(self):
        registry = InMemoryPlanRegistry()
        service = _service(registry=registry)
        first = service.create_plan(text="Bedtime.", domain=Domain.STREAMING, explicit_context={})
        second = service.create_plan(text="Keep it calm.", domain=Domain.STREAMING, explicit_context={})
        assert first.plan.plan_id != second.plan.plan_id
        assert len(registry) == 2

    @pytest.mark.parametrize("hard,source", [(True, ConstraintSource.USER), (False, ConstraintSource.SYSTEM), (False, ConstraintSource.DOMAIN)])
    def test_interpreter_cannot_smuggle_authority_through_profile_override(self, hard, source):
        from intent_engine.agentic.context_interpreter import RuleBasedContextInterpreter
        class ForgedInterpreter:
            def interpret(self, goal):
                result = RuleBasedContextInterpreter().interpret(goal)
                result.explicit_constraints.append(IntentConstraint(type="viewer_maturity", value="adult", hard=hard, source=source))
                return result
        service = V4PlanningService(interpreter=ForgedInterpreter(), clock=lambda: NOW)
        with pytest.raises(PlanCreationError) as captured:
            _create_wind_down(service)
        assert captured.value.code == "untrusted_constraint_authority"

    def test_server_time_profile_policy_and_session_own_the_plan(self):
        registry = InMemoryPlanRegistry()
        result = _create_wind_down(
            _service(registry=registry),
            context={
                "viewer": "adult",
                "energy": 0.9,
            },
        )

        assert result.goal_request.timestamp == NOW
        assert result.goal_request.session_id == "public-streaming-demo"
        assert result.plan.created_at == NOW
        assert result.plan.current_state["viewer"] == "kids"
        assert result.interpretation.entities["viewer"] == "kids"
        assert any(
            "server-owned viewer profile" in assumption
            for assumption in result.plan.assumptions
        )
        assert [
            constraint.model_dump(mode="json")
            for constraint in result.plan.constraints
            if constraint.hard
        ] == [
            {
                "type": "viewer_maturity",
                "value": "kids",
                "hard": True,
                "source": "SYSTEM",
            }
        ]

        stored = registry.get(
            owner_id="public-streaming-demo",
            plan_id=result.plan.plan_id,
            now=NOW,
        )
        assert stored is not None
        assert stored.goal_request == result.goal_request
        assert stored.interpretation == result.interpretation
        assert stored.plan == result.plan
        assert dict(stored.active_profile_context) == {"viewer": "kids"}
        assert stored.authoritative_constraints == tuple(
            constraint for constraint in result.plan.constraints if constraint.hard
        )

    def test_returned_values_cannot_mutate_the_stored_record(self):
        registry = InMemoryPlanRegistry()
        result = _create_wind_down(_service(registry=registry))
        original_energy = result.plan.current_state["energy"]
        original_context = dict(result.goal_request.explicit_context)

        result.plan.current_state["energy"] = 0.0
        result.goal_request.explicit_context["energy"] = 0.0
        result.interpretation.entities["energy"] = 0.0

        stored = registry.get(
            owner_id="public-streaming-demo",
            plan_id=result.plan.plan_id,
            now=NOW,
        )
        assert stored is not None
        assert stored.plan.current_state["energy"] == original_energy
        assert stored.goal_request.explicit_context == original_context
        assert stored.interpretation.entities["energy"] != 0.0

        stored.plan.current_state["energy"] = 0.0
        second_read = registry.get(
            owner_id="public-streaming-demo",
            plan_id=result.plan.plan_id,
            now=NOW,
        )
        assert second_read is not None
        assert second_read.plan.current_state["energy"] == original_energy

    def test_same_input_and_trusted_time_are_deterministic(self):
        first = _create_wind_down(_service()).plan
        second = _create_wind_down(_service()).plan

        assert first == second
        assert first.plan_id == second.plan_id

    def test_non_streaming_domain_fails_before_planning(self):
        with pytest.raises(PlanCreationError) as captured:
            _service().create_plan(
                text="Get me there quickly.",
                domain=Domain.RIDE_MATCHING,
                explicit_context={},
            )

        assert captured.value.code == "unsupported_domain"

    def test_unknown_context_cannot_smuggle_time_or_session_authority(self):
        with pytest.raises(PlanCreationError) as captured:
            _create_wind_down(
                _service(),
                context={
                    "viewer": "adult",
                    "timestamp": "1999-01-01T00:00:00Z",
                    "session_id": "forged-client-session",
                },
            )

        assert captured.value.code == "unsupported_context"

    def test_clock_must_be_server_supplied_and_timezone_aware(self):
        service = _service(clock=lambda: datetime(2026, 10, 8, 19, 0))

        with pytest.raises(RuntimeError, match="timezone-aware"):
            _create_wind_down(service)


class TestTrustedPlanningContext:
    def test_authoritative_constraints_must_be_hard_and_non_inferred(self):
        with pytest.raises(ValueError, match="hard and non-inferred"):
            TrustedPlanningContext(
                owner_id="owner",
                session_id="session",
                active_profile_context={"viewer": "kids"},
                authoritative_constraints=(
                    IntentConstraint(
                        type="viewer_maturity",
                        value="kids",
                        hard=False,
                        source=ConstraintSource.SYSTEM,
                    ),
                ),
            )

    def test_fixed_policy_returns_detached_snapshots(self):
        resolver = FixedStreamingDemoPolicyResolver()

        first = resolver.resolve(Domain.STREAMING)
        second = resolver.resolve(Domain.STREAMING)

        assert first == second
        assert first is not second
        assert first.authoritative_constraints[0] is not second.authoritative_constraints[0]


class TestInMemoryPlanRegistry:
    def _record(self, *, service=None):
        registry = InMemoryPlanRegistry()
        selected = _service(registry=registry) if service is None else service
        result = _create_wind_down(selected)
        record = registry.get(
            owner_id="public-streaming-demo",
            plan_id=result.plan.plan_id,
            now=NOW,
        )
        assert record is not None
        return result, record

    def test_lookup_is_owner_scoped_and_missing_matches_foreign(self):
        registry = InMemoryPlanRegistry()
        result = _create_wind_down(_service(registry=registry))

        assert registry.get(
            owner_id="another-owner",
            plan_id=result.plan.plan_id,
            now=NOW,
        ) is None
        assert registry.get(
            owner_id="public-streaming-demo",
            plan_id="plan_missing",
            now=NOW,
        ) is None

    def test_capacity_evicts_the_oldest_record(self):
        registry = InMemoryPlanRegistry(max_entries=1)
        times = iter((NOW, NOW + timedelta(minutes=1)))
        service = _service(registry=registry, clock=lambda: next(times))

        first = _create_wind_down(service)
        second = service.create_plan(
            text="Family movie night.",
            domain=Domain.STREAMING,
            explicit_context={"energy": 0.5},
        )

        assert len(registry) == 1
        assert registry.get(
            owner_id="public-streaming-demo",
            plan_id=first.plan.plan_id,
            now=NOW + timedelta(minutes=1),
        ) is None
        assert registry.get(
            owner_id="public-streaming-demo",
            plan_id=second.plan.plan_id,
            now=NOW + timedelta(minutes=1),
        ) is not None

    def test_plan_expiry_removes_the_record(self):
        registry = InMemoryPlanRegistry()
        result = _create_wind_down(_service(registry=registry))
        assert result.plan.expires_at is not None

        assert registry.get(
            owner_id="public-streaming-demo",
            plan_id=result.plan.plan_id,
            now=result.plan.expires_at,
        ) is None
        assert len(registry) == 0

    def test_max_retention_applies_when_plan_has_no_expiry(self):
        _, record = self._record()
        no_expiry = StoredPlanRecord(
            owner_id=record.owner_id,
            stored_at=record.stored_at,
            goal_request=record.goal_request,
            interpretation=record.interpretation,
            plan=record.plan.model_copy(update={"expires_at": None}),
            active_profile_context=record.active_profile_context,
            authoritative_constraints=record.authoritative_constraints,
        )
        registry = InMemoryPlanRegistry(max_retention=timedelta(minutes=10))
        registry.put(no_expiry)

        assert registry.get(
            owner_id=no_expiry.owner_id,
            plan_id=no_expiry.plan.plan_id,
            now=NOW + timedelta(minutes=10),
        ) is None

    def test_different_record_with_same_owner_and_plan_id_is_rejected(self):
        _, record = self._record()
        registry = InMemoryPlanRegistry()
        registry.put(record)
        changed = StoredPlanRecord(
            owner_id=record.owner_id,
            stored_at=record.stored_at,
            goal_request=record.goal_request.model_copy(
                update={"text": "Different retained goal text"}
            ),
            interpretation=record.interpretation,
            plan=record.plan,
            active_profile_context=record.active_profile_context,
            authoritative_constraints=record.authoritative_constraints,
        )

        with pytest.raises(PlanRegistryError, match="collision"):
            registry.put(changed)
