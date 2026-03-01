# Intent Engine v2 Spec

## Problem

Parents spend ~10 minutes per day manually filtering streaming content for their children. Recommendation systems optimize for engagement — not parental intent — leading to friction, eroded trust, and missed opportunities around learning, wellness, and healthy routines.

Current solutions (age gates, watch time limits, profile locks) address **restriction**, not **guidance**. Parents have contextual goals that today's systems can't express:

- "It's bedtime — I want something calm, not exciting."
- "They've been watching all day — show them something educational."
- "It's Saturday afternoon — active and fun is fine."

These intent signals are invisible to existing recommendation infrastructure.

## Solution: Deterministic Intent-Aware Re-Ranking

Intent Engine is a rules-first, deterministic re-ranking layer that sits between content retrieval and presentation. Parents express context once, and the system adapts — explainably, with no ML required.

**Core properties:**
- **Deterministic** — same input, same output, every time
- **Soft constraints** — intent re-ranks items but never filters them
- **Explainable** — every score has a human-readable reason and decomposable formula
- **Rules first** — no LLM dependency; LLM is optional and OFF by default
- **Safe defaults** — unknown input degrades gracefully to base-score ordering
- **Safety first** — hard constraints (age ratings, maturity gates) apply before any ranking logic
- **Platform-agnostic** — same engine works for streaming, music, and e-commerce catalogs

## What Was Built

### Backend (Python / FastAPI)

**168 tests, all passing.** Fully implemented ranking pipeline with two modes.

| Component | Purpose |
|-----------|---------|
| `schemas.py` | Pydantic models: Intent, Item, RankedItem, RankingRequest/Response, IntentType enum (popular, budget, premium, comparison, targeted, discovery, unknown), RankingMode enum (simple, advanced) |
| `rules_translator.py` | Rules-first intent translation: keyword mapping, time-of-day bucket inference (morning through late_night), weekend detection, safe defaults for unknown input |
| `simple_ranker.py` | Soft-constraint re-ranker: keyword matching, preference matching, intent_weight blending (`final = (1-w)*base + w*intent`), 2-3 structured explanation lines per item |
| `intent_parser.py` | Free-text intent classifier: keyword-to-IntentType mapping with confidence scoring, regex filter extraction (price, category, brand), LLM fallback when confidence < 0.5 |
| `ranking_engine.py` | Multi-factor ranker: base scoring (quality×0.4 + popularity×0.3), intent-type-specific boosts, preference matching, budget constraints, history boosts, diversity guardrails (no 3+ consecutive same-category), latency tracking per pipeline stage |
| `prophecy_agent.py` | Time-aware intent scheduling: 6 time contexts (early morning through late night), schedule management with day-of-week filters and midnight-crossing, shift prediction, proactive suggestions (configurable lookahead window, default 15 min), override tracking |
| `llm_adapter.py` | Optional LLM integration: env-var gated (`LLM_ENABLED`), strict JSON + Pydantic validation, structured logging, returns `None` on any error — stub `_call_llm()` body ready for HTTP/SDK replacement |
| `api.py` | FastAPI REST API: `/rank` POST endpoint dispatches on `mode` field — `"simple"` routes to IntentTranslator + IntentRanker, `"advanced"` (default) routes to IntentParser + RankingEngine |

#### Two Ranking Modes

**Simple mode** — lightweight keyword/preference matching:
```
User input → IntentTranslator (keyword map + time bucket) → IntentRanker (soft-constraint blending) → Ranked items with explanations
```

**Advanced mode** (default) — multi-factor scoring with diversity:
```
User input → IntentParser (classification + filter extraction + optional LLM) → RankingEngine (multi-factor scoring + diversity guardrails) → Ranked items with latency breakdown
```

#### Prophecy Agent

Time-aware intent scheduling that predicts and automates intent shifts:

```python
agent = ProphecyAgent()
agent.add_schedule(IntentSchedule(
    time_context=TimeContext.BEDTIME,
    start_time=time(20, 0),
    end_time=time(22, 0),
    intent_template={"energyLevel": 15, "tone": "soothing"},
))

# 15 minutes before bedtime → proactive suggestion
suggestion = agent.should_suggest_intent_shift(datetime(2026, 2, 20, 19, 50))
```

### Frontend (React / TypeScript / Tailwind)

**Deployed to Vercel.** Two distinct experiences.

#### `/` — Parent-Intent Wizard Flow

