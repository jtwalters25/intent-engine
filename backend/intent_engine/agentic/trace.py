"""Typed construction of successful V4 execution traces.

The builder is deliberately observational.  It snapshots the values already
produced by orchestration and the engine's correlated resolved-ranking
execution, checks that their prepared intent and constraints agree, and never
invokes a validator, normalizer, adapter, or ranker.  A trace records evidence;
it is not execution authority.
"""

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from datetime import datetime
import json
import math
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from intent_engine.agentic.normalizer import NormalizedAdapterInput
from intent_engine.agentic.orchestrator import ActivePlanStep, PreparedPlanExecution
from intent_engine.agentic.schemas import (
    MAX_JSON_ITEMS,
    MAX_JSON_NESTING,
    CandidateSafetyDecision,
    ContextInterpretation,
    ExecutionTrace,
    GoalRequest,
    IntentApplicationTrace,
    IntentPlan,
    IntentStep,
    RankedCandidateTrace,
    RankingDecisionTrace,
    RankingMultiplierTrace,
    RankingScoreTrace,
    TraceLatency,
    TraceValidationResult,
    TraceValidationStatus,
)
from intent_engine.core.domain_engine import ResolvedRankingExecution
from intent_engine.schemas import (
    Domain,
    Intent,
    Item,
    LatencyBreakdown,
    RankedItem,
    RankingMode,
    RankingResponse,
    ScoreBreakdown,
)


_ModelT = TypeVar("_ModelT", bound=BaseModel)
_DETERMINISTIC_TRACE_FIELDS = {
    "goal_request",
    "interpretation",
    "plan",
    "validation_results",
    "active_step",
    "intent_application",
    "safety_decisions",
    "ranking_trace",
}


