"""Core schemas for the Intent Engine."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class IntentType(str, Enum):
    """Predefined intent types for rules-first translation."""
    DISCOVERY = "discovery"
    TARGETED = "targeted"
    COMPARISON = "comparison"
    BUDGET = "budget"
    PREMIUM = "premium"
    POPULAR = "popular"
    UNKNOWN = "unknown"


class UserContext(BaseModel):
    """User context for personalization."""
    user_id: str = Field(..., description="Unique user identifier")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    history: List[str] = Field(default_factory=list, description="User interaction history (item IDs)")
    budget_range: Optional[tuple[float, float]] = Field(None, description="Budget range (min, max)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "preferences": {"category": "electronics", "brand": "apple"},
                "history": ["item1", "item2"],
                "budget_range": [100.0, 500.0]
            }
        }


class Intent(BaseModel):
    """Parsed intent from user input."""
    intent_type: IntentType = Field(default=IntentType.UNKNOWN, description="Classified intent type")
    intent_text: Optional[str] = Field(None, description="Original intent text from user")
    extracted_filters: Dict[str, Any] = Field(default_factory=dict, description="Filters extracted from intent")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in intent classification")
    use_llm: bool = Field(default=False, description="Whether to use LLM for intent parsing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "intent_type": "discovery",
                "intent_text": "show me something new",
                "extracted_filters": {},
                "confidence": 0.9,
                "use_llm": False
            }
        }


class Item(BaseModel):
    """Item to be ranked."""
    item_id: str = Field(..., description="Unique item identifier")
    title: str = Field(..., description="Item title")
    category: str = Field(..., description="Item category")
    price: float = Field(..., ge=0, description="Item price")
    popularity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Popularity score (0-1)")
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Quality score (0-1)")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional item attributes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "item123",
                "title": "Wireless Headphones",
                "category": "electronics",
                "price": 199.99,
                "popularity_score": 0.85,
                "quality_score": 0.9,
                "attributes": {"brand": "Sony", "color": "black"}
            }
        }


class RankedItem(BaseModel):
    """Item with ranking information."""
    item: Item = Field(..., description="The item")
    rank: int = Field(..., ge=1, description="Rank position (1-indexed)")
    score: float = Field(..., description="Final ranking score")
    explanation: str = Field(..., description="Explanation for ranking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "item": {
                    "item_id": "item123",
                    "title": "Wireless Headphones",
                    "category": "electronics",
                    "price": 199.99,
                    "popularity_score": 0.85,
                    "quality_score": 0.9,
                    "attributes": {}
                },
                "rank": 1,
                "score": 0.95,
                "explanation": "High quality and popular item matching user preferences"
            }
        }


class RankingRequest(BaseModel):
    """Request for ranking items."""
    items: List[Item] = Field(..., min_length=1, description="Items to rank")
    user_context: UserContext = Field(..., description="User context")
    intent_text: Optional[str] = Field(None, description="Optional intent text")
    use_llm: bool = Field(default=False, description="Enable LLM for intent parsing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "item_id": "item1",
                        "title": "Product 1",
                        "category": "electronics",
                        "price": 99.99,
                        "popularity_score": 0.8,
                        "quality_score": 0.85
                    }
                ],
                "user_context": {
                    "user_id": "user123",
                    "preferences": {},
                    "history": []
                },
                "intent_text": "show me popular items",
                "use_llm": False
            }
        }


class LatencyBreakdown(BaseModel):
    """Latency breakdown for performance monitoring."""
    total_ms: float = Field(..., description="Total processing time in milliseconds")
    intent_parsing_ms: float = Field(..., description="Intent parsing time")
    ranking_ms: float = Field(..., description="Ranking computation time")
    diversity_check_ms: float = Field(..., description="Diversity check time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_ms": 45.2,
                "intent_parsing_ms": 10.5,
                "ranking_ms": 30.1,
                "diversity_check_ms": 4.6
            }
        }


class RankingResponse(BaseModel):
    """Response with ranked items."""
    ranked_items: List[RankedItem] = Field(..., description="Ranked items with explanations")
    latency: LatencyBreakdown = Field(..., description="Latency breakdown")
    intent: Intent = Field(..., description="Parsed intent")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ranked_items": [],
                "latency": {
                    "total_ms": 45.2,
                    "intent_parsing_ms": 10.5,
                    "ranking_ms": 30.1,
                    "diversity_check_ms": 4.6
                },
                "intent": {
                    "intent_type": "discovery",
                    "intent_text": None,
                    "extracted_filters": {},
                    "confidence": 0.0,
                    "use_llm": False
                }
            }
        }