| Screen | What It Shows |
|--------|---------------|
| Intent Setup | Parent sets context: time (auto-detected), energy level, age range — defaults-over-configuration, override only what matters |
| Curated Home | Content rows re-ranked by intent — "Top picks for your kids" reflects active context, not pure engagement |
| Kid Browse | Netflix-style hero + category rows — content pre-filtered and ranked by intent before the child sees it; categories dynamically weighted |
| Content Detail | Explainable recommendations — "Why we picked this" panel with rationale (age-appropriate, encourages curiosity, etc.) |
| PIN Gate | 4-digit PIN keeps parent controls away from kids — simple, familiar pattern |
| Parent Controls | Fine-grained: prioritize educational, lower stimulation, weekly rotation, viewing time limits, "end on a calm note," Trust & Safety card |

#### `/demo` — Interactive Re-Ranking Demo

Portfolio-grade interactive demo showing the engine across three platforms.

| Feature | Implementation |
|---------|---------------|
| **Platform Tabs** | Streaming, Music, E-Commerce — each with 8-item catalog and 4 context presets |
| **Context Presets** | Streaming: Bedtime, Solo Morning, Family Weekend, Focus Session. Music: Wind Down, Morning Commute, Family Playtime, Deep Work. E-Commerce: Baby Shower, Treat Yourself, Family Holiday, Home Office |
| **Signal Sliders** | 5 tweakable signals (0-1): Time of Day, Viewer Profile, Energy Intent, Device, Prophecy Schedule — drag any slider, ranking updates instantly |
| **Before/After Columns** | Left: engagement-score order. Right: intent-adjusted order with movement indicators (+7, -4) and status badges (boosted, demoted, blocked) |
| **Scoring Formula** | Live code-style display: `base(0.58) × time(0.91) × viewer(1.20) × energy(0.90) × device(1.10) × prophecy(1.32) = 0.83` — hover any item to see its breakdown |
| **Prophecy Agent** | Mock scheduling card with countdown timer, intensity indicator (Off / Moderate / Full auto) |
| **Hard Constraints** | Adult-maturity content scores 0.00 when viewer signal is set to kids — visible as BLOCKED overlay |

#### Multiplier-Based Scoring Model

The demo uses a transparent multiplier chain (no additive black box):

```
final_score = base_engagement_score
  × time_multiplier        // time-of-day → calm/active preference
  × viewer_multiplier      // maturity gating (0.0 = blocked, 1.2 = boosted)
  × energy_multiplier      // energy intent alignment with item calm score
  × device_multiplier      // runtime fit for screen size
  × prophecy_boost         // scheduled preference amplification
  + diversity_penalty      // penalizes genre repetition in ranked list
```

Each multiplier is computed from the item's metadata (`calmScore`, `maturity`, `complexity`, `runtime`) and the corresponding signal value (0-1). Every ranking decision is fully decomposable — an engineer can trace any anomaly to the exact signal that caused it.

| Signal | Low (0) | High (1) | Item Property |
|--------|---------|----------|---------------|
| Time | Late night → neutral | Bedtime → favor calm | `calmScore` |
| Viewer | Kids → block adult, boost kids | Solo adult → boost adult, reduce kids | `maturity` |
| Energy | Wind down → strongly favor calm | High energy → favor stimulating | `calmScore` (inverted) |
| Device | Phone → favor short runtime | Home theater → favor long premium | `runtime` |
| Prophecy | Off | Full auto → strong calm + kids boost | `calmScore`, `maturity` |

## Project Structure

```
intent-engine/
├── backend/
│   ├── intent_engine/
│   │   ├── schemas.py            # Pydantic models + enums
│   │   ├── rules_translator.py   # Rules-first intent translation
│   │   ├── simple_ranker.py      # Soft-constraint re-ranker (simple mode)
│   │   ├── intent_parser.py      # Text classifier + filter extraction (advanced mode)
│   │   ├── ranking_engine.py     # Multi-factor ranker + diversity (advanced mode)
│   │   ├── prophecy_agent.py     # Time-aware intent scheduling
│   │   ├── llm_adapter.py        # Optional LLM adapter (OFF by default)
│   │   └── api.py                # FastAPI REST API
│   ├── tests/                    # 168 tests
│   ├── scripts/                  # Demo scripts
│   └── demo_prophecy.py          # Prophecy Agent demo
├── frontend/
│   ├── src/
│   │   ├── pages/Demo.tsx        # Interactive re-ranking demo
│   │   ├── components/demo/
│   │   │   ├── PlatformTabs.tsx   # Platform selector
│   │   │   ├── ContextSwitcher.tsx # Vertical context presets
│   │   │   ├── SignalSliders.tsx   # 5 tweakable signals
│   │   │   ├── ScoringFormula.tsx  # Live multiplier display
│   │   │   ├── ProphecyAgent.tsx   # Scheduling indicator
│   │   │   └── ContentCard.tsx     # Item card with hover
│   │   └── data/
│   │       └── demoPlatforms.ts   # 3 catalogs + signals + ranking function
│   └── package.json
├── docs/screenshots/              # 10 Playwright-captured screenshots
└── README.md
```

