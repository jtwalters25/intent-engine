# Netflix Kids – Parent-Intent Mode

A conceptual prototype demonstrating intent-aware content discovery for children's streaming. This project explores how parental intent signals—time of day, energy preferences, and learning goals—can be integrated into recommendation systems without sacrificing safety, performance, or engineering simplicity.

> **Note:** This is a design prototype intended to demonstrate systems thinking and backend architecture. It is not a production service.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Design Principles](#design-principles)
3. [High-Level System Architecture](#high-level-system-architecture)
4. [Intent Modeling](#intent-modeling)
5. [Ranking & Re-Ranking Strategy](#ranking--re-ranking-strategy)
6. [Embeddings & Content Graph](#embeddings--content-graph)
7. [Performance, Reliability & Fallbacks](#performance-reliability--fallbacks)
8. [Privacy & Trust Considerations](#privacy--trust-considerations)
9. [Prototype Scope & Limitations](#prototype-scope--limitations)
10. [Why This Matters](#why-this-matters)

---

## Project Overview

### The Problem

Current parental controls in streaming services focus primarily on **restriction and compliance**:
- Age gates and content ratings
- Watch time limits
- Profile locks

While necessary, these controls don't help parents with a more nuanced need: **intent-based guidance**. Parents often have contextual goals:

- "It's bedtime—I want something calm, not exciting."
- "They've been watching all day—show them something educational."
- "It's a rainy Saturday afternoon—active and fun is fine."

These intent signals are currently invisible to recommendation systems.

### What This Prototype Demonstrates

This project implements a **Parent-Intent Re-Ranking Layer**—a conceptual addition to existing recommendation infrastructure that:

1. Infers session context (time of day, child profile)
2. Accepts optional parent overrides (energy level, learning focus)
3. Re-ranks content candidates to match stated intent
4. Maintains all existing safety guarantees

The prototype UI demonstrates the parent-facing experience. The documentation below explains how the backend system would operate.

---

## Design Principles

These principles guide every architectural decision:

### 1. Safety First
Hard constraints (age ratings, content blocks) are applied **before** any ranking logic. Intent signals never override safety filters.

### 2. Defaults Over Configuration
The system auto-infers reasonable defaults from context (time of day, child age). Parents can override, but shouldn't have to.

### 3. Soft Intent Constraints
Intent preferences apply **weights**, not gates. A "calm bedtime" session still surfaces some variety—it doesn't hard-block all energetic content.

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
                   │  • Apply intent-based score modifiers           │
                   │  • Enforce diversity constraints                │
                   │  • Apply rotation rules (avoid repetition)      │
                   │  • Respect energy-level preferences             │
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
| Reuse existing candidate generation | Minimizes integration risk; leverages proven ML infrastructure |
| Intent as a modifier layer | Clean separation of concerns; easy to disable or A/B test |
| Session-scoped intent | Privacy-preserving; no persistent behavioral modeling of children |

---

## Intent Modeling

### Intent Object Structure

Parent intent is represented as structured, typed data:

```typescript
interface ParentIntent {
  // Session context
  sessionId: string;
  childProfileId: string;
  timestamp: ISO8601;
  
  // Inferred defaults (can be overridden)
  timeOfDay: 'morning' | 'afternoon' | 'evening' | 'bedtime';
  
  // Parent-specified preferences (0-100 scale)
  energyLevel: number;  // 0 = very calm, 100 = high energy
  
  // Optional learning focus areas
  learningFocus: Array<'stem' | 'literacy' | 'emotional' | 'social' | 'fun'>;
  
  // Age alignment (may differ from profile age)
  ageRange: string;  // e.g., "5-7"
  
  // Parent control flags
  prioritizeEducational: boolean;
  lowerStimulation: boolean;
  endOnCalmNote: boolean;
}
```

### Intent Inference Pipeline

```
Current Time → Time-of-Day Classification → Default Energy Level
     +
Child Profile → Age Range → Default Learning Focus
     +
Parent Overrides (optional) → Final Intent Object
```

### On LLM Usage

Large language models may be used for:
- Natural language translation ("I want something calm" → `energyLevel: 20`)
- Fallback intent parsing when structured input fails

LLMs are **never** given decision authority. All final ranking decisions use deterministic rules applied to structured intent data.

---

## Ranking & Re-Ranking Strategy

### Candidate Generation (Unchanged)

The existing recommendation system generates candidate content:
- Collaborative filtering based on similar profiles
- Content-based similarity
- Popularity signals within age-appropriate cohorts
- Editorial curation and seasonal content

This prototype does not modify candidate generation.

### Intent-Aware Re-Ranking

Re-ranking applies score modifiers based on the intent object:

```python
def apply_intent_rerank(candidates: List[Content], intent: ParentIntent) -> List[Content]:
    for content in candidates:
        base_score = content.recommendation_score
        
        # Energy alignment modifier
        energy_delta = abs(content.energy_level - intent.energyLevel)
        energy_modifier = 1.0 - (energy_delta / 100) * 0.4  # Max 40% penalty
        
        # Learning focus boost
        learning_boost = 1.0
        if intent.learningFocus:
            overlap = len(set(content.learning_tags) & set(intent.learningFocus))
            learning_boost = 1.0 + (overlap * 0.15)  # 15% boost per matching focus
        
        # Time-of-day appropriateness
        time_modifier = get_time_appropriateness(content, intent.timeOfDay)
        
        # Educational priority
        edu_boost = 1.2 if intent.prioritizeEducational and content.is_educational else 1.0
        
        # Final score
        content.intent_score = base_score * energy_modifier * learning_boost * time_modifier * edu_boost
    
    return sorted(candidates, key=lambda c: c.intent_score, reverse=True)
```

### Diversity & Rotation Enforcement

After intent re-ranking:

1. **Genre Diversity**: No more than 3 consecutive items from the same genre
2. **Recency Penalty**: Recently watched titles receive score decay
3. **Series Balancing**: Limit franchise over-representation
4. **Calm Closer**: If `endOnCalmNote` is true, ensure row endings skew calm

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

These embeddings enable similarity calculations beyond genre:
- "Shows with similar pacing to *Bluey*"
- "Calm alternatives to *Paw Patrol*"

### Content Graph

A graph structure captures relationships:

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

Graph traversal supports:
- "Show me calmer alternatives"
- "More like this, but educational"
- Safe exploration without jarring transitions

---

## Performance, Reliability & Fallbacks

### Latency Constraints

| Component | Target | Budget |
|-----------|--------|--------|
| Intent inference | < 10ms | Lookup + simple rules |
| Re-ranking | < 30ms | Score computation |
| Total overhead | < 50ms | On top of existing rec latency |
| End-to-end | < 100ms | Full response |

### Caching Strategy

Common intent profiles are pre-computed and cached:

```typescript
const CACHED_PROFILES = [
  'bedtime_calm_ages_4-6',
  'morning_energetic_ages_5-7',
  'afternoon_balanced_ages_3-5',
  // ... ~50 high-frequency combinations
];
```

Cache hit rate target: > 70% for intent-modified results.

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

**The safest system is the fallback system.**

Every degraded mode maintains age-appropriate, safety-filtered content. No failure path exposes inappropriate content.

---

## Privacy & Trust Considerations

### Data Handling Principles

| Principle | Implementation |
|-----------|---------------|
| Session-scoped intent | Intent objects are not persisted beyond the session |
| No child behavioral modeling | We model parent preferences, not child viewing patterns |
| Aggregation over personalization | Insights derived from cohorts, not individuals |
| COPPA-safe defaults | All data handling assumes child presence |

### What We Don't Do

- ❌ Track individual child viewing behavior for ad targeting
- ❌ Build persistent preference models for children
- ❌ Share intent data across profiles or households
- ❌ Use intent signals to increase engagement metrics

### What We Do

- ✅ Help parents express viewing context
- ✅ Surface content aligned with stated intent
- ✅ Forget session intent after session ends
- ✅ Default to maximum privacy when ambiguous

---

## Prototype Scope & Limitations

### What This Prototype Includes

- **UI Flow**: Parent-facing intent setup wizard
- **Visual Design**: Netflix-inspired dark theme with time-based ambient gradients
- **Conceptual UX**: Child selection, intent configuration, content transparency panels
- **Mock Data**: Sample show cards with intent-relevant metadata

### What This Prototype Does Not Include

- ❌ Real recommendation backend
- ❌ Actual content embeddings or ML models
- ❌ Production authentication or profile management
- ❌ Real-time re-ranking service
- ❌ A/B testing infrastructure

### Intended Use

This prototype is designed for:
- Demonstrating systems thinking to engineering teams
- Illustrating UX flows to product partners
- Documenting architectural decisions for future implementation
- Serving as a conversation starter, not a production blueprint

---

## Why This Matters

### For Parents

Current streaming experiences create decision fatigue:
- "What should the kids watch?"
- "Is this appropriate for bedtime?"
- "Are they just watching junk?"

Intent-aware ranking shifts the burden from parents to the system. Instead of browsing and filtering, parents express context once, and the system adapts.

### For Long-Term Trust

Engagement-optimized recommendations erode parental trust:
- Autoplay keeps kids watching past bedtime
- Algorithmic rabbit holes lead to questionable content
- Parents feel they're fighting the system

Intent-aware ranking builds trust by aligning incentives:
- The system respects stated boundaries
- Recommendations support healthy routines
- Transparency features explain "why this content"

### For Engineering

This design integrates incrementally:
- No replacement of existing rec infrastructure
- Clean modifier layer with rollback capability
- Minimal latency overhead (< 50ms)
- Graceful degradation to proven systems

The architecture respects the reality that recommendation systems are complex, ML-heavy, and require careful iteration. This proposal adds intent awareness without requiring a rewrite.

---

## Technical Stack (Prototype)

This UI prototype is built with:

- **React 18** with TypeScript
- **Tailwind CSS** for styling
- **Lucide React** for iconography
- **Radix UI** primitives for accessibility
- **Vite** for development

---

## Running the Prototype

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

---

## License

This is a conceptual prototype for demonstration purposes.

---

*Built to demonstrate how thoughtful systems design can make streaming better for families.*
