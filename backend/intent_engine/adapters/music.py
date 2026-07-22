"""Music domain adapter (Spotify-style playlist/track ranking)."""

from typing import Any, Dict

from intent_engine.schemas import Domain, Item, MultiplierSet, MusicIntent


# Keyword → intent mapping
_KEYWORD_MAP: Dict[str, MusicIntent] = {
    "focus": MusicIntent.FOCUS,
    "study": MusicIntent.FOCUS,
    "concentrate": MusicIntent.FOCUS,
    "deep work": MusicIntent.FOCUS,
    "calm": MusicIntent.CALM,
    "relax": MusicIntent.CALM,
    "sleep": MusicIntent.CALM,
    "wind down": MusicIntent.CALM,
    "chill": MusicIntent.CALM,
    "soothing": MusicIntent.CALM,
    "upbeat": MusicIntent.UPBEAT,
    "energetic": MusicIntent.UPBEAT,
    "party": MusicIntent.UPBEAT,
    "workout": MusicIntent.UPBEAT,
    "pump": MusicIntent.UPBEAT,
    "dance": MusicIntent.UPBEAT,
    "new": MusicIntent.DISCOVERY,
    "discover": MusicIntent.DISCOVERY,
    "explore": MusicIntent.DISCOVERY,
    "fresh": MusicIntent.DISCOVERY,
}


class MusicAdapter:
    """Domain adapter for music (Spotify-style playlists and tracks)."""

    @property
    def domain(self) -> Domain:
        return Domain.MUSIC

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve raw intent signals into canonical music intent."""
        intent_type = MusicIntent.UNKNOWN
        energy_level = float(raw_input.get("energy_level", 0.5))
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

        # Infer from time / energy when still unknown
        if intent_type == MusicIntent.UNKNOWN:
            if time_bucket in ("bedtime", "late_night"):
                intent_type = MusicIntent.CALM
            elif energy_level > 0.7:
                intent_type = MusicIntent.UPBEAT
            elif energy_level < 0.3:
                intent_type = MusicIntent.CALM

        return {
            "intent_type": intent_type.value,
            "energy_level": energy_level,
            "time_bucket": time_bucket,
            "listener_profile": raw_input.get("listener_profile", "family"),
        }

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        """Compute multipliers based on music-specific signals."""
        attrs = item.attributes
        calm_score = float(attrs.get("calm_score", 0.5))
        energy = float(attrs.get("energy", 1.0 - calm_score))
        focus_friendly = float(attrs.get("focus_friendly", 0.5))
        maturity = attrs.get("maturity", "family")

        intent_type = intent.get("intent_type", "unknown")
        energy_level = float(intent.get("energy_level", 0.5))
        time_bucket = intent.get("time_bucket", "afternoon")
        listener_profile = intent.get("listener_profile", "family")

        # Context multiplier: time-of-day alignment
        context = 1.0
        if time_bucket in ("bedtime", "late_night"):
            context = 0.6 + 0.8 * calm_score  # calm tracks boosted
        elif time_bucket == "early_morning":
            context = 0.7 + 0.6 * calm_score

        # Profile multiplier: maturity / explicit gating for kids listeners
        profile = 1.0
        if listener_profile == "kids":
            if maturity == "adult":
                profile = 0.0  # hard gate via multiplier
            elif maturity == "teen":
                profile = 0.3
            elif maturity == "kids":
                profile = 1.2
        elif listener_profile == "adult":
            if maturity == "kids":
                profile = 0.8

        # Urgency multiplier: intent-driven energy/focus alignment
        urgency = 1.0
        if intent_type == "focus":
            urgency = 0.7 + 0.6 * focus_friendly  # favor background-friendly
        elif intent_type == "calm":
            urgency = 0.5 + calm_score  # strongly favor calm
        elif intent_type == "upbeat":
            urgency = 0.6 + 0.8 * energy  # favor high-energy

        # Energy level influence
        if energy_level < 0.3:
            urgency *= (0.6 + 0.8 * calm_score)
        elif energy_level > 0.7:
            urgency *= (0.6 + 0.8 * energy)

        # Cost multiplier: N/A for music
        cost = 1.0

        # Prophecy: schedule / routine boost
        prophecy = 1.0
        if intent_type == "calm":
            prophecy = 1.0 + 0.3 * calm_score
        elif intent_type == "focus":
            prophecy = 1.0 + 0.3 * focus_friendly

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
        """Block adult content for kids, or explicit tracks when filtered."""
        maturity_gate = constraints.get("maturity_gate")
        if maturity_gate == "kids":
            if item.attributes.get("maturity", "family") == "adult":
                return True
        if constraints.get("block_explicit"):
            if item.attributes.get("explicit", False):
                return True
        return False

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        """Generate human-readable explanation."""
        if multipliers.profile == 0.0:
            return f"'{item.title}' blocked: explicit/adult content not suitable for kids profile"
        parts = []
        if multipliers.context > 1.1:
            parts.append("good time-of-day fit")
        elif multipliers.context < 0.8:
            parts.append("less aligned with current time")
        if multipliers.urgency > 1.1:
            parts.append("matches listening energy")
        elif multipliers.urgency < 0.8:
            parts.append("energy mismatch")
        if multipliers.prophecy > 1.1:
            parts.append("routine-boosted")
        if multipliers.profile > 1.0:
            parts.append("age-appropriate boost")

        if not parts:
            return f"'{item.title}' ranked by base engagement score"
        return f"'{item.title}': {', '.join(parts)}"

    def diversity_key(self, item: Item) -> str:
        """Group by genre for diversity."""
        return item.attributes.get("genre", item.category or "unknown")
