"""Tests for FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from intent_engine.app import app
from intent_engine.schemas import Item, UserContext


class TestAPI:
    """Test FastAPI endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Intent Engine"
        assert data["status"] == "healthy"
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_rank_endpoint_basic(self):
        """Test basic ranking request."""
        request_data = {
            "items": [
                {
                    "item_id": "item1",
                    "title": "Test Item 1",
                    "category": "electronics",
                    "price": 99.99,
                    "popularity_score": 0.8,
                    "quality_score": 0.85,
                    "attributes": {}
                },
                {
                    "item_id": "item2",
                    "title": "Test Item 2",
                    "category": "electronics",
                    "price": 149.99,
                    "popularity_score": 0.9,
                    "quality_score": 0.95,
                    "attributes": {}
                }
            ],
            "user_context": {
                "user_id": "test_user",
                "preferences": {},
                "history": []
            },
            "intent_text": None,
            "use_llm": False
        }
        
        response = self.client.post("/rank", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "ranked_items" in data
        assert "latency" in data
        assert "intent" in data
        assert len(data["ranked_items"]) == 2
    
    def test_rank_endpoint_with_intent(self):
        """Test ranking with intent text."""
        request_data = {
            "items": [
                {
                    "item_id": "item1",
                    "title": "Test Item",
                    "category": "electronics",
                    "price": 99.99,
                    "popularity_score": 0.8,
                    "quality_score": 0.85,
                    "attributes": {}
                }
            ],
            "user_context": {
                "user_id": "test_user",
                "preferences": {},
                "history": []
            },
            "intent_text": "show me popular items",
            "use_llm": False
        }
        
        response = self.client.post("/rank", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["intent"]["intent_text"] == "show me popular items"
        assert data["intent"]["intent_type"] == "popular"
    
    def test_rank_endpoint_with_preferences(self):
        """Test ranking with user preferences."""
        request_data = {
            "items": [
                {
                    "item_id": "item1",
                    "title": "Test Item",
                    "category": "electronics",
                    "price": 99.99,
                    "popularity_score": 0.8,
                    "quality_score": 0.85,
                    "attributes": {"brand": "Sony"}
                }
            ],
            "user_context": {
                "user_id": "test_user",
                "preferences": {"brand": "Sony"},
                "history": []
            },
            "intent_text": None,
            "use_llm": False
        }
        
        response = self.client.post("/rank", json=request_data)
        assert response.status_code == 200
    
    def test_rank_endpoint_latency_breakdown(self):
        """Test that latency breakdown is returned."""
        request_data = {
            "items": [
                {
                    "item_id": "item1",
                    "title": "Test Item",
                    "category": "electronics",
                    "price": 99.99,
                    "popularity_score": 0.8,
                    "quality_score": 0.85,
                    "attributes": {}
                }
            ],
            "user_context": {
                "user_id": "test_user",
                "preferences": {},
                "history": []
            },
            "intent_text": "test",
            "use_llm": False
        }
        
        response = self.client.post("/rank", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        latency = data["latency"]
        assert "total_ms" in latency
        assert "intent_parsing_ms" in latency
        assert "ranking_ms" in latency
        assert "diversity_check_ms" in latency
        assert latency["total_ms"] > 0
    
    def test_rank_endpoint_invalid_request(self):
        """Test ranking with invalid request."""
        request_data = {
            "items": [],  # Empty items list should fail validation
            "user_context": {
                "user_id": "test_user",
                "preferences": {},
                "history": []
            }
        }
        
        response = self.client.post("/rank", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_rank_endpoint_missing_fields(self):
        """Test ranking with missing required fields."""
        request_data = {
            "items": [
                {
                    "item_id": "item1",
                    "title": "Test Item",
                    "category": "electronics",
                    "price": 99.99
                    # Missing required scores
                }
            ],
            "user_context": {
                "user_id": "test_user"
            }
        }
        
        response = self.client.post("/rank", json=request_data)
        # Should succeed with defaults
        assert response.status_code == 200
