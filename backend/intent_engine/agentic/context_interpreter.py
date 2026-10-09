"""Deterministic natural-language interpretation for the V4 streaming pilot.

The interpreter is deliberately small and rules-first.  It extracts only the
canonical context needed by :class:`RuleBasedIntentPlanner`; it never inspects
candidates, ranks items, or grants policy authority to client input.
"""

from __future__ import annotations

import math
import re
import unicodedata
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Protocol, Tuple, runtime_checkable

from pydantic import ValidationError

from intent_engine.agentic.schemas import (
    ConstraintSource,
    ContextInterpretation,
    GoalRequest,
    IntentConstraint,
)
from intent_engine.schemas import Domain


MAX_GOAL_TEXT_LENGTH = 4096
MAX_INTERPRETED_HORIZON_MINUTES = 240
SUPPORTED_CONTEXT_KEYS = frozenset({"energy", "horizon_minutes", "viewer"})
SUPPORTED_VIEWERS = frozenset({"adult", "family", "kids", "teen"})

_MINIMUM_HORIZON_MINUTES: Mapping[str, int] = MappingProxyType(
    {
        "wind_down": 15,
        "focus": 10,
        "family_time": 15,
        "quick_session": 5,
        "high_energy": 10,
    }
)

_OBJECTIVE_PATTERNS: Mapping[str, Tuple[re.Pattern[str], ...]] = MappingProxyType(
    {
        "wind_down": tuple(
            re.compile(pattern)
            for pattern in (
                r"\bbed\s*time\b",
                r"\bwind(?:ing)?(?:\s+(?:me|them|us))?\s+down\b",
                r"\bcalm(?:ing)?\b",
                r"\bsooth(?:e|ing)\b",
                r"\bsettle(?:\s+(?:me|them|us))?\s+down\b",
                r"\basleep\b",
            )
        ),
        "focus": tuple(
            re.compile(pattern)
            for pattern in (
                r"\bfocus(?:ed|ing)?\b",
                r"\beducational\b",
                r"\blearn(?:ing)?\b",
                r"\bstud(?:y|ying)\b",
                r"\bconcentrat(?:e|ing|ion)\b",
            )
        ),
        "family_time": tuple(
            re.compile(pattern)
            for pattern in (
                r"\bfamily(?:[\s-]+(?:movie|time|night|viewing))?\b",
                r"\bmovie\s+night\b",
                r"\bwatch(?:ing)?\s+together\b",
            )
        ),
        "quick_session": tuple(
            re.compile(pattern)
            for pattern in (
                r"\bquick\b",
                r"\bshort\s+(?:session|show|episode|watch)\b",
                r"\b(?:under|within|less\s+than|no\s+more\s+than)\s+"
                r"[+-]?\d{1,6}\s*(?:minutes?|mins?|min|hours?|hrs?|hr)\b",
                r"\b[+-]?\d{1,6}\s*(?:minutes?|mins?|min|hours?|hrs?|hr)\s+"
                r"(?:session|show|episode|watch)\b",
            )
        ),
        "high_energy": tuple(
            re.compile(pattern)
            for pattern in (
                r"\bhigh[\s-]+energy\b",
                r"\benergetic\b",
                r"\bexciting\b",
                r"\baction[\s-]+packed\b",
                r"\bupbeat\b",
            )
        ),
    }
)

_VIEWER_PATTERNS: Mapping[str, Tuple[re.Pattern[str], ...]] = MappingProxyType(
    {
        "kids": (
            re.compile(r"\bkids?\b"),
            re.compile(r"\bchild(?:ren)?\b"),
            re.compile(r"\btoddlers?\b"),
        ),
        "teen": (
            re.compile(r"\bteens?\b"),
            re.compile(r"\bteenagers?\b"),
        ),
        "adult": (
            re.compile(r"\badults?\b"),
            re.compile(r"\bgrown[\s-]+ups?\b"),
        ),
        # Bare "family" is an objective cue.  These forms specifically
        # describe the intended viewer profile.
        "family": (
            re.compile(r"\bfamily[\s-]+friendly\b"),
            re.compile(r"\bfamily\s+profile\b"),
            re.compile(r"\bfor\s+the\s+family\b"),
        ),
    }
)

