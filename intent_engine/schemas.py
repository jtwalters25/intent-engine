"""Pydantic schemas for the Intent Engine."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


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
    intent: Intent = Field(..., description="User's current intent")
    history: List[str] = Field(default_factory=list, description="List of previously interacted item IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")


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
    final_score: float = Field(..., ge=0.0, description="Final computed score after re-ranking")
    intent_score: float = Field(..., ge=0.0, description="Score based on intent matching")
    explanation: str = Field(default="", description="Human-readable explanation of the ranking")
