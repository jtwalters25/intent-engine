# Intent Engine v3 Spec

## Problem

Ranked surfaces are everywhere — streaming libraries, ride options, food delivery feeds, driver incentive displays. Every one of them shares the same flaw: they optimize for platform engagement, not user context.

The result is friction. A parent can't tell Netflix "it's bedtime, wind them down." A commuter can't tell Uber "I take UberX every weekday at 8am — stop showing me Pool." A hungry user can't tell Uber Eats "it's Sunday, I want comfort food, not my usual."

Current solutions address restriction, not guidance. They can't express intent.

> "It's bedtime — show something calm, not exciting."
> "It's my morning commute — surface my usual ride, fast."
> "They've been watching all day — show something educational."

These signals are invisible to existing recommendation infrastructure.

---

## Solution: Domain-Agnostic Intent-Aware Re-Ranking

Intent Engine is a rules-first, deterministic re-ranking layer that sits between content retrieval and presentation — across any ranked surface. Context is expressed once. The system adapts. Explainably. Without ML.

**Core properties:**
- **Deterministic** — same input, same output, every time
- **Domain-agnostic** — one engine, pluggable domain adapters
- **Soft constraints** — intent re-ranks, never filters
- **Explainable** — every score has a human-readable reason and decomposable formula
- **Rules first** — no LLM dependency; LLM is optional and OFF by default
- **Safe defaults** — unknown input degrades gracefully to base-score ordering
- **Hard constraints first** — maturity gates, surge caps, allergen blocks apply before any ranking logic

---

## Domains

Intent Engine ships with three domain adapters out of the box:

| Domain | Ranked Surface | Platform Analogy |
|--------|---------------|-----------------|
| `streaming` | Content catalog | Netflix |
| `ride_matching` | Ride product options | Uber |
| `food_delivery` | Restaurant / dish feed | Uber Eats |

Each domain shares the same engine core. Only the signal vocabulary and item metadata schema change.

---

## Schemas

### Domain + Intent Enums

```python
class Domain(str, Enum):
    streaming = "streaming"
    ride_matching = "ride_matching"
    food_delivery = "food_delivery"

class StreamingIntent(str, Enum):
    popular = "popular"
    educational = "educational"
    calm = "calm"
    discovery = "discovery"
    unknown = "unknown"

class RideIntent(str, Enum):
    budget = "budget"        # Pool, shared
    comfort = "comfort"      # UberX, Comfort
    premium = "premium"      # Black, SUV
    urgent = "urgent"        # fastest available
    habitual = "habitual"    # matches recurring pattern

class FoodIntent(str, Enum):
    comfort = "comfort"
    healthy = "healthy"
    fast = "fast"
    discovery = "discovery"
    habitual = "habitual"
    unknown = "unknown"
```

### Item Schema

```python
class Item(BaseModel):
    id: str
    title: str
    base_score: float          # platform-provided engagement score
    domain: Domain
    attributes: dict           # domain-specific metadata (see below)

# Streaming attributes
{
    "calm_score": 0.8,         # 0=stimulating, 1=calm
    "maturity": "kids",        # kids | family | teen | adult
    "complexity": 0.4,         # cognitive load
    "runtime_minutes": 22
}

# Ride attributes
{
    "comfort_score": 0.7,      # 0=basic, 1=premium
    "eta_minutes": 4,
    "price_multiplier": 1.2,   # surge factor
    "capacity": 4,
    "eco_rating": 0.6
}

# Food attributes
{
    "prep_time_minutes": 15,
    "cuisine_type": "mexican",
    "price_tier": 2,           # 1-4
    "health_score": 0.6,
    "reorder_rate": 0.4        # how often this is reordered by similar users
}
```

### Ranking Request/Response

