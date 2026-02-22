"""Rules-first intent translator.

Converts raw user input (scenario text + optional time context) into a
structured Intent object using keyword mapping, time_bucket inference,
and safe defaults. No LLM required — deterministic and testable.

Design decisions:
- Keyword mapping is a flat dict so it's easy to audit and extend.
- time_bucket is inferred from hour-of-day; callers can also pass it explicitly.
- When nothing matches, we return a neutral Intent (safe defaults) rather
  than raising or returning None. This keeps the downstream ranker happy.
- Priority is boosted when multiple signals align (e.g. "bedtime" text + evening hour).
"""

from typing import Dict, List, Optional, Tuple
from .schemas import Intent


# ---------------------------------------------------------------------------
# Keyword mapping tables
# ---------------------------------------------------------------------------
# Each entry: input_keyword -> (output_keywords, preferences_patch, priority_delta)
# output_keywords get merged into Intent.keywords
# preferences_patch gets merged into Intent.preferences
# priority_delta adjusts the final priority (clamped to 0.0-1.0)

KEYWORD_MAP: Dict[str, Tuple[List[str], Dict, float]] = {
    # Mood / energy
    "calm": (["relaxing", "gentle", "quiet", "soothing"], {"mood": "calm", "energy": "low"}, 0.0),
    "relaxing": (["relaxing", "gentle", "soothing"], {"mood": "calm", "energy": "low"}, 0.0),
    "energetic": (["exciting", "active", "upbeat"], {"mood": "energetic", "energy": "high"}, 0.0),
    "fun": (["exciting", "playful", "adventure", "games", "funny"], {"mood": "fun", "energy": "high"}, 0.0),
    "creative": (["art", "craft", "music", "drawing", "building"], {"mood": "creative"}, 0.0),

    # Time-of-day contexts
    "bedtime": (["sleep", "relaxing", "gentle", "quiet", "lullaby", "wind-down"],
                {"mood": "calm", "energy": "low", "time_bucket": "bedtime"}, 0.1),
    "afterschool": (["educational", "engaging", "interactive", "homework-friendly"],
                    {"time_bucket": "afterschool"}, 0.05),
    "morning": (["bright", "cheerful", "wake-up"], {"time_bucket": "morning"}, 0.0),
    "weekend": (["adventure", "family", "outdoor", "long-form", "special"],
                {"time_bucket": "weekend", "energy": "high"}, 0.05),

    # Content domains
    "stem": (["science", "math", "engineering", "technology", "experiment", "coding", "robot"],
             {"category": "stem"}, 0.05),
    "science": (["science", "experiment", "nature", "space"], {"category": "stem"}, 0.0),
    "math": (["math", "numbers", "puzzle", "logic"], {"category": "stem"}, 0.0),
    "stories": (["story", "narrative", "fairy-tale", "adventure"], {"category": "stories"}, 0.0),
    "music": (["music", "songs", "rhythm", "instruments"], {"category": "music"}, 0.0),
    "art": (["art", "drawing", "painting", "craft"], {"category": "art"}, 0.0),
    "nature": (["nature", "animals", "outdoor", "garden"], {"category": "nature"}, 0.0),
    "educational": (["learning", "educational", "teaching", "lesson"], {"category": "educational"}, 0.0),
}


# ---------------------------------------------------------------------------
# Time bucket inference
# ---------------------------------------------------------------------------
# Maps hour ranges to bucket names. Ranges are [start, end).

TIME_BUCKET_RANGES: List[Tuple[int, int, str]] = [
    (6, 9, "morning"),
    (9, 12, "mid_morning"),
    (12, 15, "afternoon"),
    (15, 17, "afterschool"),
    (17, 19, "evening"),
    (19, 21, "bedtime"),
    (21, 24, "late_night"),
    (0, 6, "late_night"),
]


def infer_time_bucket(hour: int) -> str:
    """Return a time_bucket string for the given hour (0-23).

    Falls back to "unknown" if hour is out of range, which should never
    happen in practice but keeps us safe.
    """
    hour = hour % 24  # normalize
    for start, end, bucket in TIME_BUCKET_RANGES:
        if start <= hour < end:
            return bucket
    return "unknown"


