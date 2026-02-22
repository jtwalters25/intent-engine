# Intent Engine

A deterministic, intent-aware re-ranking engine with a React prototype UI. Demonstrates how parental intent signals — time of day, energy preferences, learning goals — can reshape content recommendations without ML, personalization, or randomness.

> **Prototype** — built to demonstrate systems thinking and backend architecture, not a production service.

## Live Demo

**Interactive UI:** https://dist-pisd-one-60.vercel.app
**Python Backend:** Fully implemented with 168 passing tests

> **Note:** The frontend currently uses mock data and is not connected to the backend API. The backend runs locally via `uvicorn`.

## What It Does

**Problem:** Parents spend ~10 min/day manually filtering content. Streaming recommendations optimize for engagement, not parental intent.

**Solution:** A re-ranking layer that sits between retrieval and presentation. Parents express context once ("it's bedtime"), and the system adapts — deterministically, explainably, with no ML required.

**Key capabilities:**
- Rules-first intent translation (keyword mapping, time-of-day inference)
- Soft-constraint re-ranking (intent boosts items but never filters them)
- Prophecy Agent for time-aware scheduling (auto-switch to bedtime mode at 8 PM)
- Structured explanations for every ranking decision
- Optional LLM fallback (off by default, env-var gated)

## Project Structure

```
intent-engine/
├── backend/                     # Python backend (FastAPI + ranking engine)
│   ├── intent_engine/
│   │   ├── schemas.py           # Pydantic models (Intent, Item, RankedItem, etc.)
│   │   ├── rules_translator.py  # Rules-first intent translator
│   │   ├── simple_ranker.py     # Soft-constraint re-ranker
│   │   ├── intent_parser.py     # Free-text intent classifier
│   │   ├── ranking_engine.py    # Multi-factor ranker with diversity
│   │   ├── prophecy_agent.py    # Time-aware intent scheduling
│   │   ├── llm_adapter.py       # Optional LLM adapter (OFF by default)
│   │   └── api.py               # FastAPI REST API
│   ├── tests/                   # 168 tests, all passing
│   ├── scripts/                 # Demo scripts
│   ├── demo_prophecy.py         # Prophecy Agent demo
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── README.md                # Backend-specific docs
├── frontend/                    # React UI prototype
│   ├── src/                     # React components, pages, hooks
│   ├── public/                  # Static assets
│   ├── package.json
│   └── README.md                # Frontend-specific docs
└── README.md                    # This file
```

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start API server
uvicorn intent_engine.api:app --reload

# Run demos
python -m scripts.demo_runner
python demo_prophecy.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`.

## Two Ranking Modes

The `/rank` endpoint accepts a `mode` field:

| Mode | Pipeline | Use Case |
|------|----------|----------|
| `simple` | IntentTranslator + IntentRanker | Lightweight keyword/preference matching |
| `advanced` (default) | IntentParser + RankingEngine | Multi-factor scoring with diversity guardrails |

## Prophecy Agent

Time-aware intent scheduling that predicts and automates intent shifts:

```python
from intent_engine.prophecy_agent import ProphecyAgent, IntentSchedule, TimeContext
from datetime import datetime, time

agent = ProphecyAgent()
agent.add_schedule(IntentSchedule(
    time_context=TimeContext.BEDTIME,
    start_time=time(20, 0),
    end_time=time(22, 0),
    intent_template={"energyLevel": 15, "tone": "soothing"},
))

# 15 minutes before bedtime — get a proactive suggestion
suggestion = agent.should_suggest_intent_shift(datetime(2026, 2, 20, 19, 50))
```

## Business Case

**Problem:** Parents spend 10 min/day manually filtering content for kids.

**Solution:** Set intent once, auto-switch on schedule — set it and forget it.

**Impact:** Reducing friction on parent profiles by even 2% churn translates to ~$180M annual revenue opportunity for a platform at Netflix scale.

## Design Principles

1. **Determinism** — same input, same output, every time
2. **Soft constraints** — intent re-ranks, never filters
3. **Explainability** — every score has a human-readable reason
4. **Rules first** — no LLM dependency; LLM is optional and off by default
5. **Safe defaults** — unknown input degrades gracefully to base-score ordering
6. **Safety first** — hard constraints (age ratings) apply before any ranking logic

## About

Built by [Jeremiah Walters](https://www.linkedin.com/in/jeremiahwalters/) ([GitHub](https://github.com/jtwalters25)) — exploring how thoughtful systems design can make streaming better for families.

## License

MIT
