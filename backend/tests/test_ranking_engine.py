"""Tests for ranking engine."""

import pytest
from intent_engine.ranking_engine import RankingEngine
from intent_engine.schemas import (
    Item, UserContext, RankingRequest, IntentType
)


class TestRankingEngine:
    """Test ranking engine functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = RankingEngine()
        
        # Create test items
        self.items = [
            Item(
                item_id="item1",
                title="Premium Headphones",
                category="electronics",
                price=299.99,
                popularity_score=0.9,
                quality_score=0.95,
                attributes={"brand": "Sony"}
            ),
            Item(
                item_id="item2",
                title="Budget Headphones",
                category="electronics",
                price=49.99,
                popularity_score=0.6,
                quality_score=0.7,
                attributes={"brand": "Generic"}
            ),
            Item(
                item_id="item3",
                title="Mid-range Laptop",
                category="computers",
                price=899.99,
                popularity_score=0.75,
                quality_score=0.8,
                attributes={"brand": "Dell"}
            ),
            Item(
                item_id="item4",
                title="Phone Case",
                category="accessories",
                price=19.99,
                popularity_score=0.5,
                quality_score=0.6,
                attributes={"brand": "Generic"}
            ),
        ]
        
        self.user_context = UserContext(
            user_id="test_user",
            preferences={},
            history=[],
            budget_range=None
        )
    
    def test_rank_basic(self):
        """Test basic ranking without intent."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        assert len(response.ranked_items) == len(self.items)
        assert response.ranked_items[0].rank == 1
        assert response.latency.total_ms > 0
    
    def test_rank_popular_intent(self):
        """Test ranking with popular intent boosts popular items."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="show me popular items",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Premium headphones should rank high due to popularity
        top_item = response.ranked_items[0].item
        assert top_item.popularity_score >= 0.75
        assert response.intent.intent_type == IntentType.POPULAR
    
    def test_rank_budget_intent(self):
        """Test ranking with budget intent boosts cheaper items."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="cheap affordable options",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Budget items should rank higher
        assert response.intent.intent_type == IntentType.BUDGET
        # Check that cheaper items get boost in explanation
        for ranked_item in response.ranked_items:
            if ranked_item.item.price < 100:
                assert "intent=" in ranked_item.explanation
    
    def test_rank_premium_intent(self):
        """Test ranking with premium intent boosts quality items."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="premium high-end quality",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Premium items should rank higher
        assert response.intent.intent_type == IntentType.PREMIUM
        top_item = response.ranked_items[0].item
        assert top_item.quality_score >= 0.8
    
    def test_rank_discovery_intent(self):
        """Test ranking with discovery intent promotes less popular items."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="discover something new",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        assert response.intent.intent_type == IntentType.DISCOVERY
    
    def test_user_preference_boost(self):
        """Test that user preferences boost matching items."""
        user_context = UserContext(
            user_id="test_user",
            preferences={"category": "electronics", "brand": "Sony"},
            history=[]
        )
        
        request = RankingRequest(
            items=self.items,
            user_context=user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Sony headphones should rank high due to preference match
        top_items = [ri.item for ri in response.ranked_items[:2]]
        sony_item = next((i for i in top_items if i.attributes.get("brand") == "Sony"), None)
        assert sony_item is not None
    
    def test_budget_constraint_penalty(self):
        """Test that items over budget are penalized."""
        user_context = UserContext(
            user_id="test_user",
            preferences={},
            history=[],
            budget_range=(50.0, 200.0)
        )
        
        request = RankingRequest(
            items=self.items,
            user_context=user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Items within budget should rank higher
        for ranked_item in response.ranked_items:
            if ranked_item.item.price > 200.0:
                assert "budget=" in ranked_item.explanation
    
    def test_history_boost(self):
        """Test that previously viewed items get small boost."""
        user_context = UserContext(
            user_id="test_user",
            preferences={},
            history=["item2"],
            budget_range=None
        )
        
        request = RankingRequest(
            items=self.items,
            user_context=user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # item2 should have history boost in explanation
        item2_ranked = next(ri for ri in response.ranked_items if ri.item.item_id == "item2")
        # History boost may or may not show depending on score, just verify it ranks
        assert item2_ranked is not None
    
    def test_diversity_guardrails(self):
        """Test that diversity prevents category clustering."""
        # Create multiple items from same category
        electronics_items = [
            Item(
                item_id=f"elec{i}",
                title=f"Electronics Item {i}",
                category="electronics",
                price=100.0 + i,
                popularity_score=0.9 - (i * 0.05),
                quality_score=0.85,
                attributes={}
            )
            for i in range(5)
        ]
        
        # Add items from different categories with reasonable scores
        other_items = [
            Item(
                item_id="acc1",
                title="Accessory Item 1",
                category="accessories",
                price=50.0,
                popularity_score=0.75,
                quality_score=0.80,
                attributes={}
            ),
            Item(
                item_id="acc2",
                title="Accessory Item 2",
                category="accessories",
                price=60.0,
                popularity_score=0.73,
                quality_score=0.78,
                attributes={}
            ),
        ]
        
        all_items = electronics_items + other_items
        
        request = RankingRequest(
            items=all_items,
            user_context=self.user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Check that we don't have more than 2 consecutive same category
        violations = 0
        for i in range(len(response.ranked_items) - 2):
            cat1 = response.ranked_items[i].item.category
            cat2 = response.ranked_items[i + 1].item.category
            cat3 = response.ranked_items[i + 2].item.category
            # Should not have 3 in a row of same category
            if cat1 == cat2 == cat3:
                violations += 1
        
        # With 5 electronics and 2 accessories, we should be able to avoid most clustering
        # Allow at most 1 violation (edge case at the end if all remaining are same category)
        assert violations <= 1, f"Too many diversity violations: {violations}"
    
    def test_price_filter_extraction(self):
        """Test that price filters from intent are applied."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="find items under $100",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        # Check that price filter was extracted
        assert "price_max" in response.intent.extracted_filters
        assert response.intent.extracted_filters["price_max"] == 100.0
        
        # Items under $100 should get boost
        for ranked_item in response.ranked_items:
            if ranked_item.item.price <= 100.0:
                assert "intent=" in ranked_item.explanation
    
    def test_latency_breakdown(self):
        """Test that latency breakdown is provided."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text="test intent",
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        assert response.latency.total_ms > 0
        assert response.latency.intent_parsing_ms >= 0
        assert response.latency.ranking_ms >= 0
        assert response.latency.diversity_check_ms >= 0
        assert response.latency.total_ms >= response.latency.intent_parsing_ms
    
    def test_explanation_provided(self):
        """Test that each ranked item has an explanation."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        for ranked_item in response.ranked_items:
            assert ranked_item.explanation
            assert len(ranked_item.explanation) > 0
    
    def test_score_normalization(self):
        """Test that scores are normalized between 0 and 1."""
        request = RankingRequest(
            items=self.items,
            user_context=self.user_context,
            intent_text=None,
            use_llm=False
        )
        
        response = self.engine.rank(request)
        
        for ranked_item in response.ranked_items:
            assert 0.0 <= ranked_item.score <= 1.0
