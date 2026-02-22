"""Time-aware intent scheduling and prediction.

The ProphecyAgent predicts when user intent should shift based on temporal
patterns and scheduled rules.  It provides:

  - TimeContext classification (EARLY_MORNING through LATE_NIGHT)
  - Default intent templates for each time context
  - Schedule management with time ranges and day-of-week filtering
  - Active schedule detection with midnight-crossing support
  - Intent shift prediction based on schedules and time transitions
  - Learning from manual overrides (tracking for future enhancements)

Design decisions:
  - Schedules are checked in insertion order; first match wins.
  - Midnight-crossing ranges (end < start) are handled transparently.
  - Override history is append-only for pattern analysis.
  - Prediction considers both explicit schedules and natural context
    transitions, returning whichever is soonest.
"""

from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Time-context constants
# ---------------------------------------------------------------------------

# (start_hour, end_hour, context_name)  —  ranges are [start, end)
# LATE_NIGHT crosses midnight: hour >= 22 OR hour < 5
TIME_CONTEXT_RANGES: List[Tuple[int, int, str]] = [
    (5, 8, "EARLY_MORNING"),
    (8, 12, "MORNING"),
    (12, 17, "AFTERNOON"),
    (17, 20, "EVENING"),
    (20, 22, "BEDTIME"),
    (22, 5, "LATE_NIGHT"),
]

