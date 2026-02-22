"""Tests for the rules-first IntentTranslator."""

import pytest
from intent_engine.rules_translator import IntentTranslator, infer_time_bucket


class TestInferTimeBucket:
    """Unit tests for the time_bucket inference helper."""

    @pytest.mark.parametrize("hour,expected", [
        (7, "morning"),
        (10, "mid_morning"),
        (13, "afternoon"),
        (16, "afterschool"),
        (18, "evening"),
        (20, "bedtime"),
        (22, "late_night"),
        (3, "late_night"),
    ])
    def test_known_hours(self, hour, expected):
        assert infer_time_bucket(hour) == expected

    def test_midnight_wraps(self):
        assert infer_time_bucket(0) == "late_night"
        assert infer_time_bucket(24) == "late_night"  # 24 % 24 = 0

    def test_boundary_6am(self):
        """6 AM is the start of morning, not late_night."""
        assert infer_time_bucket(6) == "morning"

    def test_boundary_21(self):
        """21:00 starts late_night, not bedtime."""
        assert infer_time_bucket(21) == "late_night"


class TestIntentTranslator:
    """Tests for the IntentTranslator class."""

    def setup_method(self):
        self.translator = IntentTranslator()

    # --- keyword mapping ---

    def test_calm_keywords(self):
        intent = self.translator.translate("calm")
        assert "relaxing" in intent.keywords
        assert "gentle" in intent.keywords
        assert intent.preferences.get("mood") == "calm"
        assert intent.preferences.get("energy") == "low"

    def test_stem_keywords(self):
        intent = self.translator.translate("stem educational")
        assert "science" in intent.keywords
        assert "math" in intent.keywords
        assert intent.preferences.get("category") in ("stem", "educational")

    def test_fun_keywords(self):
        intent = self.translator.translate("fun energetic")
        assert "exciting" in intent.keywords
        assert "playful" in intent.keywords
        assert intent.preferences.get("mood") in ("fun", "energetic")

    def test_bedtime_sets_time_bucket(self):
        intent = self.translator.translate("bedtime")
        assert intent.preferences.get("time_bucket") == "bedtime"
        # bedtime text alone should still produce calm keywords
        assert "sleep" in intent.keywords or "relaxing" in intent.keywords

    def test_keywords_are_deduplicated(self):
        """'bedtime calm' both map 'relaxing' and 'gentle' — should appear once."""
        intent = self.translator.translate("bedtime calm")
        assert intent.keywords.count("relaxing") == 1
        assert intent.keywords.count("gentle") == 1

    # --- time_bucket inference from hour ---

    def test_hour_sets_time_bucket(self):
        intent = self.translator.translate("fun", hour=20)
        # Text doesn't set time_bucket, so hour should
        assert intent.preferences.get("time_bucket") == "bedtime"

    def test_text_time_bucket_takes_precedence(self):
        """If text says 'bedtime', that wins over hour=10 (mid_morning)."""
        intent = self.translator.translate("bedtime", hour=10)
        assert intent.preferences.get("time_bucket") == "bedtime"

    def test_aligned_time_boosts_priority(self):
        """When text says 'bedtime' and hour is 20 (bedtime), priority gets extra boost."""
        intent_aligned = self.translator.translate("bedtime", hour=20)
        intent_misaligned = self.translator.translate("bedtime", hour=10)
        assert intent_aligned.priority > intent_misaligned.priority

    # --- weekend inference ---

    def test_saturday_adds_weekend_keywords(self):
        intent = self.translator.translate("fun", day_of_week="saturday")
        assert "family" in intent.keywords
        assert "outdoor" in intent.keywords

    def test_weekday_does_not_add_weekend(self):
        intent = self.translator.translate("fun", day_of_week="monday")
        # 'family' and 'outdoor' should NOT be injected by weekend logic
        # (they may appear from 'fun' keywords though)
        assert intent.preferences.get("time_bucket") != "weekend"

    # --- safe defaults ---

    def test_empty_text_returns_browse(self):
        intent = self.translator.translate("")
        assert intent.intent_type == "browse"
        assert intent.keywords == []
        assert intent.priority == 0.5

    def test_none_text_returns_browse(self):
        """Passing no text should not crash."""
        intent = self.translator.translate()
        assert intent.intent_type == "browse"
        assert intent.priority == 0.5

    def test_unknown_text_returns_browse(self):
        intent = self.translator.translate("xyzzy foobar")
        assert intent.intent_type == "browse"
        assert intent.keywords == []

    def test_priority_clamped_to_1(self):
        """Even with many priority boosts, priority should not exceed 1.0."""
        intent = self.translator.translate(
            "bedtime calm stem afterschool weekend fun",
            hour=20,
            day_of_week="saturday",
        )
        assert intent.priority <= 1.0

    def test_priority_never_negative(self):
        intent = self.translator.translate("")
        assert intent.priority >= 0.0

    # --- intent_type inference ---

    def test_stem_intent_type(self):
        intent = self.translator.translate("stem")
        assert intent.intent_type == "educational"

    def test_calm_intent_type(self):
        intent = self.translator.translate("calm")
        assert intent.intent_type == "calm"

    def test_fun_intent_type(self):
        intent = self.translator.translate("fun")
        assert intent.intent_type == "entertainment"

    def test_bedtime_intent_type(self):
        intent = self.translator.translate("bedtime")
        assert intent.intent_type == "calm"

    # --- custom keyword map ---

    def test_custom_keyword_map(self):
        custom = {
            "cooking": (["recipe", "kitchen"], {"category": "cooking"}, 0.1),
        }
        translator = IntentTranslator(keyword_map=custom)
        intent = translator.translate("cooking")
        assert "recipe" in intent.keywords
        assert intent.preferences.get("category") == "cooking"