```python
class RankingRequest(BaseModel):
    domain: Domain
    mode: RankingMode          # simple | advanced
    intent: dict               # domain-specific intent signals
    items: list[Item]
    constraints: dict = {}     # hard constraints (surge_cap, maturity_gate, allergens)

class RankedItem(BaseModel):
    item: Item
    final_score: float
    score_breakdown: ScoreBreakdown
    explanation: str           # human-readable reason
    status: str                # boosted | neutral | demoted | blocked

class RankingResponse(BaseModel):
    ranked_items: list[RankedItem]
    intent_resolved: dict
    mode_used: RankingMode
    latency_ms: dict           # per-stage latency breakdown
    domain: Domain
```

---

## Signal Maps

The same five signals operate across all domains. Only their semantic meaning changes per domain.

| Signal | Streaming | Ride Matching | Food Delivery |
|--------|-----------|---------------|---------------|
| **context** | Time of day → calm/active | Time of day → commute/leisure | Time of day → meal type |
| **profile** | Viewer maturity (kids/adult) | Rider tier preference | Dietary profile |
| **urgency** | Energy level | Trip urgency | Hunger urgency |
| **cost_sensitivity** | N/A | Surge price tolerance | Price tier preference |
| **schedule** | Prophecy bedtime/morning | Commute pattern | Meal routine |

### Hard Constraint Equivalents

| Streaming | Ride | Food |
|-----------|------|------|
| Maturity gate (blocks adult content for kids) | Surge cap (blocks rides above price threshold) | Allergen block (blocks items with flagged ingredients) |

The hard constraint pattern is universal. The vocabulary changes. The enforcement logic does not.

---

## Scoring Formula

Domain-agnostic multiplier chain:

```
final_score = base_score
  × context_multiplier       # time-of-day alignment with item attributes
  × profile_multiplier       # user profile fit (maturity, tier, dietary)
  × urgency_multiplier       # urgency alignment (calm/active, fast/leisurely)
  × cost_multiplier          # price sensitivity alignment
  × prophecy_boost           # scheduled preference amplification
  + diversity_penalty        # penalizes consecutive same-category items
```

### Per-Domain Multiplier Behavior

**Streaming:**
- `context_multiplier`: bedtime → favors high `calm_score`
- `profile_multiplier`: kids profile → blocks adult maturity (score = 0.0)
- `urgency_multiplier`: low energy → favors high `calm_score`

**Ride Matching:**
- `context_multiplier`: morning commute → favors low `eta_minutes`
- `profile_multiplier`: budget rider → favors low `price_multiplier`, demotes Black/SUV
- `urgency_multiplier`: high urgency → favors lowest ETA regardless of comfort
- `cost_multiplier`: surge sensitivity → soft-demotes high `price_multiplier` items; hard blocks above cap

**Food Delivery:**
- `context_multiplier`: Sunday evening → favors high `health_score` inverse (comfort food)
- `profile_multiplier`: dietary profile → blocks allergen-flagged items
- `urgency_multiplier`: high hunger urgency → favors low `prep_time_minutes`
- `cost_multiplier`: price sensitivity → demotes tier 3-4 items

---

## Prophecy Agent (Extended)

Time-aware intent scheduling. Predicts and automates intent shifts across all domains.

```python
class IntentSchedule(BaseModel):
    domain: Domain
    time_context: TimeContext
    start_time: time
    end_time: time
    intent_template: dict
    day_filter: list[DayOfWeek] = []  # empty = every day
```

**Streaming example:**
```python
IntentSchedule(
    domain=Domain.streaming,
    time_context=TimeContext.BEDTIME,
    start_time=time(20, 0),
    end_time=time(22, 0),
    intent_template={"energy_level": 0.1, "tone": "soothing"}
)
```

**Ride matching examples:**
```python
# Morning commute — surface UberX fast, suppress Pool
IntentSchedule(
    domain=Domain.ride_matching,
    time_context=TimeContext.MORNING,
    start_time=time(7, 30),
    end_time=time(9, 0),
    intent_template={"urgency": 0.8, "comfort_preference": 0.6},
    day_filter=[Mon, Tue, Wed, Thu, Fri]
)

# Friday late night — suppress surge-sensitive, boost premium tolerance
IntentSchedule(
    domain=Domain.ride_matching,
    time_context=TimeContext.LATE_NIGHT,
    start_time=time(22, 0),
    end_time=time(2, 0),  # midnight crossing supported
    intent_template={"surge_sensitivity": 0.2, "premium_tolerance": 0.8},
    day_filter=[Fri, Sat]
)
```

