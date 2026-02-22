"""Tests for intent parser."""

import pytest
from intent_engine.intent_parser import IntentParser
from intent_engine.schemas import IntentType


class TestIntentParser:
    """Test intent parser functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IntentParser()
    
    def test_parse_discovery_intent(self):
        """Test discovery intent classification."""
        intent = self.parser.parse("show me something new")
        assert intent.intent_type == IntentType.DISCOVERY
        assert intent.confidence > 0.5
        assert intent.intent_text == "show me something new"
    
    def test_parse_popular_intent(self):
        """Test popular intent classification."""
        intent = self.parser.parse("show me popular items")
        assert intent.intent_type == IntentType.POPULAR
        assert intent.confidence > 0.5
    
    def test_parse_budget_intent(self):
        """Test budget intent classification."""
        intent = self.parser.parse("looking for cheap options")
        assert intent.intent_type == IntentType.BUDGET
        assert intent.confidence > 0.5
    
    def test_parse_premium_intent(self):
        """Test premium intent classification."""
        intent = self.parser.parse("show me premium quality items")
        assert intent.intent_type == IntentType.PREMIUM
        assert intent.confidence > 0.5
    
    def test_parse_comparison_intent(self):
        """Test comparison intent classification."""
        intent = self.parser.parse("compare the best options")
        assert intent.intent_type == IntentType.COMPARISON
        assert intent.confidence > 0.5
    
    def test_parse_targeted_intent(self):
        """Test targeted intent classification."""
        intent = self.parser.parse("find something specific")
        assert intent.intent_type == IntentType.TARGETED
        assert intent.confidence > 0.5
    
    def test_parse_no_intent(self):
        """Test parsing when no intent text provided."""
        intent = self.parser.parse(None)
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0
        assert intent.intent_text is None
    
    def test_parse_empty_intent(self):
        """Test parsing empty string."""
        intent = self.parser.parse("")
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0
    
    def test_extract_price_max_filter(self):
        """Test extraction of maximum price filter."""
        intent = self.parser.parse("find items under $100")
        assert "price_max" in intent.extracted_filters
        assert intent.extracted_filters["price_max"] == 100.0
    
    def test_extract_price_min_filter(self):
        """Test extraction of minimum price filter."""
        intent = self.parser.parse("find items over $50")
        assert "price_min" in intent.extracted_filters
        assert intent.extracted_filters["price_min"] == 50.0
    
    def test_extract_category_filter(self):
        """Test extraction of category filter."""
        intent = self.parser.parse("show me items in electronics")
        assert "category" in intent.extracted_filters
        assert intent.extracted_filters["category"].lower() == "electronics"
    
    def test_extract_brand_filter(self):
        """Test extraction of brand filter."""
        intent = self.parser.parse("show me items from Apple")
        assert "brand" in intent.extracted_filters
        assert intent.extracted_filters["brand"].lower() == "apple"
    
    def test_multiple_keywords_high_confidence(self):
        """Test that multiple keyword matches increase confidence."""
        intent = self.parser.parse("discover and explore new trending items")
        assert intent.confidence >= 0.8
    
    def test_llm_flag_preserved(self):
        """Test that use_llm flag is preserved in result."""
        intent = self.parser.parse("test", use_llm=True)
        assert intent.use_llm is True
        
        intent = self.parser.parse("test", use_llm=False)
        assert intent.use_llm is False
    
    def test_llm_fallback(self, monkeypatch):
        """Test that LLMAdapter fallback occurs when LLM output is invalid or unavailable."""
        from intent_engine.intent_parser import IntentParser
        parser = IntentParser()
        monkeypatch.setenv("LLM_ENABLED", "1")
        # Patch LLMAdapter to return invalid output
        parser._llm_adapter._call_llm = lambda prompt: None
        intent = parser.parse("premium tech", use_llm=True)
        assert intent.intent_type != "llm", "Fallback to rules should occur when LLM output is invalid"
