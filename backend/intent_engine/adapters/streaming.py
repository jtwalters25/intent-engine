"""Streaming domain adapter (Netflix-style content ranking)."""

from typing import Any, Dict

from intent_engine.schemas import Domain, Item, MultiplierSet, StreamingIntent


# Keyword → intent mapping
_KEYWORD_MAP: Dict[str, StreamingIntent] = {
    "calm": StreamingIntent.CALM,
    "soothing": StreamingIntent.CALM,
    "bedtime": StreamingIntent.CALM,
    "wind down": StreamingIntent.CALM,
    "relax": StreamingIntent.CALM,
    "quiet": StreamingIntent.CALM,
    "educational": StreamingIntent.EDUCATIONAL,
    "learning": StreamingIntent.EDUCATIONAL,
    "stem": StreamingIntent.EDUCATIONAL,
    "science": StreamingIntent.EDUCATIONAL,
    "math": StreamingIntent.EDUCATIONAL,
    "popular": StreamingIntent.POPULAR,
    "trending": StreamingIntent.POPULAR,
    "top": StreamingIntent.POPULAR,
    "hits": StreamingIntent.POPULAR,
    "new": StreamingIntent.DISCOVERY,
    "discover": StreamingIntent.DISCOVERY,
    "explore": StreamingIntent.DISCOVERY,
    "surprise": StreamingIntent.DISCOVERY,
}

# Time-of-day buckets
_TIME_BUCKETS = {
    "early_morning": (5, 8),
    "morning": (8, 12),
    "afternoon": (12, 17),
    "evening": (17, 20),
    "bedtime": (20, 22),
    "late_night": (22, 5),
}


def _resolve_time_bucket(hour: int) -> str:
    """Map hour (0-23) to a named time bucket."""
    if 5 <= hour < 8:
        return "early_morning"
    elif 8 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 20:
        return "evening"
    elif 20 <= hour < 22:
        return "bedtime"
    else:
        return "late_night"


class StreamingAdapter:
    """Domain adapter for streaming content (Netflix-style)."""

    @property
    def domain(self) -> Domain:
        return Domain.STREAMING

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve raw intent signals into canonical streaming intent."""
        intent_type = StreamingIntent.UNKNOWN
        energy_level = raw_input.get("energy_level", 0.5)
        time_bucket = raw_input.get("time_bucket", "afternoon")

        # Check keywords
        keywords = raw_input.get("keywords", [])
        intent_text = raw_input.get("intent_text", "")
        search_text = " ".join(keywords).lower()
        if intent_text:
            search_text += " " + intent_text.lower()

        for keyword, mapped_intent in _KEYWORD_MAP.items():
            if keyword in search_text:
                intent_type = mapped_intent
                break

        # Infer from time if still unknown
        if intent_type == StreamingIntent.UNKNOWN:
            if time_bucket == "bedtime":
                intent_type = StreamingIntent.CALM
            elif time_bucket == "early_morning":
                intent_type = StreamingIntent.CALM

        # Infer from energy level
        if intent_type == StreamingIntent.UNKNOWN and energy_level < 0.3:
            intent_type = StreamingIntent.CALM

        return {
            "intent_type": intent_type.value,
            "energy_level": energy_level,
            "time_bucket": time_bucket,
            "viewer_profile": raw_input.get("viewer_profile", "family"),
        }

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        """Compute multipliers based on streaming-specific signals."""
        attrs = item.attributes
        calm_score = float(attrs.get("calm_score", 0.5))
        maturity = attrs.get("maturity", "family")
        complexity = float(attrs.get("complexity", 0.5))

        intent_type = intent.get("intent_type", "unknown")
        energy_level = float(intent.get("energy_level", 0.5))
        time_bucket = intent.get("time_bucket", "afternoon")
        viewer_profile = intent.get("viewer_profile", "family")

        # Context multiplier: time-of-day alignment
        context = 1.0
        if time_bucket in ("bedtime", "late_night"):
            context = 0.6 + 0.8 * calm_score  # calm items boosted
        elif time_bucket == "early_morning":
            context = 0.7 + 0.6 * calm_score

        # Profile multiplier: maturity gating
        profile = 1.0
        if viewer_profile == "kids":
            if maturity == "adult":
                profile = 0.0  # hard gate via multiplier
            elif maturity == "teen":
                profile = 0.3
            elif maturity == "kids":
                profile = 1.2
        elif viewer_profile == "adult":
            if maturity == "kids":
                profile = 0.7

        # Urgency multiplier: energy alignment
        urgency = 1.0
        if intent_type == "calm":
            urgency = 0.5 + calm_score  # strongly favor calm
        elif intent_type == "popular":
            urgency = 0.8 + 0.4 * (1.0 - calm_score)  # favor stimulating

        # Energy level influence
        if energy_level < 0.3:
            urgency *= (0.6 + 0.8 * calm_score)
        elif energy_level > 0.7:
            urgency *= (0.6 + 0.8 * (1.0 - calm_score))

        # Cost multiplier: N/A for streaming
        cost = 1.0

        # Prophecy: schedule-based boost
        prophecy = 1.0
        if intent_type == "calm":
            prophecy = 1.0 + 0.3 * calm_score
        elif intent_type == "educational":
            prophecy = 1.0 + 0.3 * complexity

        return MultiplierSet(
            context=round(context, 3),
            profile=round(profile, 3),
            urgency=round(urgency, 3),
            cost=cost,
            prophecy=round(prophecy, 3),
        )

    def apply_hard_constraints(
        self, item: Item, constraints: Dict[str, Any]
    ) -> bool:
        """Block adult content for kids maturity gate."""
        maturity_gate = constraints.get("maturity_gate")
        if maturity_gate == "kids":
            item_maturity = item.attributes.get("maturity", "family")
            if item_maturity == "adult":
                return True
        return False

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        """Generate human-readable explanation."""
        parts = []
        if multipliers.profile == 0.0:
            return f"'{item.title}' blocked: adult content not suitable for kids profile"
        if multipliers.context > 1.1:
            parts.append("good time-of-day fit")
        elif multipliers.context < 0.8:
            parts.append("less aligned with current time")
        if multipliers.urgency > 1.1:
            parts.append("matches energy intent")
        elif multipliers.urgency < 0.8:
            parts.append("energy mismatch")
        if multipliers.prophecy > 1.1:
            parts.append("schedule-boosted")
        if multipliers.profile > 1.0:
            parts.append("age-appropriate boost")

        if not parts:
            return f"'{item.title}' ranked by base engagement score"
        return f"'{item.title}': {', '.join(parts)}"

    def diversity_key(self, item: Item) -> str:
        """Group by genre/category for diversity."""
        return item.attributes.get("genre", item.category or "unknown")
