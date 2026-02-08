#!/usr/bin/env python3
"""
Demo script for Intent Engine.

This script demonstrates the key features of the Intent Engine:
- Rules-first intent parsing
- Deterministic re-ranking
- Diversity guardrails
- Latency tracking
"""

import json
from intent_engine.schemas import Item, UserContext, RankingRequest
from intent_engine.ranking_engine import RankingEngine


def print_separator():
    """Print a visual separator."""
    print("\n" + "="*80 + "\n")


def demo_basic_ranking():
    """Demonstrate basic ranking without intent."""
    print("DEMO 1: Basic Ranking (No Intent)")
    print("-" * 40)
    
    items = [
        Item(
            item_id="laptop1",
            title="Premium Gaming Laptop",
            category="computers",
            price=1499.99,
            popularity_score=0.85,
            quality_score=0.92,
            attributes={"brand": "ASUS", "ram": "32GB"}
        ),
        Item(
            item_id="laptop2",
            title="Budget Student Laptop",
            category="computers",
            price=499.99,
            popularity_score=0.65,
            quality_score=0.75,
            attributes={"brand": "Acer", "ram": "8GB"}
        ),
        Item(
            item_id="mouse1",
            title="Wireless Gaming Mouse",
            category="accessories",
            price=79.99,
            popularity_score=0.80,
            quality_score=0.85,
            attributes={"brand": "Logitech"}
        ),
    ]
    
    user_context = UserContext(
        user_id="demo_user_1",
        preferences={},
        history=[]
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text=None,
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print(f"Items ranked: {len(response.ranked_items)}")
    print(f"Total latency: {response.latency.total_ms:.2f}ms")
    print("\nTop 3 Results:")
    for ranked_item in response.ranked_items[:3]:
        print(f"  {ranked_item.rank}. {ranked_item.item.title}")
        print(f"     Score: {ranked_item.score:.3f}")
        print(f"     Explanation: {ranked_item.explanation}")


def demo_popular_intent():
    """Demonstrate ranking with popular intent."""
    print("DEMO 2: Popular Intent")
    print("-" * 40)
    
    items = [
        Item(
            item_id="phone1",
            title="Flagship Smartphone",
            category="phones",
            price=999.99,
            popularity_score=0.95,
            quality_score=0.90,
            attributes={"brand": "Apple"}
        ),
        Item(
            item_id="phone2",
            title="Mid-range Phone",
            category="phones",
            price=499.99,
            popularity_score=0.60,
            quality_score=0.80,
            attributes={"brand": "Samsung"}
        ),
        Item(
            item_id="phone3",
            title="Budget Phone",
            category="phones",
            price=299.99,
            popularity_score=0.45,
            quality_score=0.70,
            attributes={"brand": "Motorola"}
        ),
    ]
    
    user_context = UserContext(
        user_id="demo_user_2",
        preferences={},
        history=[]
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text="show me popular trending items",
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print(f"Intent detected: {response.intent.intent_type}")
    print(f"Confidence: {response.intent.confidence:.2f}")
    print(f"Total latency: {response.latency.total_ms:.2f}ms")
    print("\nRanked Results:")
    for ranked_item in response.ranked_items:
        print(f"  {ranked_item.rank}. {ranked_item.item.title}")
        print(f"     Popularity: {ranked_item.item.popularity_score:.2f}")
        print(f"     Score: {ranked_item.score:.3f}")
        print(f"     Explanation: {ranked_item.explanation}")


def demo_budget_constraint():
    """Demonstrate budget constraints."""
    print("DEMO 3: Budget Intent with Price Filter")
    print("-" * 40)
    
    items = [
        Item(
            item_id="headphone1",
            title="Premium Noise-Canceling Headphones",
            category="audio",
            price=349.99,
            popularity_score=0.88,
            quality_score=0.93,
            attributes={"brand": "Sony"}
        ),
        Item(
            item_id="headphone2",
            title="Good Quality Headphones",
            category="audio",
            price=149.99,
            popularity_score=0.75,
            quality_score=0.82,
            attributes={"brand": "Sennheiser"}
        ),
        Item(
            item_id="headphone3",
            title="Basic Headphones",
            category="audio",
            price=49.99,
            popularity_score=0.60,
            quality_score=0.70,
            attributes={"brand": "Generic"}
        ),
    ]
    
    user_context = UserContext(
        user_id="demo_user_3",
        preferences={},
        history=[],
        budget_range=(50.0, 200.0)
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text="find affordable options under $150",
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print(f"Intent: {response.intent.intent_type}")
    print(f"User budget: ${user_context.budget_range[0]}-${user_context.budget_range[1]}")
    print(f"Extracted filters: {response.intent.extracted_filters}")
    print("\nRanked Results:")
    for ranked_item in response.ranked_items:
        in_budget = "✓" if ranked_item.item.price <= 200 else "✗"
        print(f"  {ranked_item.rank}. {ranked_item.item.title}")
        print(f"     Price: ${ranked_item.item.price} {in_budget}")
        print(f"     Score: {ranked_item.score:.3f}")
        print(f"     Explanation: {ranked_item.explanation}")


def demo_user_preferences():
    """Demonstrate user preference matching."""
    print("DEMO 4: User Preference Matching")
    print("-" * 40)
    
    items = [
        Item(
            item_id="tablet1",
            title="iPad Pro",
            category="tablets",
            price=799.99,
            popularity_score=0.90,
            quality_score=0.92,
            attributes={"brand": "Apple", "storage": "256GB"}
        ),
        Item(
            item_id="tablet2",
            title="Galaxy Tab",
            category="tablets",
            price=649.99,
            popularity_score=0.75,
            quality_score=0.85,
            attributes={"brand": "Samsung", "storage": "128GB"}
        ),
        Item(
            item_id="tablet3",
            title="Surface Pro",
            category="tablets",
            price=999.99,
            popularity_score=0.70,
            quality_score=0.88,
            attributes={"brand": "Microsoft", "storage": "512GB"}
        ),
    ]
    
    user_context = UserContext(
        user_id="demo_user_4",
        preferences={"brand": "Apple", "category": "tablets"},
        history=["tablet2"]  # Previously viewed Galaxy Tab
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text=None,
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print(f"User preferences: {user_context.preferences}")
    print(f"User history: {user_context.history}")
    print("\nRanked Results:")
    for ranked_item in response.ranked_items:
        brand_match = "✓" if ranked_item.item.attributes.get("brand") == "Apple" else ""
        history_match = "📖" if ranked_item.item.item_id in user_context.history else ""
        print(f"  {ranked_item.rank}. {ranked_item.item.title} {brand_match}{history_match}")
        print(f"     Brand: {ranked_item.item.attributes.get('brand')}")
        print(f"     Score: {ranked_item.score:.3f}")
        print(f"     Explanation: {ranked_item.explanation}")


def demo_diversity_guardrails():
    """Demonstrate diversity guardrails."""
    print("DEMO 5: Diversity Guardrails")
    print("-" * 40)
    
    # Create many items from same category
    items = []
    for i in range(6):
        items.append(Item(
            item_id=f"laptop{i+1}",
            title=f"Laptop Model {i+1}",
            category="computers",
            price=800.0 + (i * 100),
            popularity_score=0.9 - (i * 0.05),
            quality_score=0.85,
            attributes={"brand": "Various"}
        ))
    
    # Add items from different categories
    items.append(Item(
        item_id="mouse1",
        title="Gaming Mouse",
        category="accessories",
        price=59.99,
        popularity_score=0.70,
        quality_score=0.80,
        attributes={"brand": "Logitech"}
    ))
    
    items.append(Item(
        item_id="monitor1",
        title="4K Monitor",
        category="displays",
        price=499.99,
        popularity_score=0.75,
        quality_score=0.82,
        attributes={"brand": "Dell"}
    ))
    
    user_context = UserContext(
        user_id="demo_user_5",
        preferences={},
        history=[]
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text=None,
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print("Checking for category diversity...")
    print("\nRanked Results:")
    prev_categories = []
    for ranked_item in response.ranked_items:
        category = ranked_item.item.category
        
        # Check diversity rule
        if len(prev_categories) >= 2:
            if prev_categories[-1] == category and prev_categories[-2] == category:
                warning = " ⚠️ DIVERSITY ISSUE"
            else:
                warning = ""
        else:
            warning = ""
        
        print(f"  {ranked_item.rank}. {ranked_item.item.title}")
        print(f"     Category: {category}{warning}")
        
        prev_categories.append(category)


def demo_latency_breakdown():
    """Demonstrate latency breakdown."""
    print("DEMO 6: Latency Breakdown")
    print("-" * 40)
    
    items = [Item(
        item_id=f"item{i}",
        title=f"Product {i}",
        category=f"category{i % 3}",
        price=100.0 * i,
        popularity_score=0.5 + (i * 0.05),
        quality_score=0.6 + (i * 0.04),
        attributes={}
    ) for i in range(20)]
    
    user_context = UserContext(
        user_id="demo_user_6",
        preferences={},
        history=[]
    )
    
    engine = RankingEngine()
    request = RankingRequest(
        items=items,
        user_context=user_context,
        intent_text="show me the best quality premium items",
        use_llm=False
    )
    
    response = engine.rank(request)
    
    print(f"Ranked {len(response.ranked_items)} items")
    print("\nLatency Breakdown:")
    print(f"  Intent Parsing: {response.latency.intent_parsing_ms:.2f}ms")
    print(f"  Ranking:        {response.latency.ranking_ms:.2f}ms")
    print(f"  Diversity:      {response.latency.diversity_check_ms:.2f}ms")
    print(f"  {'─'*40}")
    print(f"  Total:          {response.latency.total_ms:.2f}ms")


def main():
    """Run all demos."""
    print("\n" + "="*80)
    print(" "*20 + "INTENT ENGINE DEMO")
    print("="*80)
    
    demos = [
        demo_basic_ranking,
        demo_popular_intent,
        demo_budget_constraint,
        demo_user_preferences,
        demo_diversity_guardrails,
        demo_latency_breakdown,
    ]
    
    for i, demo in enumerate(demos, 1):
        print_separator()
        demo()
    
    print_separator()
    print("Demo completed! Run the FastAPI server with:")
    print("  python -m intent_engine.app")
    print("\nThen test the API:")
    print("  curl http://localhost:8000/")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
