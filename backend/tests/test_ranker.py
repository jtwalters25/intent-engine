"""Tests for the IntentRanker."""

import pytest
from intent_engine.schemas import Intent, UserContext, CandidateItem
from intent_engine.simple_ranker import IntentRanker


class TestIntentRanker:
    """Tests for IntentRanker class."""
    
    def test_ranker_initialization(self):
        """Test ranker initialization with valid weight."""
        ranker = IntentRanker(intent_weight=0.5)
        assert ranker.intent_weight == 0.5
    
    def test_ranker_default_weight(self):
        """Test ranker default weight."""
        ranker = IntentRanker()
        assert ranker.intent_weight == 0.5
    
    def test_ranker_weight_validation(self):
        """Test that intent_weight must be between 0 and 1."""
        # Valid weights
        IntentRanker(intent_weight=0.0)
        IntentRanker(intent_weight=0.5)
        IntentRanker(intent_weight=1.0)
        
        # Invalid weights should raise ValueError
        with pytest.raises(ValueError):
            IntentRanker(intent_weight=-0.1)
        
        with pytest.raises(ValueError):
            IntentRanker(intent_weight=1.5)
    
    def test_keyword_match_scoring(self):
        """Test keyword matching logic."""
        ranker = IntentRanker()
        item = CandidateItem(
            item_id="item1",
            title="Python Machine Learning Tutorial",
            attributes={"tags": ["python", "ml"]},
            base_score=0.5
        )
        keywords = ["python", "machine learning"]
        
        score = ranker._calculate_keyword_match_score(item, keywords)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should match both keywords
    
    def test_keyword_match_no_keywords(self):
        """Test keyword matching with no keywords."""
        ranker = IntentRanker()
        item = CandidateItem(
            item_id="item1",
            title="Test",
            base_score=0.5
        )
        
        score = ranker._calculate_keyword_match_score(item, [])
        assert score == 0.5  # Neutral score
    
    def test_preference_match_scoring(self):
        """Test preference matching logic."""
        ranker = IntentRanker()
        item = CandidateItem(
            item_id="item1",
            title="Test",
            attributes={"category": "technology", "difficulty": "intermediate"},
            base_score=0.5
        )
        preferences = {"category": "technology", "difficulty": "intermediate"}
        
        score = ranker._calculate_preference_match_score(item, preferences)
        assert score == 1.0  # Perfect match
    
    def test_preference_match_partial(self):
        """Test partial preference matching."""
        ranker = IntentRanker()
        item = CandidateItem(
            item_id="item1",
            title="Test",
            attributes={"category": "technology"},
            base_score=0.5
        )
        preferences = {"category": "technology", "difficulty": "intermediate"}
        
        score = ranker._calculate_preference_match_score(item, preferences)
        assert score == 0.5  # One of two matches
    
    def test_preference_match_no_preferences(self):
        """Test preference matching with no preferences."""
        ranker = IntentRanker()
        item = CandidateItem(
            item_id="item1",
            title="Test",
            base_score=0.5
        )
        
        score = ranker._calculate_preference_match_score(item, {})
        assert score == 0.5  # Neutral score
    
    def test_ranking_deterministic(self):
        """Test that ranking is deterministic."""
        ranker = IntentRanker(intent_weight=0.5)
        
        context = UserContext(
            user_id="user1",
            intent=Intent(
                intent_type="search",
                keywords=["python"],
                preferences={"category": "tech"},
                priority=0.9
            )
        )
        
        candidates = [
            CandidateItem(item_id="item1", title="Python Guide", base_score=0.6),
            CandidateItem(item_id="item2", title="Java Guide", base_score=0.8),
            CandidateItem(item_id="item3", title="Python Advanced", base_score=0.5),
        ]
        
        # Run ranking multiple times
        results1 = ranker.rank(candidates, context)
        results2 = ranker.rank(candidates, context)
        
        # Results should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.item.item_id == r2.item.item_id
            assert r1.final_score == r2.final_score
            assert r1.intent_score == r2.intent_score
    
    def test_ranking_sorted_by_score(self):
        """Test that results are sorted by final score."""
        ranker = IntentRanker(intent_weight=0.5)
        
        context = UserContext(
            user_id="user1",
            intent=Intent(
                intent_type="search",
                keywords=["python"],
                priority=0.9
            )
        )
        
        candidates = [
            CandidateItem(item_id="item1", title="Java", base_score=0.9),
            CandidateItem(item_id="item2", title="Python ML", base_score=0.8),
            CandidateItem(item_id="item3", title="Python", base_score=0.5),
        ]
        
        results = ranker.rank(candidates, context)
        
        # Verify descending order
        for i in range(len(results) - 1):
            assert results[i].final_score >= results[i + 1].final_score
    
    def test_ranking_with_zero_intent_weight(self):
        """Test ranking with zero intent weight (use only base score)."""
        ranker = IntentRanker(intent_weight=0.0)
        
        context = UserContext(
            user_id="user1",
            intent=Intent(
                intent_type="search",
                keywords=["python"],
                priority=1.0
            )
        )
        
        candidates = [
            CandidateItem(item_id="item1", title="Java", base_score=0.9),
            CandidateItem(item_id="item2", title="Python", base_score=0.5),
        ]
        
        results = ranker.rank(candidates, context)
        
        # With zero intent weight, only base score matters
        assert results[0].item.item_id == "item1"  # Higher base score
        assert results[0].final_score == 0.9
    
    def test_ranking_with_full_intent_weight(self):
        """Test ranking with full intent weight (ignore base score)."""
        ranker = IntentRanker(intent_weight=1.0)
        
        context = UserContext(
            user_id="user1",
            intent=Intent(
                intent_type="search",
                keywords=["python"],
                priority=1.0
            )
        )
        
        candidates = [
            CandidateItem(
                item_id="item1",
                title="Java Guide",
                attributes={"tags": ["java"]},
                base_score=0.9
            ),
            CandidateItem(
                item_id="item2",
                title="Python Guide",
                attributes={"tags": ["python"]},
                base_score=0.3
            ),
        ]
        
        results = ranker.rank(candidates, context)
        
        # With full intent weight, intent score should dominate
        assert results[0].item.item_id == "item2"  # Better intent match
    
    def test_explanation_generation(self):
        """Test that explanations are generated."""
        ranker = IntentRanker()
        
        context = UserContext(
            user_id="user1",
            intent=Intent(
                intent_type="search",
                keywords=["python", "ml"],
                preferences={"category": "tech"},
                priority=0.9
            )
        )
        
        candidates = [
            CandidateItem(
                item_id="item1",
                title="Python Machine Learning",
                attributes={"category": "tech", "tags": ["python", "ml"]},
                base_score=0.8
            ),
        ]
        
        results = ranker.rank(candidates, context)
        
        assert len(results) == 1
        assert results[0].explanation != ""
        assert "python" in results[0].explanation.lower() or "ml" in results[0].explanation.lower()
    
    def test_empty_candidates(self):
        """Test ranking with no candidates."""
        ranker = IntentRanker()
        
        context = UserContext(
            user_id="user1",
            intent=Intent(intent_type="search")
        )
        
        results = ranker.rank([], context)
        assert results == []
    
    def test_single_candidate(self):
        """Test ranking with a single candidate."""
        ranker = IntentRanker()
        
        context = UserContext(
            user_id="user1",
            intent=Intent(intent_type="search", keywords=["python"])
        )
        
        candidates = [
            CandidateItem(item_id="item1", title="Python", base_score=0.7)
        ]
        
        results = ranker.rank(candidates, context)
        assert len(results) == 1
        assert results[0].item.item_id == "item1"
