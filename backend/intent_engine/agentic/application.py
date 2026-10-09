"""Application boundary for safe V4 planning and later execution.

The external API supplies a natural-language goal and untrusted context only.
Trusted time, profile state, safety policy, and record ownership are resolved
inside this module.  The bounded in-memory registry is deliberately a
process-local pilot implementation; it is not durable audit storage and is not
exposed through a retrieval endpoint.
"""

from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from hashlib import sha256
from threading import RLock
from types import MappingProxyType
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple, runtime_checkable
from uuid import uuid4

from intent_engine.agentic.context_interpreter import (
    ContextInterpreter,
    InterpretationError,
    RuleBasedContextInterpreter,
)
from intent_engine.agentic.planner import PlanningError, RuleBasedIntentPlanner
from intent_engine.agentic.schemas import (
    ConstraintSource,
    ContextInterpretation,
    GoalRequest,
    IntentConstraint,
    IntentPlan,
    datetime_instant,
    validate_json_value,
)
from intent_engine.agentic.validator import CONSTRAINT_TYPE_ALIASES
from intent_engine.schemas import Domain


DEFAULT_PLAN_REGISTRY_CAPACITY = 256
DEFAULT_PLAN_REGISTRY_RETENTION = timedelta(hours=4)


class PlanExecutionError(ValueError):
    """Public-safe execution rejection with an HTTP status."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.public_message = message
        self.status_code = status_code
        super().__init__(message)


class PlanCreationError(ValueError):
    """Expected, public-safe rejection while creating a plan."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.public_message = message
        super().__init__(message)


