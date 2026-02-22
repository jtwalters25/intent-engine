# Intent Engine

A company-agnostic, deterministic intent-based re-ranking engine. Schemas + rules-first intent translation + soft-constraint re-ranking + human-readable explanations. **Not** a full recommender system — it sits between retrieval and presentation.

## TL;DR / 60-second read

Intent Engine is a deterministic, rules-first re-ranking layer for content catalogs. It translates user input into intent, then re-ranks items with soft constraints—never filters. LLM is optional and OFF by default; ranking is always deterministic. Two modes: simple (rules-only) and advanced (multi-factor, shallow, explainable). No ML, no personalization, no randomness.

## Ranking Modes

The `/rank` endpoint accepts a `mode` field (`"simple"` or `"advanced"`).

### Simple mode (`mode: "simple"`)

```
User input (text + time context)
        │
        ▼
┌──────────────────┐
│ IntentTranslator  │  keyword mapping, time_bucket inference, safe defaults
│(rules_translator) │  rules-first — no LLM required
└──────┬───────────┘
       │ Intent (keywords, preferences, priority)
       ▼
┌──────────────────┐
│  IntentRanker     │  deterministic re-ranking via intent_weight blending
│ (simple_ranker)   │  intent is a SOFT constraint — all items survive
└──────┬───────────┘
       │ List[RankedItem] (score + 2-3 explanation lines)
       ▼
    Presentation
```

Lightweight keyword/preference matching. Works with any `CandidateItem`. No diversity pass.

### Advanced mode (`mode: "advanced"`, default)

```
User input (free text)
        │
        ▼
┌──────────────────┐
│  IntentParser     │  rules-based classification + optional LLM fallback
│ (intent_parser.py)│  confidence scoring + filter extraction
└──────┬───────────┘
       │ Intent (type, filters, confidence)
       ▼
┌──────────────────┐
│  RankingEngine    │  multi-factor scoring + diversity guardrails
│ (ranking_engine.py)│  budget constraints + history boosts + latency tracking
└──────┬───────────┘
       │ RankingResponse (ranked items + latency breakdown)
       ▼
    Presentation
```

Multi-factor scoring with diversity guardrails. Requires `Item` fields (category, price, popularity_score, quality_score).

## Features

- **Pydantic Schemas** — type-safe models for intent, items, ranking requests/responses
- **Rules-First Intent Translation** — keyword mapping, time inference, safe defaults
- **Rules-Based Intent Parsing** — classifies free text into intent types with confidence scoring and filter extraction
- **Soft-Constraint Re-Ranking** — intent boosts matching items but never filters non-matching ones; blend controlled by intent_weight
- **Advanced Ranking Engine** — shallow multi-factor scoring; intelligence comes from composition, not complexity; no single factor dominates without intent_weight
- **Structured Explanations** — concise, human-readable lines per ranked item
- **FastAPI REST API** — schema-validated endpoints for ranking
- **Deterministic** — same input always produces same output, no randomness
- **Two Ranking Modes** — simple (rules-only) and advanced (multi-factor), selectable per request
- **LLM-Free by Default** — LLM adapter exists but is OFF unless enabled; LLM translates language only, never scores or ranks; any LLM failure falls back to rules deterministically

## Installation

```bash
pip install -r requirements.txt
```

For development (adds pytest):

```bash
pip install -r requirements-dev.txt
```

## Quick Start

### 3-Scenario Demo (recommended)

```bash
python -m scripts.demo_runner
```

Runs three scenarios through the full pipeline using a synthetic 12-item children's content catalog:

1. **Bedtime Calm** — evening wind-down content at 8 PM
2. **Afterschool STEM** — educational science/math after school at 4 PM
3. **Weekend Fun** — energetic family adventure on a Saturday

### Basic Demo

```bash
python -m scripts.demo
```

Single scenario with a tech/Python catalog.

## Usage

### With the Translator (full pipeline)

```python
from intent_engine.rules_translator import IntentTranslator
from intent_engine.simple_ranker import IntentRanker
from intent_engine.schemas import UserContext, CandidateItem

# Step 1: Translate scenario text + time context into an Intent
translator = IntentTranslator()
intent = translator.translate("bedtime calm", hour=20, day_of_week="tuesday")

# Step 2: Build UserContext
context = UserContext(user_id="user_001", intent=intent)

# Step 3: Rank candidates (all items survive — soft constraint)
ranker = IntentRanker(intent_weight=0.6)
ranked = ranker.rank(candidates, context)

# Step 4: Read results
for r in ranked:
    print(f"{r.item.title}: {r.final_score:.3f}")
    for line in r.explanations:
        print(f"  - {line}")
```

