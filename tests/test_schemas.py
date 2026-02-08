"""Tests for Pydantic schemas."""

import pytest
from intent_engine.schemas import Intent, UserContext, CandidateItem, RankedItem


class TestIntent:
    """Tests for Intent schema."""
    
    def test_intent_creation(self):
        """Test creating a valid intent."""
        intent = Intent(
            intent_type="search",
            keywords=["python", "ml"],
            preferences={"category": "tech"},
            priority=0.8
        )
        assert intent.intent_type == "search"
        assert len(intent.keywords) == 2
        assert intent.preferences["category"] == "tech"
        assert intent.priority == 0.8
    
    def test_intent_defaults(self):
        """Test intent with default values."""
        intent = Intent(intent_type="browse")
        assert intent.keywords == []
        assert intent.preferences == {}
        assert intent.priority == 1.0
    
    def test_intent_priority_validation(self):
        """Test that priority must be between 0 and 1."""
        # Valid priorities
        Intent(intent_type="test", priority=0.0)
        Intent(intent_type="test", priority=0.5)
        Intent(intent_type="test", priority=1.0)
        
        # Invalid priorities should raise validation error
        with pytest.raises(ValueError):
            Intent(intent_type="test", priority=-0.1)
        
        with pytest.raises(ValueError):
            Intent(intent_type="test", priority=1.5)


class TestUserContext:
    """Tests for UserContext schema."""
    
    def test_user_context_creation(self):
        """Test creating a valid user context."""
        intent = Intent(intent_type="search", keywords=["python"])
        context = UserContext(
            user_id="user123",
            intent=intent,
            history=["item1", "item2"],
            metadata={"device": "mobile"}
        )
        assert context.user_id == "user123"
        assert context.intent.intent_type == "search"
        assert len(context.history) == 2
        assert context.metadata["device"] == "mobile"
    
    def test_user_context_defaults(self):
        """Test user context with default values."""
        intent = Intent(intent_type="browse")
        context = UserContext(user_id="user456", intent=intent)
        assert context.history == []
        assert context.metadata == {}


class TestCandidateItem:
    """Tests for CandidateItem schema."""
    
    def test_candidate_item_creation(self):
        """Test creating a valid candidate item."""
        item = CandidateItem(
            item_id="item789",
            title="Python Tutorial",
            attributes={"tags": ["python"], "category": "tech"},
            base_score=0.75
        )
        assert item.item_id == "item789"
        assert item.title == "Python Tutorial"
        assert item.attributes["category"] == "tech"
        assert item.base_score == 0.75
    
    def test_candidate_item_defaults(self):
        """Test candidate item with default values."""
        item = CandidateItem(item_id="item999", title="Test Item")
        assert item.attributes == {}
        assert item.base_score == 0.0
    
    def test_candidate_item_base_score_validation(self):
        """Test that base_score must be non-negative."""
        # Valid scores
        CandidateItem(item_id="test", title="Test", base_score=0.0)
        CandidateItem(item_id="test", title="Test", base_score=1.0)
        
        # Invalid score should raise validation error
        with pytest.raises(ValueError):
            CandidateItem(item_id="test", title="Test", base_score=-0.1)


class TestRankedItem:
    """Tests for RankedItem schema."""
    
    def test_ranked_item_creation(self):
        """Test creating a valid ranked item."""
        item = CandidateItem(
            item_id="item100",
            title="Test",
            base_score=0.5
        )
        ranked = RankedItem(
            item=item,
            final_score=0.75,
            intent_score=0.8,
            explanation="Strong match"
        )
        assert ranked.item.item_id == "item100"
        assert ranked.final_score == 0.75
        assert ranked.intent_score == 0.8
        assert ranked.explanation == "Strong match"
    
    def test_ranked_item_default_explanation(self):
        """Test ranked item with default explanation."""
        item = CandidateItem(item_id="test", title="Test")
        ranked = RankedItem(
            item=item,
            final_score=0.5,
            intent_score=0.6
        )
        assert ranked.explanation == ""
    
    def test_ranked_item_score_validation(self):
        """Test that scores must be non-negative."""
        item = CandidateItem(item_id="test", title="Test")
        
        # Valid scores
        RankedItem(item=item, final_score=0.0, intent_score=0.0)
        RankedItem(item=item, final_score=1.0, intent_score=1.0)
        
        # Invalid scores should raise validation error
        with pytest.raises(ValueError):
            RankedItem(item=item, final_score=-0.1, intent_score=0.5)
        
        with pytest.raises(ValueError):
            RankedItem(item=item, final_score=0.5, intent_score=-0.1)