_HIGH_CURRENT_ENERGY_PATTERNS = (
    re.compile(r"\b(?:are|is|feel(?:ing)?|seem(?:s|ing)?)\s+wired\b"),
    re.compile(r"\bbouncing\s+off\s+the\s+walls\b"),
)
_LOW_CURRENT_ENERGY_PATTERNS = (
    re.compile(r"\b(?:are|is|feel(?:ing)?|seem(?:s|ing)?)\s+(?:tired|sleepy)\b"),
    re.compile(r"\blow[\s-]+energy\s+(?:right\s+now|currently)\b"),
)

_NUMERIC_DURATION_PATTERN = re.compile(
    r"\b(?:under|within|for|in|about|approximately|less\s+than|"
    r"no\s+more\s+than)\s+"
    r"(?P<amount>[+-]?\d{1,6})(?![\d.])\s*"
    r"(?P<unit>minutes?|mins?|min|hours?|hrs?|hr)\b"
)
_SESSION_DURATION_PATTERN = re.compile(
    r"(?<![\d.])(?P<amount>[+-]?\d{1,6})(?![\d.])\s*"
    r"(?P<unit>minutes?|mins?|min|hours?|hrs?|hr)\s+"
    r"(?:session|show|episode|watch)\b"
)
_AN_HOUR_PATTERN = re.compile(
    r"\b(?:under|within|for|in|about|approximately)\s+an?\s+hour\b"
)
_HALF_HOUR_PATTERN = re.compile(
    r"\b(?:under|within|for|in|about|approximately)\s+half\s+an?\s+hour\b"
)

_NEGATED_PREFIX_PATTERN = re.compile(
    r"(?:\bnot|\bno|\bavoid|\bwithout|\bdon't|\bdo\s+not|\bnothing)\s+"
    r"(?:(?:want|anything)\s+)?(?:a\s+|an\s+)?(?:too\s+)?$"
)


