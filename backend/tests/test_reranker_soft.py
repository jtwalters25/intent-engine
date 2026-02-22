"""Tests for soft-constraint reranker behavior.

These tests verify the key invariant: intent is a SOFT constraint that
re-ranks items but never filters them out. Every candidate that goes in
must come out, regardless of how poorly it matches the intent.
"""

import pytest
from intent_engine.schemas import Intent, UserContext, CandidateItem
from intent_engine.simple_ranker import IntentRanker


def _make_context(keywords=None, preferences=None, priority=0.9):
    """Helper to build a UserContext with a given intent."""
    return UserContext(
        user_id="test_user",
        intent=Intent(
            intent_type="test",
            keywords=keywords or [],
            preferences=preferences or {},
            priority=priority,
        ),
    )


def _make_item(item_id, title, base_score=0.5, **attrs):
    """Helper to build a CandidateItem."""
    return CandidateItem(
        item_id=item_id,
        title=title,
        attributes=attrs,
        base_score=base_score,
    )


# ---------------------------------------------------------------------------
# Soft constraint: all items survive
# ---------------------------------------------------------------------------

class TestSoftConstraint:
    """Intent re-ranking must never drop items."""

    def test_all_items_returned(self):
        """Every input candidate must appear in the output, even if zero match."""
        ranker = IntentRanker(intent_weight=1.0)
        context = _make_context(keywords=["quantum", "physics"])

        candidates = [
            _make_item("a", "Cooking 101", base_score=0.9, category="cooking"),
            _make_item("b", "Gardening Tips", base_score=0.8, category="garden"),
            _make_item("c", "Cat Videos", base_score=0.7, category="pets"),
        ]

        ranked = ranker.rank(candidates, context)
        assert len(ranked) == len(candidates)
        output_ids = {r.item.item_id for r in ranked}
        assert output_ids == {"a", "b", "c"}

    def test_non_matching_items_get_lower_score(self):
        """Items that don't match intent should score lower, but not be removed."""
        ranker = IntentRanker(intent_weight=0.6)
        context = _make_context(
            keywords=["science", "experiment"],
            preferences={"category": "stem"},
        )

        matching = _make_item("match", "Science Experiment", base_score=0.5,
                              category="stem", tags=["science", "experiment"])
        non_matching = _make_item("nomatch", "Dance Party", base_score=0.5,
                                  category="music", tags=["dance", "fun"])

        ranked = ranker.rank([matching, non_matching], context)

        assert len(ranked) == 2
        scores = {r.item.item_id: r.final_score for r in ranked}
        assert scores["match"] > scores["nomatch"]

    def test_high_base_score_can_overcome_low_intent(self):
        """A non-matching item with very high base_score can still rank above
        a matching item with low base_score, depending on intent_weight."""
        ranker = IntentRanker(intent_weight=0.3)  # base score matters more
        context = _make_context(keywords=["science"])

        weak_match = _make_item("weak", "Science Fun", base_score=0.2,
                                tags=["science"])
        strong_base = _make_item("strong", "Dance Party", base_score=0.95,
                                 tags=["dance"])

        ranked = ranker.rank([weak_match, strong_base], context)
        # With 70% base weight and 0.95 base, strong_base should win
        assert ranked[0].item.item_id == "strong"

    def test_zero_intent_weight_preserves_base_order(self):
        """With intent_weight=0, output order should match base_score order."""
        ranker = IntentRanker(intent_weight=0.0)
        context = _make_context(keywords=["zzz_never_matches"])

        items = [
            _make_item("low", "Low", base_score=0.3),
            _make_item("mid", "Mid", base_score=0.6),
            _make_item("high", "High", base_score=0.9),
        ]

        ranked = ranker.rank(items, context)
        assert [r.item.item_id for r in ranked] == ["high", "mid", "low"]

    def test_full_intent_weight_orders_by_intent(self):
        """With intent_weight=1.0, base_score is ignored entirely."""
        ranker = IntentRanker(intent_weight=1.0)
        context = _make_context(
            keywords=["python"],
            preferences={"category": "tech"},
        )

        python_item = _make_item("py", "Python Guide", base_score=0.1,
                                 category="tech", tags=["python"])
        java_item = _make_item("java", "Java Guide", base_score=0.99,
                               category="tech", tags=["java"])

        ranked = ranker.rank([python_item, java_item], context)
        # python_item should win on intent despite terrible base_score
        assert ranked[0].item.item_id == "py"


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

class TestExplanations:
    """Each ranked item should carry 2-3 human-readable explanation lines."""

    def test_explanations_list_has_at_least_2_lines(self):
        ranker = IntentRanker()
        context = _make_context(keywords=["science"])
        items = [_make_item("a", "Science Fun", tags=["science"])]

        ranked = ranker.rank(items, context)
        assert len(ranked[0].explanations) >= 2

    def test_explanations_list_has_at_most_3_lines(self):
        ranker = IntentRanker()
        context = _make_context(keywords=["science"])
        items = [_make_item("a", "Science Fun", base_score=0.9,
                            tags=["science"])]

        ranked = ranker.rank(items, context)
        assert len(ranked[0].explanations) <= 3

    def test_explanation_string_is_joined_lines(self):
        """The legacy `explanation` field should be the lines joined by '; '."""
        ranker = IntentRanker()
        context = _make_context(keywords=["science"])
        items = [_make_item("a", "Science Fun", tags=["science"])]

        ranked = ranker.rank(items, context)
        assert ranked[0].explanation == "; ".join(ranked[0].explanations)

    def test_no_match_explanation_is_clear(self):
        """When nothing matches, the explanation should say so explicitly."""
        ranker = IntentRanker()
        context = _make_context(keywords=["quantum"])
        items = [_make_item("a", "Dance Party", tags=["dance"])]

        ranked = ranker.rank(items, context)
        assert "no direct keyword" in ranked[0].explanations[0].lower()

    def test_matching_explanation_mentions_keywords(self):
        ranker = IntentRanker()
        context = _make_context(keywords=["science", "math"])
        items = [_make_item("a", "Science and Math", tags=["science", "math"])]

        ranked = ranker.rank(items, context)
        first_line = ranked[0].explanations[0].lower()
        assert "science" in first_line or "math" in first_line

    def test_score_tier_in_second_line(self):
        """Second explanation line should contain a score tier."""
        ranker = IntentRanker()
        context = _make_context(keywords=["science"])
        items = [_make_item("a", "Science Fun", tags=["science"])]

        ranked = ranker.rank(items, context)
        second_line = ranked[0].explanations[1].lower()
        assert any(tier in second_line for tier in ["strong", "moderate", "weak"])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Ranking must be deterministic — same input always produces same output."""

    def test_repeated_runs_identical(self):
        ranker = IntentRanker(intent_weight=0.5)
        context = _make_context(keywords=["adventure", "fun"])
        items = [
            _make_item("a", "Adventure Quest", base_score=0.7, tags=["adventure"]),
            _make_item("b", "Math Puzzle", base_score=0.8, tags=["math"]),
            _make_item("c", "Fun Games", base_score=0.6, tags=["fun", "games"]),
        ]

        r1 = ranker.rank(items, context)
        r2 = ranker.rank(items, context)

        assert [r.item.item_id for r in r1] == [r.item.item_id for r in r2]
        assert [r.final_score for r in r1] == [r.final_score for r in r2]