class TraceBuildError(ValueError):
    """Fail-closed trace construction error with stable location metadata."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {message}")


def _snapshot_json(value: Any, *, path: str) -> Any:
    """Materialize a bounded JSON copy, including immutable prepared mappings."""

    pending_items = [0]
    active_containers = set()

    def snapshot(current: Any, current_path: str, depth: int) -> Any:
        pending_items[0] += 1
        if pending_items[0] > MAX_JSON_ITEMS:
            raise TraceBuildError(
                "trace_data_too_large",
                path,
                f"exceeds the maximum JSON item count of {MAX_JSON_ITEMS}",
            )

        if current is None or isinstance(current, (str, bool, int)):
            return current
        if isinstance(current, float):
            if not math.isfinite(current):
                raise TraceBuildError(
                    "invalid_trace_data",
                    current_path,
                    "must not contain NaN or infinity",
                )
            return current

        if isinstance(current, MappingABC):
            if depth >= MAX_JSON_NESTING:
                raise TraceBuildError(
                    "trace_data_too_deep",
                    path,
                    f"exceeds the maximum JSON nesting of {MAX_JSON_NESTING}",
                )
            marker = id(current)
            if marker in active_containers:
                raise TraceBuildError(
                    "cyclic_trace_data",
                    current_path,
                    "must not contain a cycle",
                )
            active_containers.add(marker)
            try:
                try:
                    supplied = dict(current)
                except Exception as exc:
                    raise TraceBuildError(
                        "invalid_trace_data",
                        current_path,
                        "could not be snapshotted",
                    ) from exc
                if any(not isinstance(key, str) for key in supplied):
                    raise TraceBuildError(
                        "invalid_trace_data",
                        current_path,
                        "object keys must be strings",
                    )
                return {
                    key: snapshot(
                        supplied[key],
                        f"{current_path}.{key}",
                        depth + 1,
                    )
                    for key in supplied
                }
            finally:
                active_containers.remove(marker)

        if isinstance(current, SequenceABC) and not isinstance(
            current, (str, bytes)
        ):
            if depth >= MAX_JSON_NESTING:
                raise TraceBuildError(
                    "trace_data_too_deep",
                    path,
                    f"exceeds the maximum JSON nesting of {MAX_JSON_NESTING}",
                )
            marker = id(current)
            if marker in active_containers:
                raise TraceBuildError(
                    "cyclic_trace_data",
                    current_path,
                    "must not contain a cycle",
                )
            active_containers.add(marker)
            try:
                try:
                    supplied = tuple(current)
                except Exception as exc:
                    raise TraceBuildError(
                        "invalid_trace_data",
                        current_path,
                        "could not be snapshotted",
                    ) from exc
                return [
                    snapshot(item, f"{current_path}[{index}]", depth + 1)
                    for index, item in enumerate(supplied)
                ]
            finally:
                active_containers.remove(marker)

        raise TraceBuildError(
            "invalid_trace_data",
            current_path,
            "must be JSON-compatible",
        )

    return snapshot(value, path, 0)


def _snapshot_contract(value: Any, model: Type[_ModelT], *, path: str) -> _ModelT:
    if not isinstance(value, model):
        raise TraceBuildError(
            "invalid_trace_input",
            path,
            f"must be a {model.__name__}",
        )
    try:
        payload = value.model_dump(mode="python")
        return model.model_validate(payload)
    except Exception as exc:
        raise TraceBuildError(
            "invalid_trace_input",
            path,
            "failed contract revalidation",
        ) from exc


def _snapshot_active_step(value: ActivePlanStep) -> IntentStep:
    if not isinstance(value, ActivePlanStep):
        raise TraceBuildError(
            "invalid_prepared_execution",
            "prepared_execution.active_step",
            "must be an ActivePlanStep",
        )
    try:
        return IntentStep(
            step_id=value.step_id,
            offset_minutes=value.offset_minutes,
            intent=_snapshot_json(
                value.intent,
                path="prepared_execution.active_step.intent",
            ),
            transition_reason=value.transition_reason,
            completion_condition=(
                None
                if value.completion_condition is None
                else _snapshot_json(
                    value.completion_condition,
                    path="prepared_execution.active_step.completion_condition",
                )
            ),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        if isinstance(exc, TraceBuildError):
            raise
        raise TraceBuildError(
            "invalid_prepared_execution",
            "prepared_execution.active_step",
            "failed active-step validation",
        ) from exc


def _snapshot_item(value: Any, *, path: str) -> Item:
    # rank_resolved receives Item values.  CandidateItem would omit replay
    # fields such as category and price when serialized through RankedItem.
    if not isinstance(value, Item):
        raise TraceBuildError(
            "untraceable_candidate",
            path,
            "resolved ranking candidates must retain the full Item contract",
        )
    try:
        payload = value.model_dump(mode="python")
        payload["attributes"] = _snapshot_json(
            value.attributes,
            path=f"{path}.attributes",
        )
        item = Item.model_validate(payload)
    except Exception as exc:
        if isinstance(exc, TraceBuildError):
            raise
        raise TraceBuildError(
            "invalid_ranking_response",
            path,
            "candidate failed Item validation",
        ) from exc
    return item


def _snapshot_ranked_candidate(
    value: Any,
    *,
    index: int,
) -> tuple[RankedCandidateTrace, CandidateSafetyDecision]:
    path = f"ranking_response.ranked_items.{index}"
    if not isinstance(value, RankedItem):
        raise TraceBuildError(
            "invalid_ranking_response",
            path,
            "must be a RankedItem",
        )
    if not isinstance(value.score_breakdown, ScoreBreakdown):
        raise TraceBuildError(
            "missing_score_breakdown",
            f"{path}.score_breakdown",
            "resolved ranking must provide a score breakdown",
        )

    item = _snapshot_item(value.item, path=f"{path}.item")
    breakdown = value.score_breakdown
    try:
        multiplier_trace = RankingMultiplierTrace(
            context=breakdown.multipliers.context,
            profile=breakdown.multipliers.profile,
            urgency=breakdown.multipliers.urgency,
            cost=breakdown.multipliers.cost,
            prophecy=breakdown.multipliers.prophecy,
        )
        score_trace = RankingScoreTrace(
            base_score=breakdown.base_score,
            multipliers=multiplier_trace,
            diversity_penalty=breakdown.diversity_penalty,
            final_score=breakdown.final_score,
            blocked=breakdown.blocked,
            block_reason=breakdown.block_reason,
        )
        candidate_trace = RankedCandidateTrace(
            item=item,
            rank=value.rank,
            final_score=value.final_score,
            status=value.status,
            explanation=value.explanation,
            score_breakdown=score_trace,
        )
    except (AttributeError, ValidationError, ValueError, TypeError) as exc:
        raise TraceBuildError(
            "invalid_ranking_response",
            path,
            "ranked candidate contains inconsistent trace evidence",
        ) from exc

    if isinstance(value.score, bool) or not isinstance(value.score, (int, float)):
        raise TraceBuildError(
            "invalid_ranking_response",
            f"{path}.score",
            "must be a finite numeric value",
        )
    try:
        numeric_score = float(value.score)
    except (OverflowError, ValueError) as exc:
        raise TraceBuildError(
            "invalid_ranking_response",
            f"{path}.score",
            "must be a finite numeric value",
        ) from exc
    if not math.isfinite(numeric_score) or numeric_score != candidate_trace.final_score:
        raise TraceBuildError(
            "inconsistent_ranking_score",
            f"{path}.score",
            "score, final_score, and score breakdown must match",
        )

    try:
        safety = CandidateSafetyDecision(
            candidate_id=item.item_id,
            rank=candidate_trace.rank,
            blocked=score_trace.blocked,
            reason=score_trace.block_reason,
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise TraceBuildError(
            "invalid_ranking_response",
            path,
            "candidate safety evidence is malformed",
        ) from exc
    return candidate_trace, safety


class ExecutionTraceBuilder:
    """Construct a trace from one completed in-process execution."""

    def build(
        self,
        *,
        trace_id: str,
        goal_request: GoalRequest,
        interpretation: ContextInterpretation,
        plan: IntentPlan,
        prepared_execution: PreparedPlanExecution,
        ranking_execution: ResolvedRankingExecution,
        engine_version: str,
        adapter_version: str,
    ) -> ExecutionTrace:
        goal = _snapshot_contract(goal_request, GoalRequest, path="goal_request")
        interpreted = _snapshot_contract(
            interpretation,
            ContextInterpretation,
            path="interpretation",
        )
        checked_plan = _snapshot_contract(plan, IntentPlan, path="plan")

        if not isinstance(prepared_execution, PreparedPlanExecution):
            raise TraceBuildError(
                "invalid_trace_input",
                "prepared_execution",
                "must be a PreparedPlanExecution",
            )
        if not isinstance(prepared_execution.evaluated_at, datetime):
            raise TraceBuildError(
                "invalid_prepared_execution",
                "prepared_execution.evaluated_at",
                "must be a datetime",
            )
        if prepared_execution.plan_id != checked_plan.plan_id:
            raise TraceBuildError(
                "plan_mismatch",
                "prepared_execution.plan_id",
                "does not match the traced plan",
            )
        if prepared_execution.domain != checked_plan.domain:
            raise TraceBuildError(
                "domain_mismatch",
                "prepared_execution.domain",
                "does not match the traced plan",
            )
        if not isinstance(prepared_execution.domain, Domain):
            raise TraceBuildError(
                "invalid_prepared_execution",
                "prepared_execution.domain",
                "must retain the typed Domain value",
            )
        if not isinstance(prepared_execution.normalized_input, NormalizedAdapterInput):
            raise TraceBuildError(
                "invalid_prepared_execution",
                "prepared_execution.normalized_input",
                "must be a NormalizedAdapterInput",
            )
        if prepared_execution.normalized_input.domain != checked_plan.domain:
            raise TraceBuildError(
                "domain_mismatch",
                "prepared_execution.normalized_input.domain",
                "does not match the traced plan",
            )

        active_step = _snapshot_active_step(prepared_execution.active_step)
        plan_step = next(
            (
                step
                for step in checked_plan.steps
                if step.step_id == active_step.step_id
            ),
            None,
        )
        if plan_step is None or plan_step != active_step:
            raise TraceBuildError(
                "active_step_mismatch",
                "prepared_execution.active_step",
                "must exactly match one step in the traced plan",
            )

        canonical_intent = _snapshot_json(
            prepared_execution.canonical_intent,
            path="prepared_execution.canonical_intent",
        )
        normalized = prepared_execution.normalized_input
        if not isinstance(ranking_execution, ResolvedRankingExecution):
            raise TraceBuildError(
                "invalid_trace_input",
                "ranking_execution",
                "must be a ResolvedRankingExecution",
            )
        if ranking_execution.domain != checked_plan.domain:
            raise TraceBuildError(
                "domain_mismatch",
                "ranking_execution.domain",
                "does not match the traced plan",
            )
        if not isinstance(ranking_execution.domain, Domain):
            raise TraceBuildError(
                "invalid_ranking_execution",
                "ranking_execution.domain",
                "must retain the typed Domain value",
            )
        applied_intent = _snapshot_json(
            ranking_execution.resolved_intent,
            path="ranking_execution.resolved_intent",
        )
        applied_constraints = _snapshot_json(
            ranking_execution.constraints,
            path="ranking_execution.constraints",
        )
        prepared_intent = _snapshot_json(
            normalized.resolved_intent,
            path="prepared_execution.normalized_input.resolved_intent",
        )
        prepared_constraints = _snapshot_json(
            normalized.hard_constraints,
            path="prepared_execution.normalized_input.hard_constraints",
        )
        if applied_intent != prepared_intent:
            raise TraceBuildError(
                "intent_mismatch",
                "ranking_execution.resolved_intent",
                "does not match the prepared adapter intent",
            )
        if applied_constraints != prepared_constraints:
            raise TraceBuildError(
                "constraint_mismatch",
                "ranking_execution.constraints",
                "do not match the prepared hard constraints",
            )
        try:
            intent_application = IntentApplicationTrace(
                domain=checked_plan.domain,
                canonical_intent=canonical_intent,
                applied_intent=applied_intent,
                applied_hard_constraints=applied_constraints,
                observational_signals=_snapshot_json(
                    normalized.observational_signals,
                    path=(
                        "prepared_execution.normalized_input."
                        "observational_signals"
                    ),
                ),
            )
        except (AttributeError, ValidationError, ValueError, TypeError) as exc:
            if isinstance(exc, TraceBuildError):
                raise
            raise TraceBuildError(
                "invalid_prepared_execution",
                "prepared_execution.normalized_input",
                "could not construct typed intent-application evidence",
            ) from exc

        ranking_response = ranking_execution.response
        if not isinstance(ranking_response, RankingResponse):
            raise TraceBuildError(
                "invalid_trace_input",
                "ranking_response",
                "must be a RankingResponse",
            )
        if ranking_response.domain != checked_plan.domain:
            raise TraceBuildError(
                "domain_mismatch",
                "ranking_response.domain",
                "does not match the traced plan",
            )
        if not isinstance(ranking_response.domain, Domain):
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.domain",
                "must retain the typed Domain value",
            )
        if ranking_response.mode_used != RankingMode.ADVANCED:
            raise TraceBuildError(
                "mode_mismatch",
                "ranking_response.mode_used",
                "resolved execution must report advanced mode",
            )
        if not isinstance(ranking_response.mode_used, RankingMode):
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.mode_used",
                "must retain the typed RankingMode value",
            )
        if not isinstance(ranking_response.intent, Intent):
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.intent",
                "must retain the typed Intent value",
            )
        if not isinstance(ranking_response.latency, LatencyBreakdown):
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.latency",
                "must retain the typed LatencyBreakdown value",
            )

        try:
            ranked_values = tuple(ranking_response.ranked_items)
        except Exception as exc:
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.ranked_items",
                "could not be snapshotted",
            ) from exc
        if not ranked_values:
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.ranked_items",
                "must contain at least one ranked candidate",
            )

        try:
            input_candidates = [
                _snapshot_item(
                    candidate,
                    path=f"ranking_execution.candidates.{index}",
                )
                for index, candidate in enumerate(ranking_execution.candidates)
            ]
        except (TypeError, ValueError) as exc:
            if isinstance(exc, TraceBuildError):
                raise
            raise TraceBuildError(
                "invalid_ranking_execution",
                "ranking_execution.candidates",
                "could not snapshot candidate inputs",
            ) from exc
        if not input_candidates:
            raise TraceBuildError(
                "invalid_ranking_execution",
                "ranking_execution.candidates",
                "must contain at least one candidate",
            )

        ranked_candidates = []
        safety_decisions = []
        for index, ranked_item in enumerate(ranked_values):
            candidate, safety = _snapshot_ranked_candidate(
                ranked_item,
                index=index,
            )
            ranked_candidates.append(candidate)
            safety_decisions.append(safety)

        expected_intent_type = intent_application.applied_intent.get(
            "intent_type", "unknown"
        )
        try:
            response_intent_type = ranking_response.intent.intent_type
        except AttributeError as exc:
            raise TraceBuildError(
                "invalid_ranking_response",
                "ranking_response.intent",
                "must contain a typed intent",
            ) from exc
        if response_intent_type != expected_intent_type:
            raise TraceBuildError(
                "intent_mismatch",
                "ranking_response.intent.intent_type",
                "does not match the applied intent",
            )

        try:
            ranking_trace = RankingDecisionTrace(
                domain=checked_plan.domain,
                mode_used=ranking_response.mode_used,
                intent_type=response_intent_type,
                engine_version=engine_version,
                adapter_version=adapter_version,
                input_candidates=input_candidates,
                ranked_candidates=ranked_candidates,
            )
            latency = TraceLatency(
                ranking_total_ms=ranking_response.latency.total_ms,
                intent_parsing_ms=ranking_response.latency.intent_parsing_ms,
                ranking_ms=ranking_response.latency.ranking_ms,
                diversity_check_ms=ranking_response.latency.diversity_check_ms,
            )
            validation = TraceValidationResult(
                stage="plan_execution_boundary",
                status=TraceValidationStatus.PASSED,
                evaluated_at=prepared_execution.evaluated_at,
                plan_id=checked_plan.plan_id,
                domain=checked_plan.domain,
            )
            return ExecutionTrace(
                trace_id=trace_id,
                goal_request=goal,
                interpretation=interpreted,
                plan=checked_plan,
                validation_results=[validation],
                active_step=active_step,
                intent_application=intent_application,
                safety_decisions=safety_decisions,
                ranking_trace=ranking_trace,
                outcome_events=[],
                latency=latency,
            )
        except (AttributeError, ValidationError, ValueError, TypeError) as exc:
            raise TraceBuildError(
                "invalid_trace_evidence",
                "execution_trace",
                "could not construct a coherent typed trace",
            ) from exc


def canonical_execution_decision_json(trace: ExecutionTrace) -> str:
    """Return canonical decision JSON without volatile IDs, timing, or outcomes."""

    checked = _snapshot_contract(trace, ExecutionTrace, path="trace")
    payload = checked.model_dump(
        mode="json",
        include=_DETERMINISTIC_TRACE_FIELDS,
    )
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise TraceBuildError(
            "invalid_trace_data",
            "trace",
            "could not serialize deterministic decision data",
        ) from exc