**Food delivery example:**
```python
# Sunday evening comfort food routine
IntentSchedule(
    domain=Domain.food_delivery,
    time_context=TimeContext.EVENING,
    start_time=time(17, 0),
    end_time=time(20, 0),
    intent_template={"comfort_preference": 0.9, "health_priority": 0.1},
    day_filter=[Sun]
)
```

---

## Domain Adapter Pattern

Each domain ships as a self-contained adapter that maps domain vocabulary to the shared engine interface:

```python
class DomainAdapter(Protocol):
    def resolve_intent(self, raw_input: dict) -> dict: ...
    def compute_multipliers(self, item: Item, intent: dict) -> MultiplierSet: ...
    def apply_hard_constraints(self, item: Item, constraints: dict) -> bool: ...
    def explain(self, item: Item, multipliers: MultiplierSet) -> str: ...
```

Adding a new domain = implementing four methods. The engine core doesn't change.

**This is the architectural claim:** Intent Engine is not a streaming tool. It's a re-ranking primitive. Any ranked surface with scoreable items and contextual signals can plug in.

---

## Updated Project Structure

```
intent-engine/
├── backend/
│   ├── intent_engine/
│   │   ├── core/
│   │   │   ├── schemas.py           # Shared Pydantic models + enums
│   │   │   ├── ranking_engine.py    # Domain-agnostic multi-factor ranker
│   │   │   ├── prophecy_agent.py    # Domain-aware scheduling
│   │   │   ├── llm_adapter.py       # Optional LLM (OFF by default)
│   │   │   └── api.py               # FastAPI — domain routed via request
│   │   ├── adapters/
│   │   │   ├── streaming.py         # Netflix domain adapter
│   │   │   ├── ride_matching.py     # Uber ride adapter
│   │   │   └── food_delivery.py     # Uber Eats adapter
│   │   └── tests/
│   │       ├── core/                # Shared engine tests
│   │       └── adapters/            # Per-domain adapter tests
├── frontend/
│   ├── src/
│   │   ├── pages/Demo.tsx
│   │   └── components/demo/
│   │       ├── PlatformTabs.tsx     # Streaming | Ride | Food tabs
│   │       ├── SignalSliders.tsx    # Domain-aware signal labels
│   │       ├── ScoringFormula.tsx   # Live multiplier display
│   │       └── ProphecyAgent.tsx    # Domain-aware schedule display
└── README.md
```

---

## What's Not Built Yet (Updated)

| Gap | Priority | Notes |
|-----|----------|-------|
| `ride_matching.py` adapter | High | Schema + multiplier logic defined in this spec |
| `food_delivery.py` adapter | Medium | Extend after ride adapter validates pattern |
| Frontend domain tab expansion | High | Add Ride + Food tabs to `/demo` |
| Frontend ↔ Backend wiring | Medium | Demo currently client-side mock |
| Observability | Medium | Structured logging, per-stage latency to dashboard |
| Auth middleware | Low | Not needed for public demo |
| Real content data | Medium | MovieLens for streaming, synthetic for ride/food |
| A/B testing framework | Low | Post-MVP |
| Persistence | Low | Prophecy overrides in-memory only |

---

## The Architectural Claim

> Most recommendation systems are domain-specific implementations of the same problem: rank a set of items by relevance to a user's current context. Intent Engine treats this as a primitive — a composable re-ranking layer with pluggable domain adapters, deterministic scoring, and explainability at every layer.
>
> The same engine that helps a parent wind their kids down at bedtime helps a commuter surface their usual ride at 8am and helps a tired user find comfort food on a Sunday evening.
>
> Same problem. Different vocabulary. One engine.

---

> Built by [Jeremiah Walters](https://www.linkedin.com/in/jeremiahwalters/) ([GitHub](https://github.com/jtwalters25)) — exploring how thoughtful systems design can improve ranked surfaces everywhere.
