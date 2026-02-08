"""
Quick Start Example for Intent Engine
======================================

This example shows how to use the Intent Engine both programmatically
and via the REST API.
"""

# Example 1: Using the ranking engine directly
from intent_engine.schemas import Item, UserContext, RankingRequest
from intent_engine.ranking_engine import RankingEngine

def example_direct_usage():
    """Example of using the ranking engine directly in Python."""
    
    # Create some items
    items = [
        Item(
            item_id="laptop1",
            title="Gaming Laptop",
            category="computers",
            price=1299.99,
            popularity_score=0.85,
            quality_score=0.90,
            attributes={"brand": "ASUS", "ram": "16GB"}
        ),
        Item(
            item_id="laptop2",
            title="Business Laptop",
            category="computers",
            price=899.99,
            popularity_score=0.75,
            quality_score=0.85,
            attributes={"brand": "Dell", "ram": "8GB"}
        ),
    ]
    
    # Define user context
    user_context = UserContext(
        user_id="user456",
        preferences={"category": "computers"},
        history=[],
        budget_range=(500.0, 1500.0)
    )
    
    # Create ranking request
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text="find high quality laptops",
        use_llm=False
    )
    
    # Rank items
    engine = RankingEngine()
    response = engine.rank(request)
    
    # Display results
    print(f"Intent detected: {response.intent.intent_type}")
    print(f"Total latency: {response.latency.total_ms:.2f}ms\n")
    
    for ranked_item in response.ranked_items:
        print(f"{ranked_item.rank}. {ranked_item.item.title}")
        print(f"   Score: {ranked_item.score:.3f}")
        print(f"   Explanation: {ranked_item.explanation}\n")


# Example 2: Using the REST API with curl
API_EXAMPLE = """
# Start the server
python -m intent_engine.app

# Make a ranking request
curl -X POST "http://localhost:8000/rank" \\
  -H "Content-Type: application/json" \\
  -d '{
    "items": [
      {
        "item_id": "item1",
        "title": "Product 1",
        "category": "electronics",
        "price": 99.99,
        "popularity_score": 0.8,
        "quality_score": 0.85,
        "attributes": {}
      }
    ],
    "user_context": {
      "user_id": "user123",
      "preferences": {},
      "history": []
    },
    "intent_text": "show me popular items",
    "use_llm": false
  }'
"""


# Example 3: Using the API with Python requests
def example_api_usage():
    """Example of using the Intent Engine REST API with Python."""
    import requests
    
    url = "http://localhost:8000/rank"
    
    payload = {
        "items": [
            {
                "item_id": "phone1",
                "title": "Flagship Phone",
                "category": "phones",
                "price": 999.99,
                "popularity_score": 0.95,
                "quality_score": 0.92,
                "attributes": {"brand": "Apple"}
            },
            {
                "item_id": "phone2",
                "title": "Budget Phone",
                "category": "phones",
                "price": 299.99,
                "popularity_score": 0.65,
                "quality_score": 0.75,
                "attributes": {"brand": "Motorola"}
            }
        ],
        "user_context": {
            "user_id": "user789",
            "preferences": {"brand": "Apple"},
            "history": []
        },
        "intent_text": "find premium quality phones",
        "use_llm": False
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    print("Ranked Items:")
    for item in result["ranked_items"]:
        print(f"  {item['rank']}. {item['item']['title']} (score: {item['score']:.3f})")
    
    print(f"\nLatency: {result['latency']['total_ms']:.2f}ms")
    print(f"Intent: {result['intent']['intent_type']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Intent Engine - Quick Start Examples")
    print("=" * 60)
    
    print("\nExample 1: Direct Python Usage")
    print("-" * 60)
    example_direct_usage()
    
    print("\n" + "=" * 60)
    print("\nExample 2: Using the REST API (curl)")
    print("-" * 60)
    print(API_EXAMPLE)
    
    print("\n" + "=" * 60)
    print("\nExample 3: Using the REST API (Python)")
    print("-" * 60)
    print("# First, start the server in another terminal:")
    print("#   python -m intent_engine.app")
    print("#")
    print("# Then uncomment and run:")
    print("# example_api_usage()")
