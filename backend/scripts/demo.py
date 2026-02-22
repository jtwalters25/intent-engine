"""Demo script for the Intent Engine."""

from intent_engine.schemas import Intent, UserContext, CandidateItem
from intent_engine.simple_ranker import IntentRanker


def create_synthetic_data():
    """Create synthetic user context and candidate items for demonstration."""
    
    # Create user context with intent
    user_context = UserContext(
        user_id="demo_user_001",
        intent=Intent(
            intent_type="search",
            keywords=["python", "machine learning"],
            preferences={
                "category": "technology",
                "difficulty": "intermediate"
            },
            priority=0.9
        ),
        history=["item_101", "item_102"],
        metadata={"location": "US", "device": "desktop"}
    )
    
    # Create candidate items
    candidates = [
        CandidateItem(
            item_id="item_201",
            title="Introduction to Python Programming",
            attributes={
                "category": "technology",
                "tags": ["python", "programming", "beginner"],
                "difficulty": "beginner",
                "rating": 4.5
            },
            base_score=0.75
        ),
        CandidateItem(
            item_id="item_202",
            title="Machine Learning with Python",
            attributes={
                "category": "technology",
                "tags": ["python", "machine learning", "data science"],
                "difficulty": "intermediate",
                "rating": 4.8
            },
            base_score=0.82
        ),
        CandidateItem(
            item_id="item_203",
            title="Advanced JavaScript Techniques",
            attributes={
                "category": "technology",
                "tags": ["javascript", "web development", "advanced"],
                "difficulty": "advanced",
                "rating": 4.3
            },
            base_score=0.68
        ),
        CandidateItem(
            item_id="item_204",
            title="Deep Learning Fundamentals",
            attributes={
                "category": "technology",
                "tags": ["machine learning", "deep learning", "neural networks"],
                "difficulty": "intermediate",
                "rating": 4.7
            },
            base_score=0.79
        ),
        CandidateItem(
            item_id="item_205",
            title="Python for Data Analysis",
            attributes={
                "category": "technology",
                "tags": ["python", "data analysis", "pandas"],
                "difficulty": "intermediate",
                "rating": 4.6
            },
            base_score=0.71
        ),
        CandidateItem(
            item_id="item_206",
            title="Web Design Basics",
            attributes={
                "category": "design",
                "tags": ["web design", "css", "html"],
                "difficulty": "beginner",
                "rating": 4.2
            },
            base_score=0.65
        ),
    ]
    
    return user_context, candidates


def print_divider():
    """Print a visual divider."""
    print("\n" + "=" * 80 + "\n")


def main():
    """Run the demo."""
    print("Intent Engine Demo")
    print_divider()
    
    # Create synthetic data
    user_context, candidates = create_synthetic_data()
    
    # Display user context
    print("USER CONTEXT")
    print(f"User ID: {user_context.user_id}")
    print(f"Intent Type: {user_context.intent.intent_type}")
    print(f"Keywords: {', '.join(user_context.intent.keywords)}")
    print(f"Preferences: {user_context.intent.preferences}")
    print(f"Priority: {user_context.intent.priority}")
    print_divider()
    
    # Display candidate items
    print("CANDIDATE ITEMS")
    for i, item in enumerate(candidates, 1):
        print(f"{i}. {item.title} (ID: {item.item_id})")
        print(f"   Base Score: {item.base_score:.3f}")
        print(f"   Attributes: {item.attributes}")
    print_divider()
    
    # Initialize ranker with 50/50 weight between base score and intent score
    ranker = IntentRanker(intent_weight=0.5)
    
    # Rank items
    ranked_items = ranker.rank(candidates, user_context)
    
    # Display ranked results
    print("RANKED RESULTS")
    print("(Sorted by final score, showing top results with explanations)\n")
    
    for i, ranked_item in enumerate(ranked_items, 1):
        item = ranked_item.item
        print(f"{i}. {item.title}")
        print(f"   Item ID: {item.item_id}")
        print(f"   Final Score: {ranked_item.final_score:.3f}")
        print(f"   Intent Score: {ranked_item.intent_score:.3f}")
        print(f"   Base Score: {item.base_score:.3f}")
        
        # Show detailed explanation for top 3 items
        if i <= 3:
            print(f"   📝 Explanation: {ranked_item.explanation}")
        print()
    
    print_divider()
    
    # Show summary statistics
    print("SUMMARY")
    print(f"Total items ranked: {len(ranked_items)}")
    print(f"Intent weight: {ranker.intent_weight}")
    print(f"Top ranked item: {ranked_items[0].item.title}")
    print(f"Top score: {ranked_items[0].final_score:.3f}")
    print_divider()


if __name__ == "__main__":
    main()
