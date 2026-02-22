"""Demo script for ProphecyAgent — time-aware intent scheduling.

Demonstrates:
  1. Time context inference throughout the day
  2. Scheduled intents with time ranges and day-of-week filtering
  3. Active schedule detection
  4. Intent shift predictions
  5. Proactive suggestions before shifts

Scenarios:
  - Friday 7:45 PM — 15 minutes before bedtime (should get suggestion)
  - Friday 8:00 PM — bedtime schedule active
  - Saturday 9:00 AM — weekend morning schedule active
"""

from datetime import datetime, time

from intent_engine.prophecy_agent import ProphecyAgent, TimeContext, IntentSchedule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def divider(char: str = "=", width: int = 78) -> None:
    """Print a visual divider."""
    print(char * width)


def print_scenario(
    agent: ProphecyAgent, check_time: datetime, label: str
) -> None:
    """Run a single scenario and print all results."""
    divider("-")
    print(f"  {label}")
    print(f"  Time: {check_time.strftime('%A, %I:%M %p')}")
    print()

    # Time context
    context = agent.infer_time_context(check_time)
    print(f"  Time Context: {context.value}")

    # Active schedule
    active = agent.get_active_schedule(check_time)
    if active:
        print(f"  ✅ Active Schedule: {active.time_context.value}")
        print(f"     Time range : {active.start_time.strftime('%H:%M')} – "
              f"{active.end_time.strftime('%H:%M')}")
        print(f"     Intent     : {active.intent_template}")
        if active.days_of_week is not None:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            days = [day_names[d] for d in active.days_of_week]
            print(f"     Days       : {', '.join(days)}")
    else:
        print("  ✅ Active Schedule: None (using default intent)")

    print()

    # Suggestion
    suggestion = agent.should_suggest_intent_shift(check_time, warning_minutes=15)
    if suggestion:
        shift_time = suggestion["shift_time"]
        minutes_until = int((shift_time - check_time).total_seconds() / 60)
        print(f"  🔔 Suggestion: Intent shift in {minutes_until} minutes!")
        print(f"     Next context : {suggestion['time_context'].value} "
              f"at {shift_time.strftime('%I:%M %p')}")
        print(f"     Intent       : {suggestion['intent_template']}")
    else:
        print("  🔔 Suggestion: (none — no imminent shift)")

    print()

    # Prediction
    prediction = agent.predict_next_intent_shift(check_time)
    if prediction:
        shift_time = prediction["shift_time"]
        hours_until = (shift_time - check_time).total_seconds() / 3600
        print(f"  🔮 Prediction: {prediction['shift_type'].capitalize()} shift "
              f"in {hours_until:.1f} h")
        print(f"     At          : {shift_time.strftime('%A, %I:%M %p')}")
        print(f"     New context : {prediction['time_context'].value}")
        print(f"     Intent      : {prediction['intent_template']}")
    else:
        print("  🔮 Prediction: (none)")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    divider()
    print("  ProphecyAgent Demo — Time-Aware Intent Scheduling")
    divider()
    print()

    agent = ProphecyAgent()

    # --- Add schedules ------------------------------------------------------

    agent.add_schedule(IntentSchedule(
        time_context=TimeContext.BEDTIME,
        start_time=time(20, 0),
        end_time=time(22, 0),
        intent_template={
            "energyLevel": 15,
            "learningFocus": ["emotional", "mindfulness"],
            "tone": "soothing",
        },
        recurring=True,
        days_of_week=None,  # every day
        schedule_id="bedtime_daily",
    ))

    agent.add_schedule(IntentSchedule(
        time_context=TimeContext.MORNING,
        start_time=time(8, 0),
        end_time=time(12, 0),
        intent_template={
            "energyLevel": 70,
            "learningFocus": ["creative", "play"],
            "tone": "energetic",
        },
        recurring=True,
        days_of_week=[5, 6],  # Saturday, Sunday
        schedule_id="weekend_morning",
    ))

    print("  Schedules configured:")
    print("    1. Bedtime   — 20:00-22:00 daily")
    print("    2. Weekend AM — 08:00-12:00 Sat-Sun")
    print()

    # --- Scenario 1: Friday 7:45 PM ----------------------------------------

    print_scenario(
        agent,
        datetime(2026, 2, 20, 19, 45),  # Friday
        "Scenario 1 — Friday evening, 15 min before bedtime",
    )

    # --- Scenario 2: Friday 8:00 PM ----------------------------------------

    print_scenario(
        agent,
        datetime(2026, 2, 20, 20, 0),  # Friday
        "Scenario 2 — Friday bedtime, schedule active",
    )

    # --- Scenario 3: Saturday 9:00 AM --------------------------------------

    print_scenario(
        agent,
        datetime(2026, 2, 21, 9, 0),  # Saturday
        "Scenario 3 — Saturday morning, weekend schedule",
    )

    # --- Override demo ------------------------------------------------------

    divider("-")
    print("  Manual Override Learning")
    print()
    override_time = datetime(2026, 2, 20, 20, 15)
    scheduled = {"energyLevel": 15, "tone": "soothing"}
    actual = {"energyLevel": 40, "tone": "energetic"}

    agent.learn_from_manual_override(override_time, actual, scheduled)

    print(f"  Recorded override at {override_time.strftime('%I:%M %p')}")
    print(f"    Scheduled : {scheduled}")
    print(f"    Actual    : {actual}")
    print(f"  Total overrides tracked: {len(agent._override_history)}")
    print()

    divider()
    print("  Demo complete!")
    divider()
    print()


if __name__ == "__main__":
    main()