## Test Coverage

| Suite | Tests | Covers |
|-------|-------|--------|
| `test_schemas.py` | 11 | Pydantic model validation, defaults, enums |
| `test_ranker.py` | 15 | Simple ranker: blending, explanations, edge cases |
| `test_translator.py` | 27 | Keyword mapping, time buckets, weekend detection, safe defaults |
| `test_reranker_soft.py` | 11 | Soft-constraint behavior: all items survive, ordering correctness |
| `test_intent_parser.py` | 14 | Text classification, filter extraction, confidence scoring |
| `test_ranking_engine.py` | 13 | Multi-factor scoring, diversity, budget constraints |
| `test_api.py` | 8 | FastAPI endpoints, mode dispatch, error handling |
| `test_integration.py` | 4 | End-to-end through `/rank` for both modes |
| `test_prophecy_agent.py` | 58 | Scheduling, shift prediction, override tracking, edge cases |
| **Total** | **168** | |

## Fallback Behavior

| Situation | What Happens |
|-----------|-------------|
| Empty/unknown input | Translator returns neutral `browse` intent (priority 0.5) → ranking falls back to base scores |
| No keywords match | All items get intent_score=0 → ranking is driven by base_score |
| Intent weight = 0 | Intent ignored entirely → pure base_score ordering |
| LLM adapter called | Gated by `LLM_ENABLED` env var; stub returns empty JSON → adapter returns `None` → rules result used; any exception → returns `None` |
| Viewer signal blocks content | Item scores 0.00, rendered with BLOCKED overlay — item stays in list (soft constraint) but is visually gated |
| Unknown platform/context | Demo defaults to first context preset with safe signal values |

## Tradeoffs

| Decision | Upside | Downside |
|----------|--------|----------|
| Rules over ML | Transparent, debuggable, deterministic, fast | Won't generalize to unseen vocabulary without manual keyword updates |
| Flat keyword map | Easy to audit, fast to execute, trivial to test | No semantic understanding, no hierarchy |
| Soft constraints only | Preserves catalog coverage, no accidental content removal | Low-relevance items always appear at the bottom, never hidden |
| No personalization history | Stateless, deterministic, privacy-preserving | Doesn't learn from past sessions |
| Multiplier-based scoring | Each signal's contribution is independently visible and tunable | Multiplicative interactions can amplify small signals unexpectedly |
| Client-side demo ranking | Zero latency, works offline, no backend dependency | Demo scoring diverges from backend scoring model |
| Platform-agnostic design | One engine serves streaming, music, e-commerce | Signal semantics (e.g., "device") require per-platform interpretation |

## Business Case

**Problem:** Parents spend 10 min/day manually filtering content for kids.

**Solution:** Set intent once, auto-switch on schedule — set it and forget it.

**Impact:** Reducing friction on parent profiles by even 2% churn translates to ~$180M annual revenue opportunity for a platform at Netflix scale.

**Trust multiplier:** Intent-aware ranking aligns platform incentives with parental goals. When parents feel the system respects their boundaries — not fighting them — retention deepens beyond what engagement optimization alone can achieve.

## What's Not Built Yet

| Gap | Notes |
|-----|-------|
| LLM adapter body | `_call_llm()` is a no-op stub — needs HTTP/SDK call when an LLM provider is chosen |
| Frontend ↔ Backend connection | Demo uses client-side mock data; not wired to the FastAPI `/rank` endpoint |
| Auth middleware | No authentication/authorization on the API |
| Observability | No structured JSON logging, request tracing, or metrics |
| A/B testing framework | No experimentation infrastructure |
| Real content embeddings | Item metadata is manually authored, not derived from content analysis |
| Persistence | Prophecy Agent overrides are in-memory only |

## Design Principles

1. **Determinism** — same input, same output, every time
2. **Soft constraints** — intent re-ranks, never filters
3. **Explainability** — every score has a human-readable reason
4. **Rules first** — no LLM dependency; LLM is optional and off by default
5. **Safe defaults** — unknown input degrades gracefully to base-score ordering
6. **Safety first** — hard constraints (age ratings) apply before any ranking logic
7. **Trust over engagement** — optimize for parental trust, not watch time
8. **Defaults over configuration** — auto-infer from context, let parents override only what matters

---

> Built by [Jeremiah Walters](https://www.linkedin.com/in/jeremiahwalters/) ([GitHub](https://github.com/jtwalters25)) — exploring how thoughtful systems design can make streaming better for families.