### Without the Translator (manual Intent)

```python
from intent_engine.schemas import Intent, UserContext
from intent_engine.simple_ranker import IntentRanker

context = UserContext(
    user_id="user123",
    intent=Intent(
        intent_type="search",
        keywords=["python", "machine learning"],
        preferences={"category": "technology"},
        priority=0.9,
    ),
)

ranker = IntentRanker(intent_weight=0.5)
ranked = ranker.rank(candidates, context)
```

### Intent Weight

Controls the blend between base scores and intent scores:

| Value | Behavior |
|-------|----------|
| `0.0` | Use only base scores (ignore intent) |
| `0.5` | Equal weight (default) |
| `1.0` | Use only intent scores (ignore base scores) |

Formula: `final_score = (1 - intent_weight) * base_score + intent_weight * intent_score`

## Architecture

### Schemas (`intent_engine/schemas.py`)

| Model | Purpose |
|-------|---------|
| `IntentType` | Enum: popular, budget, premium, comparison, targeted, discovery, unknown |
| `Intent` | Keywords, preferences, priority, plus optional intent_text/extracted_filters/confidence/use_llm |
| `UserContext` | User ID + Intent + history + metadata + preferences + budget_range |
| `CandidateItem` | Item ID, title, attributes dict, base_score |
| `Item` | Extends CandidateItem with category, price, popularity_score, quality_score |
| `RankedItem` | Wrapped item + final_score + intent_score + explanation + explanations + rank + score |
| `LatencyBreakdown` | Timing for each pipeline stage (intent parsing, ranking, diversity check) |
| `RankingMode` | Enum: simple, advanced |
| `RankingRequest` | Items + user context + mode + optional intent text + LLM flag |
| `RankingResponse` | Ranked items + latency breakdown + parsed intent |

### Translator (`intent_engine/rules_translator.py`)

Rules-first intent translator:

- **Keyword mapping** — flat dict mapping input words to output keywords, preferences, and priority deltas
- **Time bucket inference** — maps hour (0–23) to buckets: morning, mid_morning, afternoon, afterschool, evening, bedtime, late_night
- **Weekend detection** — Saturday/Sunday adds family/outdoor keywords
- **Safe defaults** — empty or unknown input returns a neutral `browse` intent with priority 0.5

### Ranker (`intent_engine/simple_ranker.py`)

Simple deterministic re-ranker with soft constraints:

1. **Keyword matching** — ratio of matched keywords in item title/tags/category/description
2. **Preference matching** — exact match on item attributes vs intent preferences
3. **Combined scoring** — `(keyword_score + preference_score) / 2 * priority`
4. **Blending** — `final = (1 - weight) * base + weight * intent`
5. **Explanations** — 2–3 lines per item: match detail, score tier, base score note

### Intent Parser (`intent_engine/intent_parser.py`)

Rules-based free-text intent classifier:

- **Keyword classification** — maps trigger words to IntentType enum values with confidence scoring
- **Filter extraction** — regex patterns pull out price_max, price_min, category, brand from text
- **LLM fallback** — calls `LLMAdapter` when `use_llm=True` and confidence < 0.5; adapter is gated by `LLM_ENABLED` env var and returns `None` on any failure

### LLM Adapter (`intent_engine/llm_adapter.py`)

Optional LLM integration, OFF by default:

- **Env-var gated** — only active when `LLM_ENABLED=1` (or `true`/`yes`)
- **Strict validation** — parses LLM output as JSON, validates with Pydantic; returns `None` on any error
- **Structured logging** — logs failures without leaking user content
- **Stub implementation** — `_call_llm()` is a no-op; replace the body with your HTTP/SDK call

### Ranking Engine (`intent_engine/ranking_engine.py`)

Advanced multi-factor ranker for the `Item` schema:

- **Base scoring** — `(quality * 0.4) + (popularity * 0.3)`
- **Intent boosts** — type-specific: popular boosts popularity, budget boosts cheap items, discovery boosts niche items
- **Preference boosts** — matches category/brand from user preferences
- **Budget constraints** — penalizes items outside user's budget range
- **History boosts** — small bump for previously viewed items
- **Diversity guardrails** — prevents 3+ consecutive items from the same category
- **Latency tracking** — measures ms for each pipeline stage

### FastAPI App (`intent_engine/api.py`)

REST API with three endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Service info + health check |
| `/health` | GET | Health check |
| `/rank` | POST | Rank items via `RankingRequest` → `RankingResponse` |

