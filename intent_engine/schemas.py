"""Pydantic schemas for the Intent Engine."""

from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, ConfigDict


class IntentType(str, Enum):
    """Categorized intent types for rules-based classification."""
    POPULAR = "popular"
    BUDGET = "budget"
    PREMIUM = "premium"
    COMPARISON = "comparison"
    TARGETED = "targeted"
    DISCOVERY = "discovery"
    UNKNOWN = "unknown"


class RankingMode(str, Enum):
    """Selects which ranking pipeline to use.

    ADVANCED (default): IntentParser → RankingEngine
        Multi-factor scoring with diversity guardrails. Requires Item fields
        (category, price, popularity_score, quality_score).
    SIMPLE: IntentTranslator → IntentRanker
        Keyword/preference matching with intent_weight blending. Works with
        any CandidateItem. Lighter-weight, no diversity pass.
    """
    SIMPLE = "simple"
    ADVANCED = "advanced"


class Intent(BaseModel):
    """Represents a user's intent with specific goals and preferences."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_type": "search",
                "keywords": ["python", "machine learning"],
                "preferences": {"category": "technology", "difficulty": "intermediate"},
                "priority": 0.8
            }
        }
    )
    
    intent_type: str = Field(..., description="Type of intent (e.g., 'browse', 'search', 'discover')")
    keywords: List[str] = Field(default_factory=list, description="Keywords associated with the intent")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences as key-value pairs")
    priority: float = Field(default=1.0, ge=0.0, le=1.0, description="Priority weight for this intent (0.0-1.0)")
    # Extended fields for intent_parser.py compatibility (all optional, safe defaults)
    intent_text: Optional[str] = Field(default=None, description="Original text that was parsed into this intent")
    extracted_filters: Dict[str, Any] = Field(default_factory=dict, description="Filters extracted from intent text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in the intent classification")
    use_llm: bool = Field(default=False, description="Whether LLM was used for intent parsing")


class UserContext(BaseModel):
    """Represents the user's context including their intent and profile."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user123",
                "intent": {
                    "intent_type": "search",
                    "keywords": ["python"],
                    "preferences": {"category": "technology"},
                    "priority": 0.9
                },
                "history": ["item1", "item2"],
                "metadata": {"location": "US", "device": "mobile"}
            }
        }
    )
    
    user_id: str = Field(..., description="Unique user identifier")
    intent: Intent = Field(
        default_factory=lambda: Intent(intent_type="browse"),
        description="User's current intent",
    )
    history: List[str] = Field(default_factory=list, description="List of previously interacted item IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")
    # Extended fields for ranking_engine.py compatibility
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences for ranking")
    budget_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Min/max budget as (low, high) tuple"
    )


class CandidateItem(BaseModel):
    """Represents a candidate item to be ranked."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "item_id": "item456",
                "title": "Introduction to Python",
                "attributes": {
                    "category": "technology",
                    "tags": ["python", "programming"],
                    "difficulty": "beginner"
                },
                "base_score": 0.75
            }
        }
    )
    
    item_id: str = Field(..., description="Unique item identifier")
    title: str = Field(..., description="Item title")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Item attributes for matching")
    base_score: float = Field(default=0.0, ge=0.0, description="Base score from retrieval or initial ranking")


class Item(CandidateItem):
    """Extended item with pricing and quality/popularity metadata.

    Used by the advanced RankingEngine. Inherits item_id, title,
    attributes, and base_score from CandidateItem.
    """
    category: str = Field(default="", description="Item category for diversity and filtering")
    price: float = Field(default=0.0, ge=0.0, description="Item price")
    popularity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Popularity score (0.0-1.0)")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Quality score (0.0-1.0)")


class RankedItem(BaseModel):
    """Represents a ranked item with scoring details."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "item": {
                    "item_id": "item456",
                    "title": "Introduction to Python",
                    "attributes": {"category": "technology", "tags": ["python"]},
                    "base_score": 0.75
                },
                "final_score": 0.85,
                "intent_score": 0.9,
                "explanation": "Strong match with intent keywords 'python'"
            }
        }
    )
    
    item: CandidateItem = Field(..., description="The candidate item")
    final_score: float = Field(default=0.0, ge=0.0, description="Final computed score after re-ranking")
    intent_score: float = Field(default=0.0, ge=0.0, description="Score based on intent matching")
    explanation: str = Field(default="", description="Human-readable explanation of the ranking")
    explanations: List[str] = Field(
        default_factory=list,
        description="List of 2-3 human-readable explanation lines for this ranking"
    )
    # Extended fields for ranking_engine.py compatibility
    rank: int = Field(default=0, ge=0, description="Rank position (1-based, 0 = unset)")
    score: float = Field(default=0.0, ge=0.0, description="Score from advanced ranking engine")


class LatencyBreakdown(BaseModel):
    """Latency metrics for ranking pipeline stages."""
    total_ms: float = Field(default=0.0, ge=0.0, description="Total processing time in milliseconds")
    intent_parsing_ms: float = Field(default=0.0, ge=0.0, description="Intent parsing time in milliseconds")
    ranking_ms: float = Field(default=0.0, ge=0.0, description="Ranking computation time in milliseconds")
    diversity_check_ms: float = Field(default=0.0, ge=0.0, description="Diversity check time in milliseconds")


class RankingRequest(BaseModel):
    """Request payload for the /rank endpoint."""
    items: List[Item] = Field(..., min_length=1, description="Items to rank (at least one required)")
    user_context: UserContext = Field(..., description="User context including preferences and history")
    intent_text: Optional[str] = Field(default=None, description="Optional free-text intent description")
    use_llm: bool = Field(default=False, description="Whether to use LLM for intent parsing (off by default)")
    mode: RankingMode = Field(
        default=RankingMode.ADVANCED,
        description="Ranking pipeline: 'advanced' (IntentParser+RankingEngine) or 'simple' (IntentTranslator+IntentRanker)",
    )


class RankingResponse(BaseModel):
    """Response payload from the /rank endpoint."""
    ranked_items: List[RankedItem] = Field(default_factory=list, description="Items ranked by relevance")
    latency: LatencyBreakdown = Field(
        default_factory=LatencyBreakdown, description="Latency breakdown by pipeline stage"
    )
    intent: Intent = Field(
        default_factory=lambda: Intent(intent_type="unknown"), description="The parsed intent"
    )