class InterpretationError(ValueError):
    """A fail-closed interpretation error with a stable public code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@runtime_checkable
class ContextInterpreter(Protocol):
    """Convert a typed goal into intent context without ranking candidates."""

    def interpret(self, goal_request: GoalRequest) -> ContextInterpretation:
        ...


class RuleBasedContextInterpreter:
    """Deterministic interpreter for the bounded V4 streaming vocabulary."""

    def interpret(self, goal_request: GoalRequest) -> ContextInterpretation:
        goal = self.validate_goal(goal_request)
        if goal.domain != Domain.STREAMING:
            raise InterpretationError(
                "unsupported_domain",
                "Phase 5A rules interpretation supports the streaming domain only.",
            )

        normalized_text = self._normalize_text(goal.text)
        context = self.validate_explicit_context(goal.explicit_context)
        objective = self._resolve_objective(normalized_text)

        viewer, viewer_source = self._resolve_viewer(normalized_text, context)
        energy = self._resolve_energy(normalized_text, context)
        horizon, horizon_source = self._resolve_horizon(
            normalized_text,
            context,
            objective,
        )

        entities: Dict[str, Any] = {}
        if viewer is not None:
            entities["viewer"] = viewer
        if energy is not None:
            entities["energy"] = energy

        inferred_context: Dict[str, Any] = {}
        if horizon is not None:
            inferred_context["horizon_minutes"] = horizon

        constraints: List[IntentConstraint] = []
        assumptions = [
            "The objective was derived by deterministic streaming rules from user goal text."
        ]
        if viewer is not None:
            source = (
                ConstraintSource.USER
                if viewer_source == "explicit_context"
                else ConstraintSource.INFERRED
            )
            constraints.append(
                IntentConstraint(
                    type="viewer_maturity",
                    value=viewer,
                    hard=False,
                    source=source,
                )
            )
            assumptions.append(
                "Viewer context is non-authoritative intent; server policy must supply any hard maturity gate."
            )
        if horizon_source == "goal_text":
            assumptions.append(
                f"The stated time horizon was interpreted as {horizon} minutes."
            )

        missing_information = [
            name
            for name, value in (
                ("energy", energy),
                ("viewer", viewer),
                ("horizon_minutes", horizon),
            )
            if value is None
        ]

        confidence = 0.94 if context else 0.90
        try:
            return ContextInterpretation(
                objective=objective,
                entities=entities,
                explicit_constraints=constraints,
                inferred_context=inferred_context,
                assumptions=assumptions,
                missing_information=missing_information,
                confidence=confidence,
            )
        except ValidationError as exc:  # pragma: no cover - defensive boundary
            raise InterpretationError(
                "invalid_interpretation",
                "Deterministic rules produced an invalid interpretation.",
            ) from exc

    def validate_goal(self, goal_request: Any) -> GoalRequest:
        """Validate and snapshot input before rules or optional model use."""
        if not isinstance(goal_request, GoalRequest):
            raise InterpretationError(
                "invalid_goal",
                "goal_request must be a GoalRequest.",
            )
        try:
            goal = GoalRequest.model_validate(goal_request.model_dump(mode="python"))
        except (RecursionError, TypeError, ValueError, ValidationError) as exc:
            raise InterpretationError(
                "invalid_goal",
                "goal_request failed contract validation.",
            ) from exc
        if len(goal.text) > MAX_GOAL_TEXT_LENGTH:
            raise InterpretationError(
                "goal_too_long",
                f"goal text must not exceed {MAX_GOAL_TEXT_LENGTH} characters.",
            )
        return goal

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(normalized.split())

    def validate_explicit_context(
        self,
        explicit_context: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Validate canonical context independently of objective resolution."""
        context = dict(explicit_context)
        unknown = sorted(set(context) - SUPPORTED_CONTEXT_KEYS)
        if unknown:
            raise InterpretationError(
                "unsupported_context",
                "unsupported explicit context field(s): " + ", ".join(unknown),
            )

        if "viewer" in context:
            viewer = context["viewer"]
            if not isinstance(viewer, str):
                raise InterpretationError(
                    "invalid_context",
                    "explicit_context.viewer must be a supported string.",
                )
            viewer = self._normalize_text(viewer).replace(" ", "_")
            if viewer not in SUPPORTED_VIEWERS:
                raise InterpretationError(
                    "invalid_context",
                    "explicit_context.viewer must be one of: adult, family, kids, teen.",
                )
            context["viewer"] = viewer

        if "energy" in context:
            energy = context["energy"]
            if isinstance(energy, bool) or not isinstance(energy, (int, float)):
                raise InterpretationError(
                    "invalid_context",
                    "explicit_context.energy must be a number between 0 and 1.",
                )
            try:
                numeric = float(energy)
            except (OverflowError, ValueError) as exc:
                raise InterpretationError("invalid_context", "explicit_context.energy must be finite.") from exc
            if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
                raise InterpretationError(
                    "invalid_context",
                    "explicit_context.energy must be a finite number between 0 and 1.",
                )
            context["energy"] = numeric

        if "horizon_minutes" in context:
            horizon = context["horizon_minutes"]
            if isinstance(horizon, bool) or not isinstance(horizon, int):
                raise InterpretationError(
                    "invalid_context",
                    "explicit_context.horizon_minutes must be an integer.",
                )
            context["horizon_minutes"] = horizon

        return context

    def _resolve_objective(self, text: str) -> str:
        matched = []
        for objective, patterns in _OBJECTIVE_PATTERNS.items():
            if any(self._has_positive_match(text, pattern) for pattern in patterns):
                matched.append(objective)

        if len(matched) > 1:
            raise InterpretationError(
                "ambiguous_goal",
                "goal text maps to multiple supported objectives: "
                + ", ".join(sorted(matched)),
            )
        if not matched:
            raise InterpretationError(
                "unsupported_goal",
                "goal text does not identify one supported streaming objective.",
            )
        return matched[0]

    def _has_positive_match(self, text: str, pattern: re.Pattern[str]) -> bool:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 48) : match.start()]
            if not _NEGATED_PREFIX_PATTERN.search(prefix):
                return True
        return False

    def _resolve_viewer(
        self,
        text: str,
        context: Mapping[str, Any],
    ) -> Tuple[Any, Any]:
        if "viewer" in context:
            return context["viewer"], "explicit_context"

        matched = [
            viewer
            for viewer, patterns in _VIEWER_PATTERNS.items()
            if any(pattern.search(text) for pattern in patterns)
        ]
        if len(matched) > 1:
            raise InterpretationError(
                "ambiguous_viewer",
                "goal text identifies multiple viewer profiles.",
            )
        return (matched[0], "goal_text") if matched else (None, None)

    def _resolve_energy(
        self,
        text: str,
        context: Mapping[str, Any],
    ) -> Any:
        if "energy" in context:
            return context["energy"]

        high = any(pattern.search(text) for pattern in _HIGH_CURRENT_ENERGY_PATTERNS)
        low = any(pattern.search(text) for pattern in _LOW_CURRENT_ENERGY_PATTERNS)
        if high and low:
            raise InterpretationError(
                "ambiguous_energy",
                "goal text describes conflicting current energy states.",
            )
        if high:
            return 0.9
        if low:
            return 0.2
        return None

    def _resolve_horizon(
        self,
        text: str,
        context: Mapping[str, Any],
        objective: str,
    ) -> Tuple[Any, Any]:
        if "horizon_minutes" in context:
            horizon = context["horizon_minutes"]
            source = "explicit_context"
        else:
            values = self._duration_values(text)
            if len(values) > 1:
                raise InterpretationError(
                    "ambiguous_horizon",
                    "goal text contains conflicting time horizons.",
                )
            horizon = next(iter(values)) if values else None
            source = "goal_text" if horizon is not None else None

        if horizon is None:
            return None, None

        minimum = _MINIMUM_HORIZON_MINUTES[objective]
        if not minimum <= horizon <= MAX_INTERPRETED_HORIZON_MINUTES:
            raise InterpretationError(
                "invalid_horizon",
                f"{objective} horizon must be between {minimum} and "
                f"{MAX_INTERPRETED_HORIZON_MINUTES} minutes.",
            )
        return horizon, source

    def _duration_values(self, text: str) -> set[int]:
        values = set()
        for pattern in (_NUMERIC_DURATION_PATTERN, _SESSION_DURATION_PATTERN):
            for match in pattern.finditer(text):
                amount = int(match.group("amount"))
                unit = match.group("unit")
                values.add(amount * 60 if unit.startswith(("hour", "hr")) else amount)

        if _HALF_HOUR_PATTERN.search(text):
            values.add(30)
        # Check this after half-hour; "half an hour" must not be interpreted as
        # both 30 and 60 minutes.
        text_without_half_hours = _HALF_HOUR_PATTERN.sub("", text)
        if _AN_HOUR_PATTERN.search(text_without_half_hours):
            values.add(60)
        return values


__all__ = [
    "ContextInterpreter",
    "InterpretationError",
    "MAX_GOAL_TEXT_LENGTH",
    "MAX_INTERPRETED_HORIZON_MINUTES",
    "RuleBasedContextInterpreter",
    "SUPPORTED_CONTEXT_KEYS",
    "SUPPORTED_VIEWERS",
]