class PolicyResolutionError(ValueError):
    """Raised when the server cannot establish trusted planning policy."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.public_message = message
        super().__init__(message)


class PlanRegistryError(RuntimeError):
    """Raised when an internal plan record cannot be stored safely."""


def _copy_json_mapping(values: Mapping[str, Any], *, path: str) -> Dict[str, Any]:
    try:
        copied = dict(values)
    except Exception as exc:
        raise ValueError(f"{path} must be a mapping") from exc
    validate_json_value(copied, path=path)
    # JSON round-tripping creates a detached copy of every nested container.
    return json.loads(
        json.dumps(
            copied,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _copy_contract(value: Any, expected_type: type, *, path: str) -> Any:
    if not isinstance(value, expected_type):
        raise TypeError(f"{path} must be a {expected_type.__name__}")
    try:
        return expected_type.model_validate(value.model_dump(mode="python"))
    except Exception as exc:
        raise ValueError(f"{path} failed contract validation") from exc


@dataclass(frozen=True)
class TrustedPlanningContext:
    """Profile, policy, and ownership established by server-side code."""

    owner_id: str
    session_id: str
    active_profile_context: Mapping[str, Any]
    authoritative_constraints: Sequence[IntentConstraint]

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be a non-blank server identity")
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a non-blank server identity")

        profile = _copy_json_mapping(
            self.active_profile_context,
            path="active_profile_context",
        )
        checked_constraints = []
        for index, constraint in enumerate(tuple(self.authoritative_constraints)):
            copied = _copy_contract(
                constraint,
                IntentConstraint,
                path=f"authoritative_constraints.{index}",
            )
            if not copied.hard or copied.source == ConstraintSource.INFERRED:
                raise ValueError(
                    "authoritative constraints must be hard and non-inferred"
                )
            checked_constraints.append(copied)

        object.__setattr__(self, "owner_id", self.owner_id.strip())
        object.__setattr__(self, "session_id", self.session_id.strip())
        object.__setattr__(
            self,
            "active_profile_context",
            MappingProxyType(profile),
        )
        object.__setattr__(
            self,
            "authoritative_constraints",
            tuple(checked_constraints),
        )


@runtime_checkable
class PlanningContextResolver(Protocol):
    """Resolve authenticated profile and policy outside client input."""

    def resolve(self, domain: Domain) -> TrustedPlanningContext:
        ...


class FixedStreamingDemoPolicyResolver:
    """Conservative policy for the unauthenticated public streaming pilot.

    Until a real principal/profile provider exists, the V4 API is intentionally
    bound to one server-owned kids profile.  Request context may describe a
    goal, but it cannot weaken this profile or its maturity gate.
    """

    def __init__(
        self,
        *,
        owner_id: str = "public-streaming-demo",
        session_id: str = "public-streaming-demo",
    ) -> None:
        self._context = TrustedPlanningContext(
            owner_id=owner_id,
            session_id=session_id,
            active_profile_context={"viewer": "kids"},
            authoritative_constraints=(
                IntentConstraint(
                    type="viewer_maturity",
                    value="kids",
                    hard=True,
                    source=ConstraintSource.SYSTEM,
                ),
            ),
        )

    def resolve(self, domain: Domain) -> TrustedPlanningContext:
        try:
            selected_domain = Domain(domain)
        except (TypeError, ValueError) as exc:
            raise PolicyResolutionError(
                "unsupported_domain",
                "The requested planning domain is not supported.",
            ) from exc
        if selected_domain != Domain.STREAMING:
            raise PolicyResolutionError(
                "unsupported_domain",
                "Phase 5A planning supports the streaming domain only.",
            )
        # Construct a fresh validated snapshot so callers never receive the
        # resolver's internal model instances.
        return TrustedPlanningContext(
            owner_id=self._context.owner_id,
            session_id=self._context.session_id,
            active_profile_context=self._context.active_profile_context,
            authoritative_constraints=self._context.authoritative_constraints,
        )


@dataclass(frozen=True)
class StoredPlanRecord:
    """Exact lifecycle evidence required by the later execute boundary."""

    owner_id: str
    stored_at: datetime
    goal_request: GoalRequest
    interpretation: ContextInterpretation
    plan: IntentPlan
    active_profile_context: Mapping[str, Any]
    authoritative_constraints: Sequence[IntentConstraint]

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be non-blank")
        if not isinstance(self.stored_at, datetime):
            raise TypeError("stored_at must be a datetime")
        if self.stored_at.utcoffset() is None:
            raise ValueError("stored_at must be timezone-aware")

        goal = _copy_contract(
            self.goal_request,
            GoalRequest,
            path="goal_request",
        )
        interpretation = _copy_contract(
            self.interpretation,
            ContextInterpretation,
            path="interpretation",
        )
        plan = _copy_contract(self.plan, IntentPlan, path="plan")
        profile = _copy_json_mapping(
            self.active_profile_context,
            path="active_profile_context",
        )
        constraints = tuple(
            _copy_contract(
                constraint,
                IntentConstraint,
                path=f"authoritative_constraints.{index}",
            )
            for index, constraint in enumerate(tuple(self.authoritative_constraints))
        )

        if goal.domain != plan.domain:
            raise ValueError("goal and plan domains must match")
        if goal.session_id is None:
            raise ValueError("stored goals require a server-owned session_id")
        if datetime_instant(plan.created_at) != datetime_instant(self.stored_at):
            raise ValueError("stored_at must match the trusted plan creation time")
        if any(not constraint.hard for constraint in constraints):
            raise ValueError("stored authoritative constraints must be hard")

        object.__setattr__(self, "owner_id", self.owner_id.strip())
        object.__setattr__(self, "goal_request", goal)
        object.__setattr__(self, "interpretation", interpretation)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "active_profile_context", MappingProxyType(profile))
        object.__setattr__(self, "authoritative_constraints", constraints)

    def snapshot(self) -> "StoredPlanRecord":
        """Return a detached copy safe for an in-process consumer."""
        return StoredPlanRecord(
            owner_id=self.owner_id,
            stored_at=self.stored_at,
            goal_request=self.goal_request,
            interpretation=self.interpretation,
            plan=self.plan,
            active_profile_context=self.active_profile_context,
            authoritative_constraints=self.authoritative_constraints,
        )


@runtime_checkable
class PlanRegistry(Protocol):
    """Minimal scoped record store needed by a later execute endpoint."""

    def put(self, record: StoredPlanRecord) -> None:
        ...

    def get(
        self,
        *,
        owner_id: str,
        plan_id: str,
        now: datetime,
    ) -> Optional[StoredPlanRecord]:
        ...


class InMemoryPlanRegistry:
    """Thread-safe, bounded, expiring registry for the public pilot."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_PLAN_REGISTRY_CAPACITY,
        max_retention: timedelta = DEFAULT_PLAN_REGISTRY_RETENTION,
    ) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int):
            raise TypeError("max_entries must be an integer")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if not isinstance(max_retention, timedelta) or max_retention <= timedelta(0):
            raise ValueError("max_retention must be a positive timedelta")
        self._max_entries = max_entries
        self._max_retention = max_retention
        self._records: "OrderedDict[Tuple[str, str], StoredPlanRecord]" = OrderedDict()
        self._lock = RLock()

    def put(self, record: StoredPlanRecord) -> None:
        if not isinstance(record, StoredPlanRecord):
            raise TypeError("record must be a StoredPlanRecord")
        snapshot = record.snapshot()
        key = (snapshot.owner_id, snapshot.plan.plan_id)
        with self._lock:
            self._purge_expired(snapshot.stored_at)
            existing = self._records.get(key)
            if existing is not None:
                if existing.snapshot() != snapshot:
                    raise PlanRegistryError("plan identifier collision")
                self._records.move_to_end(key)
                return
            while len(self._records) >= self._max_entries:
                self._records.popitem(last=False)
            self._records[key] = snapshot

    def get(
        self,
        *,
        owner_id: str,
        plan_id: str,
        now: datetime,
    ) -> Optional[StoredPlanRecord]:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must be non-blank")
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ValueError("plan_id must be non-blank")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("now must be a timezone-aware datetime")
        with self._lock:
            self._purge_expired(now)
            record = self._records.get((owner_id.strip(), plan_id.strip()))
            if record is None:
                return None
            self._records.move_to_end((owner_id.strip(), plan_id.strip()))
            return record.snapshot()

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def _purge_expired(self, now: datetime) -> None:
        now_instant = datetime_instant(now)
        expired = []
        for key, record in self._records.items():
            retention_deadline = record.stored_at + self._max_retention
            plan_deadline = record.plan.expires_at
            deadline = (
                retention_deadline
                if plan_deadline is None
                else min(
                    datetime_instant(plan_deadline),
                    datetime_instant(retention_deadline),
                )
            )
            if now_instant >= datetime_instant(deadline):
                expired.append(key)
        for key in expired:
            del self._records[key]


