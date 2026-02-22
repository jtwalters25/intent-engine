"""Tests for the ProphecyAgent — time-aware intent scheduling."""

import pytest
from datetime import datetime, time, timedelta

from intent_engine.prophecy_agent import (
    ProphecyAgent,
    TimeContext,
    IntentSchedule,
    IntentOverride,
)


# ---------------------------------------------------------------------------
# Time context inference
# ---------------------------------------------------------------------------

class TestTimeContextInference:
    """Test time context classification from datetime."""

    def setup_method(self):
        self.agent = ProphecyAgent()

    @pytest.mark.parametrize("hour,expected", [
        (5, TimeContext.EARLY_MORNING),
        (6, TimeContext.EARLY_MORNING),
        (7, TimeContext.EARLY_MORNING),
        (8, TimeContext.MORNING),
        (10, TimeContext.MORNING),
        (11, TimeContext.MORNING),
        (12, TimeContext.AFTERNOON),
        (14, TimeContext.AFTERNOON),
        (16, TimeContext.AFTERNOON),
        (17, TimeContext.EVENING),
        (18, TimeContext.EVENING),
        (19, TimeContext.EVENING),
        (20, TimeContext.BEDTIME),
        (21, TimeContext.BEDTIME),
        (22, TimeContext.LATE_NIGHT),
        (23, TimeContext.LATE_NIGHT),
        (0, TimeContext.LATE_NIGHT),
        (1, TimeContext.LATE_NIGHT),
        (3, TimeContext.LATE_NIGHT),
        (4, TimeContext.LATE_NIGHT),
    ])
    def test_hour_to_context_mapping(self, hour, expected):
        """Verify correct context for each representative hour."""
        dt = datetime(2026, 2, 21, hour, 30)
        assert self.agent.infer_time_context(dt) == expected

    def test_midnight_is_late_night(self):
        """Exact midnight should be LATE_NIGHT."""
        dt = datetime(2026, 2, 21, 0, 0)
        assert self.agent.infer_time_context(dt) == TimeContext.LATE_NIGHT

    def test_late_night_to_early_morning_boundary(self):
        """Transition at 5 AM: 4:59 is LATE_NIGHT, 5:00 is EARLY_MORNING."""
        before = datetime(2026, 2, 21, 4, 59)
        after = datetime(2026, 2, 21, 5, 0)
        assert self.agent.infer_time_context(before) == TimeContext.LATE_NIGHT
        assert self.agent.infer_time_context(after) == TimeContext.EARLY_MORNING


# ---------------------------------------------------------------------------
# Default intents
# ---------------------------------------------------------------------------

class TestDefaultIntents:
    """Test default intent generation for each context."""

    def setup_method(self):
        self.agent = ProphecyAgent()

    def test_bedtime_has_low_energy(self):
        intent = self.agent.get_default_intent_for_context(TimeContext.BEDTIME)
        assert intent["energyLevel"] == 15
        assert intent["tone"] == "soothing"
        assert intent["mood"] == "calm"

    def test_morning_has_high_energy(self):
        intent = self.agent.get_default_intent_for_context(TimeContext.MORNING)
        assert intent["energyLevel"] == 70
        assert "educational" in intent["learningFocus"]
        assert intent["mood"] == "active"

    def test_all_contexts_have_defaults(self):
        """Every TimeContext value should have a default intent."""
        for ctx in TimeContext:
            intent = self.agent.get_default_intent_for_context(ctx)
            assert isinstance(intent, dict)
            assert "energyLevel" in intent
            assert "learningFocus" in intent

    def test_returned_dict_is_a_copy(self):
        """Mutating the returned dict must not affect the original."""
        a = self.agent.get_default_intent_for_context(TimeContext.BEDTIME)
        a["energyLevel"] = 999
        b = self.agent.get_default_intent_for_context(TimeContext.BEDTIME)
        assert b["energyLevel"] == 15


# ---------------------------------------------------------------------------
# Schedule management
# ---------------------------------------------------------------------------