# ---------------------------------------------------------------------------
# Translator
# ---------------------------------------------------------------------------

class IntentTranslator:
    """Rules-first intent translator.

    Translates a free-text scenario description (plus optional time/day
    context) into a structured Intent suitable for the IntentRanker.

    Usage:
        translator = IntentTranslator()
        intent = translator.translate("bedtime calm", hour=20)
    """

    def __init__(self, keyword_map: Optional[Dict] = None):
        """Allow overriding the keyword map for testing or domain customization."""
        self.keyword_map = keyword_map or KEYWORD_MAP

    def translate(
        self,
        text: str = "",
        *,
        hour: Optional[int] = None,
        day_of_week: Optional[str] = None,
    ) -> Intent:
        """Translate scenario text + context into a structured Intent.

        Args:
            text: Free-text scenario description, e.g. "bedtime calm" or
                  "afterschool STEM activity".
            hour: Optional hour of day (0-23) for time_bucket inference.
            day_of_week: Optional day name (e.g. "saturday") for weekend
                         detection.

        Returns:
            A populated Intent with keywords, preferences, and priority.
            Never raises — returns safe defaults on empty/unknown input.
        """
        keywords: List[str] = []
        preferences: Dict = {}
        priority_delta: float = 0.0

        # --- Step 1: keyword mapping from text ---
        normalized = text.lower().strip()
        matched_input_keywords: List[str] = []

        for input_kw, (out_kws, prefs_patch, p_delta) in self.keyword_map.items():
            if input_kw in normalized:
                matched_input_keywords.append(input_kw)
                # Merge output keywords (deduplicated later)
                keywords.extend(out_kws)
                # Merge preferences (later values overwrite earlier)
                preferences.update(prefs_patch)
                priority_delta += p_delta

        # --- Step 2: time_bucket inference from hour ---
        if hour is not None:
            bucket = infer_time_bucket(hour)
            # Only set if text didn't already set a time_bucket
            if "time_bucket" not in preferences:
                preferences["time_bucket"] = bucket
            # Boost priority when time context aligns with text context
            text_bucket = preferences.get("time_bucket")
            if text_bucket == bucket:
                priority_delta += 0.05

        # --- Step 3: weekend inference from day_of_week ---
        if day_of_week and day_of_week.lower() in ("saturday", "sunday"):
            if "time_bucket" not in preferences or preferences["time_bucket"] != "weekend":
                # Weekend context adds outdoor/family keywords
                keywords.extend(["family", "outdoor"])
                preferences.setdefault("time_bucket", "weekend")
                priority_delta += 0.05

        # --- Step 4: deduplicate keywords ---
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # --- Step 5: compute priority with safe clamping ---
        # Base priority: 0.7 if we matched something, 0.5 for safe default
        base_priority = 0.7 if matched_input_keywords else 0.5
        priority = max(0.0, min(1.0, base_priority + priority_delta))

        # --- Step 6: safe defaults ---
        # If nothing matched, return a neutral intent that won't distort ranking
        if not unique_keywords:
            return Intent(
                intent_type="browse",
                keywords=[],
                preferences=preferences if preferences else {},
                priority=0.5,
            )

        # Determine intent_type from the strongest signal
        intent_type = self._infer_intent_type(matched_input_keywords, preferences)

        return Intent(
            intent_type=intent_type,
            keywords=unique_keywords,
            preferences=preferences,
            priority=priority,
        )

    def _infer_intent_type(
        self, matched_keywords: List[str], preferences: Dict
    ) -> str:
        """Derive a human-readable intent_type from matched signals.

        This is a simple heuristic — the first matching category wins.
        """
        category = preferences.get("category", "")
        mood = preferences.get("mood", "")
        time_bucket = preferences.get("time_bucket", "")

        if category in ("stem", "educational"):
            return "educational"
        if mood in ("calm",) or time_bucket == "bedtime":
            return "calm"
        if mood in ("fun", "energetic") or time_bucket == "weekend":
            return "entertainment"
        if category in ("stories", "music", "art", "nature"):
            return "explore"
        return "browse"