The `/rank` endpoint dispatches on `request.mode`:
- `"advanced"` (default) → `IntentParser` + `RankingEngine`
- `"simple"` → `IntentTranslator` + `IntentRanker`

Start with: `uvicorn intent_engine.api:app --reload` (serves on port 8000)

### Fallback Behavior

| Situation | What happens |
|-----------|-------------|
| Empty/unknown input text | Translator returns `browse` intent, priority 0.5 — ranking falls back to base scores |
| No keywords match any item | All items get intent_score=0; ranking is driven by base_score |
| Intent weight = 0 | Intent is completely ignored; pure base_score ordering |
| LLM adapter called | `llm_adapter.py` gated by `LLM_ENABLED` env var; stub returns empty JSON → adapter returns `None` → rules result is used; any exception → returns `None` |

## Tradeoffs

- **Rules over ML**: The keyword map is manually curated. This is transparent and debuggable but won't generalize to unseen vocabulary without updates.
- **Flat keyword map**: Intentionally simple — no hierarchy, no embeddings. Easy to audit, fast to execute, trivial to test.
- **Soft constraint only**: Intent never filters items. This preserves catalog coverage but means low-relevance items always appear at the bottom.
- **No personalization history**: The ranker doesn't learn from past interactions. This keeps it stateless and deterministic.
- **Single-pass scoring**: No iterative refinement or multi-stage ranking. Sufficient for catalogs up to ~10K items.

## Testing

Run the full test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=intent_engine --cov-report=term-missing
```

> **Note**: API tests (`test_api.py`) require `fastapi` and `httpx` to be installed.

## Project Structure

```
intent-engine/
├── intent_engine/
│   ├── __init__.py          # Package version
│   ├── schemas.py           # Pydantic models (Intent, Item, RankedItem, RankingRequest, etc.)
│   ├── rules_translator.py  # Rules-first intent translator
│   ├── simple_ranker.py     # Soft-constraint re-ranker (simple)
│   ├── intent_parser.py     # Rules-based text classifier with filter extraction
│   ├── ranking_engine.py    # Advanced multi-factor ranker with diversity
│   ├── llm_adapter.py       # Optional LLM adapter (OFF by default, env-var gated)
│   └── api.py               # FastAPI REST API (mode dispatch: simple/advanced)
├── tests/
│   ├── test_schemas.py      # Schema validation (11 tests)
│   ├── test_ranker.py       # Simple ranker tests (15 tests)
│   ├── test_translator.py   # Translator tests (27 tests)
│   ├── test_reranker_soft.py # Soft-constraint behavior tests (11 tests)
│   ├── test_intent_parser.py # Intent parser tests (14 tests)
│   ├── test_ranking_engine.py # Advanced ranking engine tests (13 tests)
│   ├── test_api.py          # FastAPI endpoint tests (8 tests)
│   └── test_integration.py  # End-to-end integration tests (4 tests)
├── scripts/
│   ├── demo_runner.py       # 3-scenario demo (bedtime, STEM, weekend)
│   ├── demo.py              # Basic single-scenario demo
│   └── examples.py          # Advanced usage examples
├── README.md
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Non-Goals

This engine intentionally does **not** do the following:

- **Full recommender system** — no collaborative filtering, no user embeddings, no A/B testing framework
- **Real-time ML inference** — no model serving, no feature stores, no online learning
- **Personalization from history** — the ranker is stateless; it doesn't learn from past sessions
- **Content filtering / moderation** — all items that go in come out; intent is a soft signal only
- **Authentication / authorization** — the API has no auth layer; add your own middleware upstream
- **Catalog management** — no CRUD for items; callers pass candidates per request

## Failure Modes

| Failure | Behavior |
|---------|----------|
| Empty item list | FastAPI returns 422 (Pydantic validation: `min_length=1`) |
| Invalid JSON body | FastAPI returns 422 with field-level error details |
| Unknown `mode` value | FastAPI returns 422 (Pydantic enum validation) |
| LLM adapter raises | Returns `None`; rules-based result is used; error logged at WARNING level |
| LLM returns invalid JSON | Adapter returns `None`; rules fallback; no crash |
| All items score identically | Order is stable (Python sort is stable); no random tiebreaking |
| Ranking engine exception | `/rank` returns 500 with `"Ranking failed: <message>"` |

## Design Principles

1. **Determinism** — same input, same output, every time
2. **Soft constraints** — intent re-ranks, never filters
3. **Explainability** — every score has a human-readable reason
4. **Rules first** — no LLM dependency; LLM is optional and off by default
5. **Safe defaults** — unknown input degrades gracefully to base-score ordering

## License

MIT