# Hour boundaries where context transitions occur (used for prediction)
CONTEXT_TRANSITION_HOURS: List[Tuple[int, str]] = [
    (5, "EARLY_MORNING"),
    (8, "MORNING"),
    (12, "AFTERNOON"),
    (17, "EVENING"),
    (20, "BEDTIME"),
    (22, "LATE_NIGHT"),
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TimeContext(str, Enum):
    """Time-of-day contexts for intent scheduling.

    Aligned with children's daily rhythms and content consumption patterns.
    """

    EARLY_MORNING = "EARLY_MORNING"  # 5:00-8:00  — wake-up, light content
    MORNING = "MORNING"              # 8:00-12:00 — active learning
    AFTERNOON = "AFTERNOON"          # 12:00-17:00 — post-lunch, varied
    EVENING = "EVENING"              # 17:00-20:00 — family time, wind-down
    BEDTIME = "BEDTIME"              # 20:00-22:00 — calming, sleep prep
    LATE_NIGHT = "LATE_NIGHT"        # 22:00-5:00  — minimal / no content


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IntentOverride(BaseModel):
    """Record of a manual intent override for learning purposes.

    Tracks when users manually change scheduled intents, enabling
    future pattern detection and schedule refinement.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-21T20:15:00",
                "scheduled_intent": {"energyLevel": 15},
                "actual_intent": {"energyLevel": 40},
                "time_context": "BEDTIME",
                "schedule_id": "bedtime_daily",
            }
        }
    )

    timestamp: datetime = Field(..., description="When the override occurred")
    scheduled_intent: Dict[str, Any] = Field(
        ..., description="Intent that was scheduled"
    )
    actual_intent: Dict[str, Any] = Field(
        ..., description="Intent the user actually selected"
    )
    time_context: TimeContext = Field(
        ..., description="Time context when override occurred"
    )
    schedule_id: Optional[str] = Field(
        default=None,
        description="Identifier for the schedule that was overridden",
    )


class IntentSchedule(BaseModel):
    """A scheduled intent with time range and recurrence rules.

    Supports flexible scheduling with time ranges, day-of-week filtering,
    and midnight-crossing ranges (e.g. 22:00-05:00 for late night).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "time_context": "BEDTIME",
                "start_time": "20:00:00",
                "end_time": "22:00:00",
                "intent_template": {
                    "energyLevel": 15,
                    "learningFocus": ["emotional", "mindfulness"],
                    "tone": "soothing",
                },
                "recurring": True,
                "days_of_week": [0, 1, 2, 3, 4],
                "enabled": True,
            }
        }
    )

    time_context: TimeContext = Field(
        ..., description="Associated time context for this schedule"
    )
    start_time: time = Field(..., description="Start time (inclusive)")
    end_time: time = Field(..., description="End time (exclusive)")
    intent_template: Dict[str, Any] = Field(
        ..., description="Intent dict to apply when schedule is active"
    )
    recurring: bool = Field(
        default=True, description="Whether schedule repeats daily/weekly"
    )
    days_of_week: Optional[List[int]] = Field(
        default=None,
        description=(
            "Days when schedule applies (0=Monday, 6=Sunday). "
            "None means all days."
        ),
    )
    enabled: bool = Field(default=True, description="Whether schedule is active")
    schedule_id: Optional[str] = Field(
        default=None,
        description="Optional identifier for correlation with overrides",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate days_of_week values are in 0-6."""
        if self.days_of_week is not None:
            if not all(0 <= day <= 6 for day in self.days_of_week):
                raise ValueError(
                    "days_of_week must contain integers 0-6 "
                    "(0=Monday, 6=Sunday)"
                )


# ---------------------------------------------------------------------------
# ProphecyAgent
# ---------------------------------------------------------------------------

class ProphecyAgent:
    """Time-aware intent scheduler and predictor.

    Manages intent schedules based on time of day, day of week, and learned
    patterns.  Provides predictions for upcoming intent shifts and suggestions
    for proactive UI changes.
    """

    def __init__(self) -> None:
        """Initialize the ProphecyAgent with empty schedules and defaults."""
        self._schedules: List[IntentSchedule] = []
        self._override_history: List[IntentOverride] = []

        self._default_intents: Dict[TimeContext, Dict[str, Any]] = {
            TimeContext.EARLY_MORNING: {
                "energyLevel": 30,
                "learningFocus": ["gentle", "wake-up"],
                "tone": "bright",
                "mood": "calm",
            },
            TimeContext.MORNING: {
                "energyLevel": 70,
                "learningFocus": ["educational", "engaging"],
                "tone": "energetic",
                "mood": "active",
            },
            TimeContext.AFTERNOON: {
                "energyLevel": 60,
                "learningFocus": ["varied", "creative"],
                "tone": "balanced",
                "mood": "exploratory",
            },
            TimeContext.EVENING: {
                "energyLevel": 40,
                "learningFocus": ["family", "storytelling"],
                "tone": "warm",
                "mood": "calm",
            },
            TimeContext.BEDTIME: {
                "energyLevel": 15,
                "learningFocus": ["emotional", "mindfulness"],
                "tone": "soothing",
                "mood": "calm",
            },
            TimeContext.LATE_NIGHT: {
                "energyLevel": 5,
                "learningFocus": ["sleep"],
                "tone": "minimal",
                "mood": "rest",
            },
        }

    # --- Core public methods ------------------------------------------------

    def infer_time_context(self, current_time: datetime) -> TimeContext:
        """Infer time context from a datetime.

        Maps hour-of-day ranges to TimeContext values.  Handles the
        midnight-crossing LATE_NIGHT range (22:00-05:00) correctly.

        Args:
            current_time: The datetime to classify.

        Returns:
            The inferred TimeContext.
        """
        hour = current_time.hour

        for start, end, context_name in TIME_CONTEXT_RANGES:
            if self._hour_in_range(hour, start, end):
                return TimeContext(context_name)

        # Fallback — should never reach here with correct ranges
        return TimeContext.AFTERNOON

    def get_default_intent_for_context(
        self, context: TimeContext
    ) -> Dict[str, Any]:
        """Get the default intent template for a time context.

        Args:
            context: The time context.

        Returns:
            A copy of the default intent dict for that context.
        """
        return self._default_intents.get(context, {}).copy()

    def add_schedule(self, schedule: IntentSchedule) -> None:
        """Add an intent schedule.

        Schedules are checked in insertion order.  When multiple schedules
        match a given time, the first one wins.

        Args:
            schedule: The schedule to add.
        """
        self._schedules.append(schedule)

    def get_active_schedule(
        self, current_time: datetime
    ) -> Optional[IntentSchedule]:
        """Find the first active schedule for the given time.

        Checks enabled schedules in insertion order, considering time range
        (with midnight-crossing support) and day-of-week filters.

        Args:
            current_time: The datetime to check.

        Returns:
            The first matching schedule, or None.
        """
        current_time_only = current_time.time()
        current_weekday = current_time.weekday()

        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            if not self._schedule_active_on_weekday(schedule, current_weekday):
                continue
            if self._time_in_range(
                current_time_only, schedule.start_time, schedule.end_time
            ):
                return schedule

        return None

    def predict_next_intent_shift(
        self, current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Predict when the next intent shift will occur.

        Considers both scheduled shifts and natural time-context transitions,
        returning whichever is soonest.

        Args:
            current_time: The reference time.

        Returns:
            A dict with shift_time, shift_type, intent_template, and
            time_context — or None if nothing is found.
        """
        candidates: List[Dict[str, Any]] = []

        next_sched = self._find_next_schedule(current_time)
        if next_sched:
            candidates.append(next_sched)

        next_ctx = self._find_next_context_transition(current_time)
        if next_ctx:
            candidates.append(next_ctx)

        if not candidates:
            return None

        return min(candidates, key=lambda c: c["shift_time"])

    def should_suggest_intent_shift(
        self, current_time: datetime, warning_minutes: int = 15
    ) -> Optional[Dict[str, Any]]:
        """Check if an intent shift is imminent.

        Args:
            current_time: The current time.
            warning_minutes: How many minutes before a shift to trigger.

        Returns:
            The shift dict if a shift is within the warning window,
            otherwise None.
        """
        next_shift = self.predict_next_intent_shift(current_time)
        if not next_shift:
            return None

        shift_time = next_shift["shift_time"]
        warning_threshold = current_time + timedelta(minutes=warning_minutes)

        if current_time < shift_time <= warning_threshold:
            return next_shift

        return None

    def learn_from_manual_override(
        self,
        current_time: datetime,
        actual_intent: Dict[str, Any],
        scheduled_intent: Dict[str, Any],
    ) -> None:
        """Record a manual intent override for future learning.

        Args:
            current_time: When the override occurred.
            actual_intent: The intent the user selected.
            scheduled_intent: The intent that was scheduled / suggested.
        """
        context = self.infer_time_context(current_time)
        active = self.get_active_schedule(current_time)

        self._override_history.append(
            IntentOverride(
                timestamp=current_time,
                scheduled_intent=scheduled_intent,
                actual_intent=actual_intent,
                time_context=context,
                schedule_id=active.schedule_id if active else None,
            )
        )

    # --- Private helpers ----------------------------------------------------

    def _hour_in_range(self, hour: int, start: int, end: int) -> bool:
        """Check if *hour* falls in [start, end), handling midnight wrap.

        Args:
            hour: Hour to check (0-23).
            start: Start hour (0-23, inclusive).
            end: End hour (0-23, exclusive).

        Returns:
            True if hour is in the range.
        """
        if start <= end:
            return start <= hour < end
        # Wraps midnight (e.g. 22 → 5)
        return hour >= start or hour < end

    def _time_in_range(self, current: time, start: time, end: time) -> bool:
        """Check if *current* falls in [start, end), handling midnight wrap.

        Args:
            current: Time to check.
            start: Start time (inclusive).
            end: End time (exclusive).

        Returns:
            True if current is in the range.
        """
        if start <= end:
            return start <= current < end
        # Crosses midnight
        return current >= start or current < end

    def _schedule_active_on_weekday(
        self, schedule: IntentSchedule, weekday: int
    ) -> bool:
        """Check if *schedule* applies on the given weekday.

        Args:
            schedule: The schedule.
            weekday: Day of week (0=Monday, 6=Sunday).

        Returns:
            True if the schedule is active on this day.
        """
        if schedule.days_of_week is None:
            return True
        return weekday in schedule.days_of_week

    def _find_next_schedule(
        self, current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Find the soonest upcoming schedule activation.

        Args:
            current_time: Reference time.

        Returns:
            Shift dict or None.
        """
        candidates: List[Dict[str, Any]] = []

        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            activation = self._calculate_next_activation(current_time, schedule)
            if activation:
                candidates.append(
                    {
                        "shift_time": activation,
                        "shift_type": "schedule",
                        "intent_template": schedule.intent_template.copy(),
                        "time_context": schedule.time_context,
                    }
                )

        if not candidates:
            return None
        return min(candidates, key=lambda c: c["shift_time"])

    def _calculate_next_activation(
        self, current_time: datetime, schedule: IntentSchedule
    ) -> Optional[datetime]:
        """Calculate when *schedule* will next activate after *current_time*.

        Looks up to 7 days ahead to account for day-of-week filtering.

        Args:
            current_time: Reference time.
            schedule: The schedule to check.

        Returns:
            Next activation datetime, or None.
        """
        # Try today first
        today_activation = datetime.combine(
            current_time.date(), schedule.start_time
        )
        if (
            today_activation > current_time
            and self._schedule_active_on_weekday(
                schedule, current_time.weekday()
            )
        ):
            return today_activation

        # Try next 7 days
        for days_ahead in range(1, 8):
            future_date = current_time.date() + timedelta(days=days_ahead)
            if self._schedule_active_on_weekday(
                schedule, future_date.weekday()
            ):
                return datetime.combine(future_date, schedule.start_time)

        return None

    def _find_next_context_transition(
        self, current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Find the next natural TimeContext transition.

        Walks forward hour-by-hour (up to 24 h) and returns the first
        point where the context changes.

        Args:
            current_time: Reference time.

        Returns:
            Shift dict or None.
        """
        current_context = self.infer_time_context(current_time)

        for offset in range(1, 25):
            future = current_time + timedelta(hours=offset)
            future_context = self.infer_time_context(future)

            if future_context != current_context:
                transition_dt = datetime.combine(
                    future.date(), time(future.hour, 0)
                )
                return {
                    "shift_time": transition_dt,
                    "shift_type": "context",
                    "intent_template": self.get_default_intent_for_context(
                        future_context
                    ),
                    "time_context": future_context,
                }

        return None