@dataclass(frozen=True)
class PlanCreationResult:
    """Detached successful result returned by the planning service."""

    goal_request: GoalRequest
    interpretation: ContextInterpretation
    plan: IntentPlan

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "goal_request",
            _copy_contract(self.goal_request, GoalRequest, path="goal_request"),
        )
        object.__setattr__(
            self,
            "interpretation",
            _copy_contract(
                self.interpretation,
                ContextInterpretation,
                path="interpretation",
            ),
        )
        object.__setattr__(
            self,
            "plan",
            _copy_contract(self.plan, IntentPlan, path="plan"),
        )


class V4PlanningService:
    """Compose trusted policy, deterministic interpretation, and planning."""

    def __init__(
        self,
        *,
        interpreter: Optional[ContextInterpreter] = None,
        planner: Optional[RuleBasedIntentPlanner] = None,
        policy_resolver: Optional[PlanningContextResolver] = None,
        registry: Optional[PlanRegistry] = None,
        clock: Optional[Callable[[], datetime]] = None,
        trace_id_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self._interpreter = (
            RuleBasedContextInterpreter() if interpreter is None else interpreter
        )
        self._planner = RuleBasedIntentPlanner() if planner is None else planner
        self._policy_resolver = (
            FixedStreamingDemoPolicyResolver()
            if policy_resolver is None
            else policy_resolver
        )
        self._registry = InMemoryPlanRegistry() if registry is None else registry
        self._clock = (
            (lambda: datetime.now(timezone.utc)) if clock is None else clock
        )
        self._trace_id_factory = trace_id_factory or (lambda: "trace_" + uuid4().hex)

    def execute_plan(self, *, plan_id: str, candidates: Sequence[Any]):
        """Compose server-retained evidence with deterministic execution once.

        The full trace remains an in-process return value. HTTP callers receive
        only the dedicated response projection defined by the V4 router.
        """
        from intent_engine.agentic.orchestrator import IntentOrchestrator, OrchestrationError
        from intent_engine.agentic.validator import PlanValidationError
        from intent_engine.agentic.trace import ExecutionTraceBuilder
        from intent_engine.core.domain_engine import DomainRankingEngine
        from intent_engine.adapters.streaming import StreamingAdapter

        now = self._trusted_now()
        try:
            trusted = self._policy_resolver.resolve(Domain.STREAMING)
        except PolicyResolutionError as exc:
            raise PlanExecutionError("policy_unavailable", "Execution policy is unavailable.", 409) from exc
        record = self._registry.get(owner_id=trusted.owner_id, plan_id=plan_id, now=now)
        if record is None:
            # Expired/evicted, foreign, and nonexistent IDs share this response.
            raise PlanExecutionError("plan_not_found", "The plan is unavailable.", 404)
        if (record.goal_request.session_id != trusted.session_id
            or dict(record.active_profile_context) != dict(trusted.active_profile_context)
            or tuple(record.authoritative_constraints) != tuple(trusted.authoritative_constraints)):
            raise PlanExecutionError("policy_changed", "Create a new plan under the current policy.", 409)
        try:
            prepared = IntentOrchestrator().prepare_execution(
                record.plan, now=now,
                active_profile_context=trusted.active_profile_context,
                authoritative_constraints=trusted.authoritative_constraints,
            )
        except (OrchestrationError, PlanValidationError) as exc:
            raise PlanExecutionError("plan_not_executable", "The plan cannot execute at the current time.", 409) from exc
        ranking = DomainRankingEngine({Domain.STREAMING: StreamingAdapter()}).rank_resolved_execution(
            domain=record.plan.domain,
            resolved_intent=prepared.normalized_input.resolved_intent,
            constraints=prepared.normalized_input.hard_constraints,
            candidates=candidates,
        )
        return ExecutionTraceBuilder().build(
            trace_id=self._trace_id_factory(), goal_request=record.goal_request,
            interpretation=record.interpretation, plan=record.plan,
            prepared_execution=prepared, ranking_execution=ranking,
            engine_version="v4-domain-engine-1", adapter_version="v4-streaming-adapter-1",
        )

    @property
    def registry(self) -> PlanRegistry:
        return self._registry

    def create_plan(
        self,
        *,
        text: str,
        domain: Domain,
        explicit_context: Mapping[str, Any],
    ) -> PlanCreationResult:
        now = self._trusted_now()
        try:
            selected_domain = Domain(domain)
            trusted = self._policy_resolver.resolve(selected_domain)
        except PolicyResolutionError as exc:
            raise PlanCreationError(exc.code, exc.public_message) from exc
        except (TypeError, ValueError) as exc:
            raise PlanCreationError(
                "unsupported_domain",
                "The requested planning domain is not supported.",
            ) from exc

        try:
            goal = GoalRequest(
                text=text,
                domain=selected_domain,
                timestamp=now,
                explicit_context=dict(explicit_context),
                session_id=trusted.session_id,
            )
            interpretation = self._interpreter.interpret(goal)
            effective_interpretation = self._apply_trusted_profile(
                interpretation,
                trusted.active_profile_context,
            )
            plan = self._planner.create_plan(
                effective_interpretation,
                selected_domain,
                now,
                authoritative_constraints=trusted.authoritative_constraints,
            )
            # Planner IDs identify intent semantics. API records also retain
            # original goal evidence: distinct goals must never overwrite it.
            identity = json.dumps(
                {"goal": goal.model_dump(mode="json"), "plan": plan.model_dump(mode="json"), "owner": trusted.owner_id},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            )
            plan_id = "plan_" + sha256(identity.encode("utf-8")).hexdigest()[:32]
            plan = IntentPlan.model_validate({
                **plan.model_dump(mode="python"),
                "plan_id": plan_id,
                "steps": [
                    {**step.model_dump(mode="python"), "step_id": f"{plan_id}_step_{index + 1}"}
                    for index, step in enumerate(plan.steps)
                ],
            })
        except InterpretationError as exc:
            raise PlanCreationError(exc.code, str(exc)) from exc
        except PlanningError as exc:
            raise PlanCreationError(exc.code, str(exc)) from exc

        record = StoredPlanRecord(
            owner_id=trusted.owner_id,
            stored_at=now,
            goal_request=goal,
            interpretation=effective_interpretation,
            plan=plan,
            active_profile_context=trusted.active_profile_context,
            authoritative_constraints=trusted.authoritative_constraints,
        )
        self._registry.put(record)
        return PlanCreationResult(
            goal_request=goal,
            interpretation=effective_interpretation,
            plan=plan,
        )

    def _trusted_now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise RuntimeError("V4 server clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    def _apply_trusted_profile(
        self,
        interpretation: ContextInterpretation,
        active_profile_context: Mapping[str, Any],
    ) -> ContextInterpretation:
        checked = _copy_contract(
            interpretation,
            ContextInterpretation,
            path="interpretation",
        )
        profile = _copy_json_mapping(
            active_profile_context,
            path="active_profile_context",
        )

        entities = dict(checked.entities)
        inferred = dict(checked.inferred_context)
        assumptions = list(checked.assumptions)
        constraints = []
        policy_overrode_input = False

        if "viewer" in profile:
            requested_values = [
                container["viewer"]
                for container in (entities, inferred)
                if "viewer" in container
            ]
            if requested_values and any(
                value != profile["viewer"] for value in requested_values
            ):
                policy_overrode_input = True
            entities["viewer"] = profile["viewer"]
            inferred.pop("viewer", None)

        for constraint in checked.explicit_constraints:
            if constraint.hard or constraint.source not in {ConstraintSource.USER, ConstraintSource.INFERRED}:
                raise PlanningError(
                    "untrusted_constraint_authority",
                    "Interpretation cannot introduce hard or privileged constraints.",
                )
            semantic_type = CONSTRAINT_TYPE_ALIASES.get(
                constraint.type,
                constraint.type,
            )
            if semantic_type == "viewer_maturity":
                policy_overrode_input = True
                continue
            constraints.append(constraint)

        if policy_overrode_input:
            assumptions.append(
                "The server-owned viewer profile superseded untrusted viewer context."
            )

        # Any future protected profile fields are copied only from the trusted
        # resolver.  The current streaming pilot supports `viewer`.
        for key, value in profile.items():
            if key != "viewer":
                raise RuntimeError(
                    f"unsupported trusted streaming profile field: {key}"
                )
            entities[key] = value

        return ContextInterpretation(
            objective=checked.objective,
            entities=entities,
            explicit_constraints=constraints,
            inferred_context=inferred,
            assumptions=list(dict.fromkeys(assumptions)),
            missing_information=checked.missing_information,
            confidence=checked.confidence,
        )


__all__ = [
    "DEFAULT_PLAN_REGISTRY_CAPACITY",
    "DEFAULT_PLAN_REGISTRY_RETENTION",
    "FixedStreamingDemoPolicyResolver",
    "InMemoryPlanRegistry",
    "PlanCreationError",
    "PlanCreationResult",
    "PlanRegistry",
    "PlanRegistryError",
    "PlanningContextResolver",
    "PolicyResolutionError",
    "StoredPlanRecord",
    "TrustedPlanningContext",
    "V4PlanningService",
]
