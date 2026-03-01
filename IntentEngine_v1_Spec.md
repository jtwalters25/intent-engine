# Intent Engine v1 Spec

## Problem

Parents spend significant time manually filtering streaming content for their children. Recommendation systems optimize for engagement, not parental intent, leading to friction, wasted time, and missed learning or wellness goals.

## Existing Solutions Fail

Current streaming platforms rely on personalization, ML, or randomness. These approaches:
- Prioritize engagement over family values
- Lack explainability and determinism
- Require ongoing manual input or complex profiles
- Fail to adapt to context (e.g., bedtime, learning, energy)

## Core Mechanism: Deterministic Re-Ranking

Intent Engine introduces a rules-first, deterministic re-ranking layer between retrieval and presentation:
- Parents set context once ("it's bedtime")
- System adapts recommendations in real-time, explainably
- No ML, personalization, or randomness required
- Soft constraints: intent boosts items, never filters
- Every ranking decision is accompanied by a human-readable explanation
- LLM adapter is optional and OFF by default; only translates language, never scores or ranks

## Persona Split: Parent vs Kid

- **Parent:** Sets intent, context, and constraints (e.g., energy, learning goals, time of day)
- **Kid:** Receives adapted recommendations, benefiting from parent-driven context without manual filtering

## Monetization Impact

Reducing friction for parent profiles by even 2% churn translates to ~$180M annual revenue opportunity for a platform at Netflix scale. "Set it and forget it" intent reduces churn, increases satisfaction, and unlocks new value for family streaming.

## Tradeoffs

- **Determinism vs. Flexibility:** Prioritizes predictable outcomes over personalization
- **Explainability vs. Complexity:** Rules-first approach ensures clarity, but limits advanced ML features
- **Safety:** Defaults degrade gracefully; hard constraints (age ratings) always apply first
- **No ML Dependency:** LLM is optional, never required for ranking
- **Composition over Complexity:** Advanced mode combines shallow factors; no single factor dominates without intent influence

---

> Use this document as a LinkedIn article, interview talking point, repo README section, or slide deck base. For more, see [Jeremiah Walters](https://www.linkedin.com/in/jeremiahwalters/) ([GitHub](https://github.com/jtwalters25)).