class TestScheduleManagement:
    """Test adding schedules and validation."""

    def setup_method(self):
        self.agent = ProphecyAgent()

    def test_add_schedule(self):
        schedule = IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={"energyLevel": 15},
        )
        self.agent.add_schedule(schedule)
        assert len(self.agent._schedules) == 1

    def test_invalid_days_of_week_raises(self):
        with pytest.raises(ValueError, match="days_of_week"):
            IntentSchedule(
                time_context=TimeContext.BEDTIME,
                start_time=time(20, 0),
                end_time=time(22, 0),
                intent_template={},
                days_of_week=[7, 8],
            )

    def test_valid_days_of_week_accepted(self):
        schedule = IntentSchedule(
            time_context=TimeContext.MORNING,
            start_time=time(8, 0),
            end_time=time(12, 0),
            intent_template={},
            days_of_week=[0, 4, 6],
        )
        assert schedule.days_of_week == [0, 4, 6]


# ---------------------------------------------------------------------------
# Active schedule detection
# ---------------------------------------------------------------------------

class TestActiveScheduleDetection:
    """Test finding active schedules based on time and day."""

    def setup_method(self):
        self.agent = ProphecyAgent()

        # Bedtime: 8pm-10pm all days
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={"energyLevel": 15, "tone": "soothing"},
            schedule_id="bedtime_all",
        ))

        # Weekend morning: 8am-12pm Sat-Sun
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.MORNING,
            start_time=time(8, 0),
            end_time=time(12, 0),
            intent_template={"energyLevel": 70, "tone": "energetic"},
            days_of_week=[5, 6],
            schedule_id="weekend_morning",
        ))

    def test_active_within_range(self):
        """Friday 8:30 PM — bedtime should be active."""
        dt = datetime(2026, 2, 20, 20, 30)  # Friday
        active = self.agent.get_active_schedule(dt)
        assert active is not None
        assert active.schedule_id == "bedtime_all"

    def test_no_active_outside_range(self):
        """Friday 3 PM — no schedule active."""
        dt = datetime(2026, 2, 20, 15, 0)
        assert self.agent.get_active_schedule(dt) is None

    def test_weekend_schedule_on_saturday(self):
        """Saturday 9 AM — weekend morning active."""
        dt = datetime(2026, 2, 21, 9, 0)  # Saturday
        active = self.agent.get_active_schedule(dt)
        assert active is not None
        assert active.schedule_id == "weekend_morning"

    def test_weekend_schedule_not_on_weekday(self):
        """Monday 9 AM — weekend schedule must NOT match."""
        dt = datetime(2026, 2, 16, 9, 0)  # Monday
        assert self.agent.get_active_schedule(dt) is None

    def test_first_match_wins(self):
        """When two schedules overlap, the first added wins."""
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.EVENING,
            start_time=time(19, 0),
            end_time=time(21, 0),
            intent_template={"energyLevel": 30},
            schedule_id="evening_overlap",
        ))
        # 8:30 PM matches both bedtime_all (added first) and evening_overlap
        dt = datetime(2026, 2, 20, 20, 30)
        assert self.agent.get_active_schedule(dt).schedule_id == "bedtime_all"

    def test_disabled_schedule_skipped(self):
        """Disabled schedules must not be returned."""
        self.agent._schedules[0].enabled = False
        dt = datetime(2026, 2, 20, 20, 30)
        assert self.agent.get_active_schedule(dt) is None


# ---------------------------------------------------------------------------
# Midnight-crossing schedules
# ---------------------------------------------------------------------------

