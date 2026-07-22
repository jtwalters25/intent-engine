# Netflix Kids: Parent-Intent Mode

A conceptual prototype demonstrating intent-aware content discovery for children's streaming. This project explores how parental intent signals (time of day, energy preferences, and learning goals) can be integrated into recommendation systems without sacrificing safety, performance, or engineering simplicity.

> **Note:** This is a design prototype intended to demonstrate systems thinking and backend architecture. It is not a production service.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Interactive Demo (`/demo`)](#interactive-demo-demo)
3. [Design Principles](#design-principles)
4. [High-Level System Architecture](#high-level-system-architecture)
5. [Demo Scoring Architecture](#demo-scoring-architecture)
6. [Intent Modeling](#intent-modeling)
7. [Ranking & Re-Ranking Strategy](#ranking--re-ranking-strategy)
8. [Embeddings & Content Graph](#embeddings--content-graph)
9. [Performance, Reliability & Fallbacks](#performance-reliability--fallbacks)
10. [Privacy & Trust Considerations](#privacy--trust-considerations)
11. [Prototype Scope & Limitations](#prototype-scope--limitations)
12. [Why This Matters](#why-this-matters)

---

## Project Overview

### The Problem

Current parental controls in streaming services focus primarily on **restriction and compliance**:
- Age gates and content ratings
- Watch time limits
- Profile locks

While necessary, these controls don't help parents with a more nuanced need: **intent-based guidance**. Parents often have contextual goals:

- "It's bedtime, I want something calm, not exciting."
- "They've been watching all day; show them something educational."
- "It's a rainy Saturday afternoon; active and fun is fine."

These intent signals are currently invisible to recommendation systems.

### What This Prototype Demonstrates

This project implements a **Parent-Intent Re-Ranking Layer**, a conceptual addition to existing recommendation infrastructure that:

1. Infers session context (time of day, child profile)
2. Accepts optional parent overrides (energy level, learning focus)
3. Re-ranks content candidates to match stated intent
4. Maintains all existing safety guarantees

The prototype includes two experiences:
- **Parent UI** (`/`): intent setup wizard, curated home, kid browse, content detail
- **Interactive Demo** (`/demo`): tweakable signal sliders with multi-platform catalogs showing real-time re-ranking

---

## Interactive Demo (`/demo`)

The `/demo` page is an interactive demonstration of the re-ranking engine.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  PlatformTabs · 5 verticals: Streaming, Music, E-Commerce,      │
│  Ride Matching, Food Delivery (Streaming carries a PILOT badge)  │
├──────────┬──────────────────────────────┬───────────────────────┤
│  LEFT    │         CENTER               │        RIGHT          │
│          │                              │                       │
│ Context  │  ┌─────────┐ ┌────────────┐  │  Signal Sliders      │
│ Switcher │  │ Before  │ │   After    │  │  ├ Time of Day       │
│ (4 pre-  │  │ column  │ │   column   │  │  ├ Viewer Profile    │
│  sets)   │  │(engage- │ │ (intent-   │  │  ├ Energy Intent     │
│          │  │ ment    │ │  adjusted) │  │  ├ Device            │
│ Prophecy │  │ order)  │ │ + movement │  │  └ Prophecy Schedule │
│ Agent    │  └─────────┘ └────────────┘  │                       │
│ indicator│                              │  Scoring Formula     │
│          │                              │  (live multipliers)   │
└──────────┴──────────────────────────────┴───────────────────────┘
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `PlatformTabs` | `components/demo/PlatformTabs.tsx` | Switch between 5 platform catalogs |
| `ContextSwitcher` | `components/demo/ContextSwitcher.tsx` | Vertical preset selector (4 per platform) |
| `SignalSliders` | `components/demo/SignalSliders.tsx` | 5 tweakable signal weights with color-coded fills |
| `ScoringFormula` | `components/demo/ScoringFormula.tsx` | Live code-style multiplier breakdown |
| `ProphecyAgent` | `components/demo/ProphecyAgent.tsx` | Mock scheduling card with countdown |
| `ContentCard` | `components/demo/ContentCard.tsx` | Item card with score badge, status, hover interaction |

### Platforms & Catalogs

| Platform | Items | Context Presets |
|----------|-------|-----------------|
| **Streaming** (`PILOT`) | Dark S3, Outer Range, Inception, The Office, Merlin Chronicles, Lion King, Planet Earth III, Bluey S4 | Bedtime, Solo Morning, Family Weekend, Focus Session |
| **Music** | Sleep Stories Podcast, Deep Focus Playlist, Morning Jazz, True Crime Weekly, Kids Sing-Along, Lo-Fi Study, Pop Hits, Classical for Baby | Wind Down, Morning Commute, Family Playtime, Deep Work |
| **E-Commerce** | Noise-Canceling Headphones, Smart Watch Pro, Baby Blanket, LEGO Set, Espresso Machine, Art Kit, Desk Mat, Board Games | Baby Shower, Treat Yourself, Family Holiday, Home Office |
| **Ride Matching** | UberX, Uber Comfort, Uber Black, UberX Share, Uber Green, UberXL, Uber Moto, Uber Shuttle | Morning Commute, Friday Night Out, Airport Run, Weekend Errand |
| **Food Delivery** | Thai Comfort Bowl, Acai Health Bowl, Quick Burrito, Discovery Ramen, Margherita Pizza, Sushi Platter, Caesar Salad, Late Night Tacos | Sunday Comfort, Weekday Lunch, Healthy Reset, Late Night Craving |

The five signals keep the same scoring math across verticals but are relabeled to fit each domain. Ride Matching uses Rider Profile, Trip Urgency, Surge Sensitivity, and Commute Pattern; Food Delivery uses Meal Time, Dietary Profile, Hunger Urgency, Price Sensitivity, and Meal Routine.

### Scoring Formula

```
final_score = base_engagement_score
  × time_multiplier        // time → calm/active alignment
  × viewer_multiplier      // maturity → viewer profile match
  × energy_multiplier      // energy intent → calm score alignment
  × device_multiplier      // device size → runtime fit
  × prophecy_boost         // scheduled preference amplification
  + diversity_penalty      // penalizes consecutive same-genre

// Hard constraint
if (maturity === "adult" && viewer === "kids") → BLOCKED
```

Each multiplier is computed from the item's metadata (calmScore, maturity, complexity, runtime) and the current signal value (0-1 slider). Users can tweak any signal in real-time and see the ranking update instantly.

### Screenshots

![Demo Overview](../docs/screenshots/07-demo-overview.png)
**Streaming / Bedtime.** Same 8-item catalog, two columns: engagement-only (left) vs. intent-adjusted (right). At bedtime with a kids viewer profile, Bluey S4 jumps from #8 to #1. Dark Season 3 (TV-MA) drops to the bottom via the viewer multiplier. Signal sliders on the right update rankings live. The scoring formula box breaks the #1 item's score into its multiplier chain.

![Scoring Formula](../docs/screenshots/08-scoring-formula.png)
**Scoring formula.** Every ranking decision breaks down into its parts: `base(0.58) x time(0.91) x viewer(1.20) x energy(0.90) x device(1.10) x prophecy(1.32) = 0.83`. Each multiplier maps to a single signal slider, so an engineer can trace any ranking anomaly back to the signal that caused it.

![Music Platform](../docs/screenshots/09-platform-music.png)
**Music / Wind Down.** The same engine works across verticals. Sleep Stories Podcast holds #1 (high calm score plus prophecy boost). Morning Jazz moves up past Deep Focus via the time multiplier. The pipeline is platform-agnostic: swap the catalog and signal configs and keep the same scoring.

![E-Commerce](../docs/screenshots/10-platform-ecommerce.png)
**E-Commerce / Baby Shower.** Intent-aware ranking beyond media. With viewer set to "kids" for gift-buying, Baby Blanket and Art Kit jump to the top. Headphones and Smart Watch are BLOCKED as adult-maturity items gated by the viewer signal at `viewer(0.00)`. The same formula drives every vertical.

---

## Design Principles

These principles guide every architectural decision:

### 1. Safety First
Hard constraints (age ratings, content blocks) are applied **before** any ranking logic. Intent signals never override safety filters.

### 2. Defaults Over Configuration
The system auto-infers reasonable defaults from context (time of day, child age). Parents can override, but shouldn't have to.

### 3. Soft Intent Constraints
Intent preferences apply **weights**, not gates. A "calm bedtime" session still surfaces some variety; it doesn't hard-block all energetic content.

### 4. Graceful Degradation
If intent services fail, the system falls back to standard Kids recommendations. No failure mode should leave a child staring at an error screen.

### 5. Trust Over Short-Term Engagement
The ranking system optimizes for parental trust, not watch time. Content that supports healthy routines is preferred over content that maximizes session length.

---

## High-Level System Architecture

The intent-aware pipeline integrates with existing recommendation infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST FLOW                                    │
└─────────────────────────────────────────────────────────────────────────────┘

   Parent UI          Intent             Safety &           Candidate
   (Session Setup) → Inference    →    Eligibility    →   Generation
                      Service           Filters            (Existing)
                         │                  │                   │
                         ▼                  ▼                   ▼
                   ┌─────────────────────────────────────────────────┐
                   │         INTENT-AWARE RE-RANKING LAYER           │
                   │                                                 │
                   │  • Apply multiplier-based score modifiers       │
                   │  • Enforce diversity constraints                │
                   │  • Apply rotation rules (avoid repetition)      │
                   │  • Respect energy-level preferences             │
                   │  • Hard-gate maturity mismatches                │
                   └─────────────────────────────────────────────────┘
                                          │
                                          ▼
                                    Cache Layer
                                          │
                                          ▼
                                   Final Response
                                   (Ranked Rows)
```

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Re-ranking, not filtering | Intent preferences should influence order, not eliminate options |
| Multiplier-based scoring | Transparent math; each signal's contribution is independently visible |
| Reuse existing candidate generation | Minimizes integration risk; leverages proven ML infrastructure |
| Intent as a modifier layer | Clean separation of concerns; easy to disable or A/B test |
| Session-scoped intent | Privacy-preserving; no persistent behavioral modeling of children |

---

## Demo Scoring Architecture

The `/demo` page implements the scoring model as a pure client-side function in `data/demoPlatforms.ts`.

### Signal → Multiplier Mapping

| Signal | Low (0) | Mid (0.5) | High (1) | Item Property Used |
|--------|---------|-----------|----------|-------------------|
| **Time** | Late night → neutral | Afternoon → neutral | Bedtime → favor calm | `calmScore` |
| **Viewer** | Kids → block adult, boost kids | Teens → neutral | Solo adult → boost adult, reduce kids | `maturity` |
| **Energy** | Wind down → strongly favor calm | Neutral | High energy → favor stimulating | `calmScore` (inverted) |
| **Device** | Phone → favor short runtime | Laptop → neutral | Home theater → favor long premium | `runtime` |
| **Prophecy** | Off | Moderate boost to calm | Full auto → strong calm + kids boost | `calmScore`, `maturity` |

### Data Flow

```
signalOverrides (user sliders)
        │
        ▼
merge with contextDefaults → SignalValues
        │
        ▼
rankWithSignals(catalog, signals)
    ├── computeTimeMultiplier(item, time)
    ├── computeViewerMultiplier(item, viewer)    // returns 0.0 = BLOCKED
    ├── computeEnergyMultiplier(item, energy)
    ├── computeDeviceMultiplier(item, device)
    ├── computeProphecyBoost(item, prophecy, time)
    └── computeDiversityPenalty(items)
        │
        ▼
ScoringBreakdown per item → sort → RankedPlatformItem[]
```

---

## Intent Modeling

### Intent Object Structure

Parent intent is represented as structured, typed data:

```typescript
interface ParentIntent {
  sessionId: string;
  childProfileId: string;
  timestamp: ISO8601;
  timeOfDay: 'morning' | 'afternoon' | 'evening' | 'bedtime';
  energyLevel: number;  // 0 = very calm, 100 = high energy
  learningFocus: Array<'stem' | 'literacy' | 'emotional' | 'social' | 'fun'>;
  ageRange: string;
  prioritizeEducational: boolean;
  lowerStimulation: boolean;
  endOnCalmNote: boolean;
}
```

### On LLM Usage

Large language models may be used for:
- Natural language translation ("I want something calm" → `energyLevel: 20`)
- Fallback intent parsing when structured input fails

LLMs are **never** given decision authority. All final ranking decisions use deterministic rules applied to structured intent data.

---

## Ranking & Re-Ranking Strategy

### Candidate Generation (Unchanged)

The existing recommendation system generates candidate content. This prototype does not modify candidate generation.

### Intent-Aware Re-Ranking

Re-ranking applies multiplier-based modifiers based on the intent signals:

```python
def apply_intent_rerank(candidates, signals):
    for content in candidates:
        score = content.base_score
        score *= compute_time_multiplier(content, signals.time)
        score *= compute_viewer_multiplier(content, signals.viewer)
        score *= compute_energy_multiplier(content, signals.energy)
        score *= compute_device_multiplier(content, signals.device)
        score *= compute_prophecy_boost(content, signals.prophecy)
        score += compute_diversity_penalty(content, ranked_so_far)
        content.final_score = clamp(score, 0, 1)
    return sorted(candidates, key=lambda c: c.final_score, reverse=True)
```

### Diversity & Rotation Enforcement

After intent re-ranking:

1. **Genre Diversity**: Duplicate genre penalty increases with each consecutive same-genre item
2. **Hard Safety Gate**: Adult content blocked entirely for kids viewer profiles
3. **Calm Closer**: Prophecy agent amplifies calm content near scheduled bedtime

---

## Embeddings & Content Graph

### Content Embeddings

Each title has a multi-dimensional embedding capturing:

| Dimension | Example Signals |
|-----------|----------------|
| Energy/Pacing | Scene cut frequency, audio dynamics, action density |
| Emotional Tone | Sentiment analysis, theme classification |
| Educational Value | Learning objectives, curriculum alignment |
| Visual Stimulation | Color saturation, motion intensity |
| Social Themes | Cooperation, conflict resolution, friendship |

### Content Graph

```
┌─────────────┐     similar_tone     ┌─────────────┐
│   Bluey     │◄────────────────────►│  Peppa Pig  │
└─────────────┘                      └─────────────┘
       │                                    │
       │ calmer_alternative                 │ same_universe
       ▼                                    ▼
┌─────────────┐                      ┌─────────────┐
│ Bluey:      │                      │ Peppa Pig:  │
│ Sleepytime  │                      │ Bedtime     │
└─────────────┘                      └─────────────┘
```

---

## Performance, Reliability & Fallbacks

### Latency Constraints

| Component | Target | Budget |
|-----------|--------|--------|
| Intent inference | < 10ms | Lookup + simple rules |
| Re-ranking | < 30ms | Score computation |
| Total overhead | < 50ms | On top of existing rec latency |
| End-to-end | < 100ms | Full response |

### Fallback Hierarchy

```
Intent-Aware Ranking (primary)
    │
    ├─► Intent service timeout → Standard Kids ranking
    │
    ├─► Re-ranking failure → Return unmodified candidates
    │
    └─► Complete failure → Static curated fallback rows
```

---

## Privacy & Trust Considerations

| Principle | Implementation |
|-----------|---------------|
| Session-scoped intent | Intent objects are not persisted beyond the session |
| No child behavioral modeling | We model parent preferences, not child viewing patterns |
| Aggregation over personalization | Insights derived from cohorts, not individuals |
| COPPA-safe defaults | All data handling assumes child presence |

---

## Prototype Scope & Limitations

### What This Prototype Includes

- **Parent UI Flow**: Intent setup wizard, curated home, kid browse, content detail
- **Interactive Demo**: Multi-platform re-ranking with tweakable signals and live formula
- **Visual Design**: Netflix-inspired dark theme with time-based ambient gradients
- **Mock Data**: 40 items across 5 platform catalogs with intent-relevant metadata

### What This Prototype Does Not Include

- Real recommendation backend connection
- Actual content embeddings or ML models
- Production authentication or profile management
- A/B testing infrastructure

---

## Why This Matters

### For Parents
Intent-aware ranking shifts the burden from parents to the system. Instead of browsing and filtering, parents express context once, and the system adapts.

### For Long-Term Trust
Intent-aware ranking builds trust by aligning incentives: the system respects stated boundaries, recommendations support healthy routines, and transparency features explain "why this content."

### For Engineering
This design integrates incrementally with no replacement of existing rec infrastructure, clean modifier layer with rollback capability, minimal latency overhead (< 50ms), and graceful degradation to proven systems.

---

## Technical Stack

- **React 18** with TypeScript
- **Tailwind CSS** for styling
- **Vite** for development and build
- **Radix UI** primitives for accessibility
- **Lucide React** for iconography

---

## Running the Prototype

```bash
npm install
npm run dev     # Development server on localhost:5173
npm run build   # Production build
```

Visit `/demo` for the interactive re-ranking demo.

---

## License

MIT

---

*Built to demonstrate how thoughtful systems design can make streaming better for families.*
