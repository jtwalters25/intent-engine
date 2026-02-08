# Intent Engine

A deterministic intent-based ranking engine for personalized recommendations.

## Features

- **Pydantic Schemas**: Type-safe data models for Intent, UserContext, CandidateItem, and RankedItem
- **Deterministic Ranking**: Re-ranking module that scores items based on user intent as a soft constraint
- **Configurable Weighting**: Adjustable balance between base scores and intent matching
- **Explainable Results**: Human-readable explanations for ranking decisions

## Installation

```bash
pip install -r requirements.txt
```

For development dependencies:

```bash
pip install -r requirements-dev.txt
```

## Quick Start

Run the demo script to see the Intent Engine in action:

```bash
python demo.py
```

This will:
1. Create synthetic user context with search intent
2. Generate candidate items
3. Rank items based on intent matching
4. Display results with explanations for top items

## Usage

### Basic Example

```python
from intent_engine.schemas import Intent, UserContext, CandidateItem
from intent_engine.ranker import IntentRanker

# Create user context with intent
user_context = UserContext(
    user_id="user123",
    intent=Intent(
        intent_type="search",
        keywords=["python", "machine learning"],
        preferences={"category": "technology"},
        priority=0.9
    )
)

# Create candidate items
candidates = [
    CandidateItem(
        item_id="item1",
        title="Machine Learning with Python",
        attributes={"category": "technology", "tags": ["python", "ml"]},
        base_score=0.8
    ),
    # ... more candidates
]

# Initialize ranker and rank items
ranker = IntentRanker(intent_weight=0.5)
ranked_items = ranker.rank(candidates, user_context)

# Access results
for item in ranked_items:
    print(f"{item.item.title}: {item.final_score:.3f}")
    print(f"Explanation: {item.explanation}")
```

### Intent Weight

The `intent_weight` parameter controls the balance between base scores and intent matching:

- `0.0`: Use only base scores (ignore intent)
- `0.5`: Equal weight to base scores and intent scores (default)
- `1.0`: Use only intent scores (ignore base scores)

## Architecture

### Schemas (`intent_engine/schemas.py`)

- **Intent**: User's intent with keywords, preferences, and priority
- **UserContext**: Complete user context including intent and history
- **CandidateItem**: Items to be ranked with attributes and base scores
- **RankedItem**: Ranked results with final scores and explanations

### Ranker (`intent_engine/ranker.py`)

The `IntentRanker` class implements deterministic re-ranking:

1. **Keyword Matching**: Scores items based on intent keyword presence
2. **Preference Matching**: Scores items based on attribute matches
3. **Combined Scoring**: Blends base scores with intent scores
4. **Explanation Generation**: Creates human-readable ranking rationales

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=intent_engine --cov-report=html
```

## Development

The project structure:

```
intent-engine/
├── intent_engine/
│   ├── __init__.py
│   ├── schemas.py      # Pydantic data models
│   └── ranker.py       # Ranking logic
├── tests/
│   ├── test_schemas.py # Schema tests
│   └── test_ranker.py  # Ranker tests
├── demo.py             # Demo script
├── pyproject.toml      # Project configuration
└── requirements.txt    # Dependencies
```

## Design Principles

1. **Correctness**: Type-safe schemas with validation
2. **Clarity**: Clean, well-documented code
3. **Testability**: Comprehensive test coverage
4. **Determinism**: Consistent, reproducible rankings
5. **Explainability**: Transparent scoring with human-readable explanations

## Future Enhancements

- API layer (FastAPI)
- Additional ranking algorithms
- Machine learning integration
- Caching and optimization
- Real-time intent learning

## License

MIT