class TestMidnightCrossingSchedules:
    """Test schedules whose time range crosses midnight."""

    def setup_method(self):
        self.agent = ProphecyAgent()
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.LATE_NIGHT,
            start_time=time(22, 0),
            end_time=time(5, 0),
            intent_template={"energyLevel": 5},
            schedule_id="late_night",
        ))

    def test_active_before_midnight(self):
        dt = datetime(2026, 2, 21, 23, 0)
        active = self.agent.get_active_schedule(dt)
        assert active is not None
        assert active.schedule_id == "late_night"

    def test_active_after_midnight(self):
        dt = datetime(2026, 2, 21, 2, 0)
        active = self.agent.get_active_schedule(dt)
        assert active is not None
        assert active.schedule_id == "late_night"

    def test_inactive_at_end_time(self):
        """End time is exclusive — 5:00 AM should not match."""
        dt = datetime(2026, 2, 21, 5, 0)
        assert self.agent.get_active_schedule(dt) is None

    def test_inactive_before_start(self):
        """9 PM is before the 10 PM start."""
        dt = datetime(2026, 2, 21, 21, 0)
        assert self.agent.get_active_schedule(dt) is None


# ---------------------------------------------------------------------------
# Intent shift prediction
# ---------------------------------------------------------------------------

class TestIntentShiftPrediction:
    """Test predicting next intent shifts."""

    def setup_method(self):
        self.agent = ProphecyAgent()
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={"energyLevel": 15},
        ))

    def test_predicts_next_schedule(self):
        """At 7 PM the next schedule shift is bedtime at 8 PM."""
        dt = datetime(2026, 2, 21, 19, 0)
        pred = self.agent.predict_next_intent_shift(dt)
        assert pred is not None
        assert pred["shift_type"] == "schedule"
        assert pred["shift_time"] == datetime(2026, 2, 21, 20, 0)
        assert pred["time_context"] == TimeContext.BEDTIME

    def test_returns_soonest_shift(self):
        """Bedtime at 8 PM is sooner than context transition at 10 PM."""
        dt = datetime(2026, 2, 21, 19, 30)
        pred = self.agent.predict_next_intent_shift(dt)
        assert pred is not None
        assert pred["shift_time"] == datetime(2026, 2, 21, 20, 0)

    def test_context_transition_when_no_schedule(self):
        """With no schedules, prediction falls back to context transitions."""
        agent = ProphecyAgent()
        dt = datetime(2026, 2, 21, 16, 0)  # AFTERNOON
        pred = agent.predict_next_intent_shift(dt)
        assert pred is not None
        assert pred["shift_type"] == "context"
        assert pred["time_context"] == TimeContext.EVENING


# ---------------------------------------------------------------------------
# Shift suggestions
# ---------------------------------------------------------------------------

class TestShiftSuggestions:
    """Test proactive shift suggestions with warning window."""

    def setup_method(self):
        self.agent = ProphecyAgent()
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={"energyLevel": 15},
        ))

    def test_suggestion_within_warning_window(self):
        """7:50 PM with 15-min warning → should suggest bedtime."""
        dt = datetime(2026, 2, 21, 19, 50)
        sug = self.agent.should_suggest_intent_shift(dt, warning_minutes=15)
        assert sug is not None
        assert sug["time_context"] == TimeContext.BEDTIME

    def test_no_suggestion_outside_window(self):
        """7:00 PM — bedtime at 8 PM is >15 min away."""
        dt = datetime(2026, 2, 21, 19, 0)
        assert self.agent.should_suggest_intent_shift(dt, 15) is None

    def test_no_suggestion_after_shift(self):
        """8:10 PM — bedtime shift already happened, next is far away."""
        dt = datetime(2026, 2, 21, 20, 10)
        sug = self.agent.should_suggest_intent_shift(dt, 15)
        # Next shift (LATE_NIGHT at 22:00) is ~110 min away — no suggestion
        assert sug is None


# ---------------------------------------------------------------------------
# Day-of-week filtering
# ---------------------------------------------------------------------------

class TestDayOfWeekFiltering:
    """Test that day-of-week filtering works correctly."""

    def setup_method(self):
        self.agent = ProphecyAgent()
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.MORNING,
            start_time=time(8, 0),
            end_time=time(12, 0),
            intent_template={"energyLevel": 70},
            days_of_week=[5, 6],  # Sat, Sun
            schedule_id="weekend",
        ))

    def test_active_on_saturday(self):
        dt = datetime(2026, 2, 21, 9, 0)  # Saturday
        assert self.agent.get_active_schedule(dt) is not None

    def test_active_on_sunday(self):
        dt = datetime(2026, 2, 22, 9, 0)  # Sunday
        assert self.agent.get_active_schedule(dt) is not None

    def test_inactive_on_monday(self):
        dt = datetime(2026, 2, 23, 9, 0)  # Monday
        assert self.agent.get_active_schedule(dt) is None

    def test_inactive_on_wednesday(self):
        dt = datetime(2026, 2, 25, 9, 0)  # Wednesday
        assert self.agent.get_active_schedule(dt) is None


# ---------------------------------------------------------------------------
# Manual override learning
# ---------------------------------------------------------------------------

class TestManualOverrideLearning:
    """Test recording manual intent overrides."""

    def setup_method(self):
        self.agent = ProphecyAgent()

    def test_record_override(self):
        dt = datetime(2026, 2, 21, 20, 15)
        self.agent.learn_from_manual_override(
            dt, {"energyLevel": 40}, {"energyLevel": 15}
        )
        assert len(self.agent._override_history) == 1
        override = self.agent._override_history[0]
        assert override.timestamp == dt
        assert override.actual_intent == {"energyLevel": 40}
        assert override.scheduled_intent == {"energyLevel": 15}
        assert override.time_context == TimeContext.BEDTIME

    def test_multiple_overrides_accumulate(self):
        for i in range(3):
            self.agent.learn_from_manual_override(
                datetime(2026, 2, 21, 20, i),
                {"energyLevel": 40},
                {"energyLevel": 15},
            )
        assert len(self.agent._override_history) == 3

    def test_override_includes_schedule_id(self):
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={"energyLevel": 15},
            schedule_id="bedtime_test",
        ))
        self.agent.learn_from_manual_override(
            datetime(2026, 2, 21, 20, 15),
            {"energyLevel": 40},
            {"energyLevel": 15},
        )
        assert self.agent._override_history[0].schedule_id == "bedtime_test"

    def test_override_without_active_schedule(self):
        """Override with no matching schedule should have schedule_id=None."""
        self.agent.learn_from_manual_override(
            datetime(2026, 2, 21, 15, 0),
            {"energyLevel": 50},
            {"energyLevel": 60},
        )
        assert self.agent._override_history[0].schedule_id is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test boundary conditions and edge cases."""

    def setup_method(self):
        self.agent = ProphecyAgent()

    def test_no_schedules_returns_none(self):
        dt = datetime(2026, 2, 21, 20, 0)
        assert self.agent.get_active_schedule(dt) is None

    def test_exact_start_time_is_active(self):
        """Start time is inclusive."""
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={},
        ))
        dt = datetime(2026, 2, 21, 20, 0, 0)
        assert self.agent.get_active_schedule(dt) is not None

    def test_exact_end_time_is_not_active(self):
        """End time is exclusive."""
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={},
        ))
        dt = datetime(2026, 2, 21, 22, 0, 0)
        assert self.agent.get_active_schedule(dt) is None

    def test_days_of_week_none_means_all_days(self):
        """days_of_week=None should match every day of the week."""
        self.agent.add_schedule(IntentSchedule(
            time_context=TimeContext.BEDTIME,
            start_time=time(20, 0),
            end_time=time(22, 0),
            intent_template={},
            days_of_week=None,
        ))
        # Monday Feb 16 through Sunday Feb 22
        for offset in range(7):
            dt = datetime(2026, 2, 16, 20, 30) + timedelta(days=offset)
            assert self.agent.get_active_schedule(dt) is not None, (
                f"Failed on day offset {offset} ({dt.strftime('%A')})"
            )

    def test_prediction_with_no_schedules(self):
        """With no schedules, prediction should still return context transitions."""
        dt = datetime(2026, 2, 21, 16, 0)
        pred = self.agent.predict_next_intent_shift(dt)
        assert pred is not None
        assert pred["shift_type"] == "context"
