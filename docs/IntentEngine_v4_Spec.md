# Intent Engine V4 — Agentic Intent Orchestration

## Status

**Proposed V4**

V4 evolves Intent Engine from deterministic context-aware re-ranking into an **agentic intent orchestration system with deterministic execution**.

The central architectural principle is:

> **Agents understand goals and create plans. Deterministic systems validate, enforce, rank, and execute them.**

V4 MUST NOT replace deterministic ranking with LLM-generated rankings.

---

# 1. Problem

V3 answers:

> Given a set of context signals, how should these candidates be ranked?

Example:

```text
viewer = kids
energy = 0.15
time = bedtime
device = television
```

The ranking engine deterministically produces an ordered result.

Real users rarely think in those parameters.

They express goals:

```text
"The kids are wired and bedtime is in an hour.
Help them wind down."
```

This contains:

- current state
- desired future state
- time horizon
- implicit safety requirements
- multiple stages of intent

V4 adds an agentic layer capable of translating that goal into a structured, validated, time-aware plan.

The deterministic Intent Engine then executes that plan.

---

# 2. V4 Thesis

Intent Engine becomes a boundary between:

```text
PROBABILISTIC REASONING

Human Goal
    ↓
Context Understanding
    ↓
Intent Planning
    ↓
Structured IntentPlan

-------------------------
DETERMINISTIC BOUNDARY
-------------------------

Schema Validation
    ↓
Policy / Safety Enforcement
    ↓
Domain Adapter
    ↓
Ranking Engine
    ↓
Ranked Results
    ↓
Structured Explanation

-------------------------
OBSERVATION BOUNDARY
-------------------------

Outcome Event
    ↓
Goal Evaluation
    ↓
Plan Continue / Adjust / Complete
```

The agent MAY propose intent.

The agent MUST NOT:

- directly assign candidate scores
- bypass safety rules
- override blocked candidates
- mutate ranking formulas
- silently invent unsupported signals
- directly choose the winning candidate

---

# 3. Goals

V4 should demonstrate five capabilities.

### G1 — Natural-language goals

Accept:

```text
"The kids need to settle down before bed."
```

instead of requiring users to configure every signal manually.

### G2 — Structured planning

Convert goals into a typed `IntentPlan`.

### G3 — Multi-step intent

Intent may evolve over time.

Example:

```text
high energy
    ↓
moderate
    ↓
calm
    ↓
bedtime
```

### G4 — Deterministic execution

Every actual ranking decision continues through the existing deterministic ranking infrastructure.

### G5 — End-to-end observability

A developer must be able to inspect:

```text
user request
→ agent interpretation
→ assumptions
→ plan
→ validation
→ safety decisions
→ scoring
→ ranking
→ outcome
```

---

# 4. Non-Goals

V4 is NOT:

- autonomous general-purpose AI
- an LLM recommendation engine
- reinforcement learning
- personalized ML ranking
- a replacement for the existing domain adapters
- a multi-agent swarm
- an attempt to make every component an "agent"

Avoid unnecessary agent abstraction.

V4 should initially contain **one orchestrator with specialized deterministic components**, not several independent LLM agents communicating with one another.

---

# 5. Core Architecture

```text
┌────────────────────────────────────┐
│             USER GOAL              │
│ "Kids are wired. Bed in an hour."  │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│         CONTEXT INTERPRETER        │
│ Rules first + optional LLM         │
│                                    │
│ Extracts:                          │
│ - viewer                           │
│ - current state                    │
│ - desired state                    │
│ - horizon                          │
│ - constraints                      │
│ - assumptions                      │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│           INTENT PLANNER           │
│                                    │
│ Creates typed IntentPlan           │
│ with one or more IntentSteps       │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│          PLAN VALIDATOR            │
│                                    │
│ Schema validation                  │
│ Supported signal validation        │
│ Confidence checks                  │
│ Policy checks                      │
│ Safe defaults                      │
└─────────────────┬──────────────────┘
                  ↓
══════════ DETERMINISTIC BOUNDARY ══════════
                  ↓
┌────────────────────────────────────┐
│         INTENT ORCHESTRATOR        │
│                                    │
│ Select active IntentStep           │
│ Resolve current context            │
│ Trigger scheduled transitions      │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│          SAFETY / POLICY           │
│                                    │
│ Hard constraints FIRST             │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│           DOMAIN ADAPTER           │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│        EXISTING RANKING ENGINE     │
│                                    │
│ Deterministic scoring              │
│ Diversity                          │
│ Tie breaking                       │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│          RANKED OUTPUT             │
│ Scores + explanation + trace       │
└─────────────────┬──────────────────┘
                  ↓
┌────────────────────────────────────┐
│          OUTCOME OBSERVER          │
│                                    │
│ What happened?                     │
│ Did state move toward goal?        │
└─────────────────┬──────────────────┘
                  ↓
            Continue / Adjust
              / Complete
```

---

# 6. Core Data Contracts

## 6.1 GoalRequest

```python
class GoalRequest(BaseModel):
    text: str
    domain: str
    timestamp: datetime

    explicit_context: dict[str, Any] = {}
    session_id: str | None = None
```

Example:

```json
{
  "text": "The kids are wired and bedtime is in an hour.",
  "domain": "streaming",
  "timestamp": "2026-10-06T19:00:00",
  "explicit_context": {
    "viewer": "kids"
  }
}
```

---

# 7. IntentPlan

This becomes the primary V4 contract.

```python
class IntentPlan(BaseModel):
    plan_id: str

    domain: str

    objective: str

    current_state: dict[str, Any]

    desired_state: dict[str, Any]

    constraints: list["IntentConstraint"]

    steps: list["IntentStep"]

    assumptions: list[str]

    confidence: float

    created_at: datetime

    expires_at: datetime | None = None

    planner_version: str
```

`created_at` is authoritative execution metadata. It MUST be populated from
trusted server/application time supplied at the deterministic planning
boundary, never copied from natural-language interpretation or generated by an
LLM.

Example:

```json
{
  "plan_id": "plan_123",

  "domain": "streaming",

  "objective": "wind_down",

  "current_state": {
    "viewer": "kids",
    "energy": 0.85
  },

  "desired_state": {
    "energy": 0.10
  },

  "constraints": [
    {
      "type": "viewer_safety",
      "value": "kids",
      "hard": true
    }
  ],

  "steps": [
    {
      "offset_minutes": 0,
      "intent": {
        "energy": 0.55,
        "tone": "familiar"
      }
    },
    {
      "offset_minutes": 25,
      "intent": {
        "energy": 0.30,
        "tone": "calm"
      }
    },
    {
      "offset_minutes": 50,
      "intent": {
        "energy": 0.10,
        "tone": "soothing"
      }
    }
  ],

  "assumptions": [
    "Bedtime occurs approximately 60 minutes from request."
  ],

  "confidence": 0.91,

  "planner_version": "v4.0"
}
```

---

# 8. IntentStep

```python
class IntentStep(BaseModel):
    step_id: str

    offset_minutes: int

    intent: dict[str, Any]

    transition_reason: str

    completion_condition: dict[str, Any] | None = None
```

The step contains intent.

It does NOT contain ranked items.

Bad:

```json
{
  "recommended_title": "Bluey"
}
```

Good:

```json
{
  "energy": 0.15,
  "tone": "soothing",
  "runtime_preference": "short"
}
```

Candidate selection remains the ranking engine's responsibility.

---

# 9. IntentConstraint

```python
class IntentConstraint(BaseModel):
    type: str
    value: Any
    hard: bool = False
    source: str
```

Sources:

```text
USER
SYSTEM
DOMAIN
INFERRED
```

Example:

```json
{
  "type": "viewer_maturity",
  "value": "kids",
  "hard": true,
  "source": "USER"
}
```

A hard constraint MUST NOT be overridden by the planner.

---

# 10. Context Interpreter

Introduce:

```text
intent_engine/agentic/context_interpreter.py
```

Responsibility:

```text
GoalRequest
     ↓
ContextInterpretation
```

Example:

```python
class ContextInterpretation(BaseModel):
    objective: str

    entities: dict[str, Any]

    explicit_constraints: list[IntentConstraint]

    inferred_context: dict[str, Any]

    assumptions: list[str]

    missing_information: list[str]

    confidence: float
```

---

# 11. Rules First

Preserve the existing project philosophy.

The pipeline SHOULD attempt deterministic interpretation first.

```text
GoalRequest
      ↓
Rules Interpreter
      ↓
Enough confidence?
   /          \
 YES          NO
 ↓             ↓
continue    Optional LLM
```

Examples that do not require an LLM:

```text
"bedtime"
"keep it calm"
"kids"
"under 30 minutes"
"family movie"
```

LLM fallback handles compositional requests:

```text
"The kids are bouncing off the walls but we're trying
to have them asleep by eight."
```

---

# 12. Planner

Introduce:

```text
intent_engine/agentic/planner.py
```

Interface:

```python
class IntentPlanner(Protocol):

    def create_plan(
        self,
        interpretation: ContextInterpretation,
        domain: str,
        now: datetime,
        authoritative_constraints: Sequence[IntentConstraint] = (),
    ) -> IntentPlan:
        ...
```

`now` and `authoritative_constraints` are trusted caller inputs. Authoritative
constraints originate from authenticated profile/session state, system policy,
domain policy, or other trusted application context. Constraints emitted by a
probabilistic interpretation remain non-authoritative even if their payload
claims a privileged source.

Implementations:

```text
RuleBasedIntentPlanner
LLMIntentPlanner
```

Recommended execution:

```text
RuleBasedIntentPlanner
        ↓
Can represent request?
     /       \
   yes        no
    ↓          ↓
return     LLMIntentPlanner
```

---

# 13. Plan Validator

Introduce:

```text
intent_engine/agentic/validator.py
```

This is one of the most important V4 components.

Every plan MUST pass validation before execution.

Validation includes:

### Schema validation

Is the plan structurally valid?

### Signal validation

Are requested signals supported by the canonical domain capabilities, and are
they classified explicitly as applied or observational during normalization?

### Range validation

Example:

```text
energy = 4.7
```

must fail when allowed range is:

```text
0 <= energy <= 1
```

### Constraint validation

Planner cannot weaken hard constraints.

### Temporal validation

Steps must be ordered.

```text
0
25
50
```

Valid.

```text
0
50
25
```

Invalid.

### Plan-size validation

Initial limit:

```text
MAX_PLAN_STEPS = 5
```

Prevents unnecessarily complicated plans.

---

# 14. Fail-Safe Behavior

Invalid agent output MUST NOT propagate into ranking.

Pipeline:

```text
LLM output
   ↓
parse
   ↓
schema validation
   ↓
semantic validation
   ↓
policy validation
   ↓
VALID?
 /    \
yes    no
↓       ↓
execute safe deterministic fallback
```

Fallback:

```text
explicit user signals
+
domain defaults
+
base ranking
```

Never:

```text
invalid agent response
→ best guess
→ ranking
```

---

# 14A. Deterministic Adapter Normalization

Before orchestration can execute a validated plan, canonical V4 vocabulary
must cross an explicit deterministic boundary:

```text
validated canonical execution context
+ separately authenticated hard constraints
        ↓
PlanIntentNormalizer
        ↓
NormalizedAdapterInput
  - domain
  - resolved_intent
  - hard_constraints
  - observational_signals
```

`resolved_intent` is the vocabulary consumed by adapter scoring methods such
as `compute_multipliers`. It is not raw input for `resolve_intent`.

For the initial streaming pilot:

| Canonical V4 value | Normalized result |
|---|---|
| `energy` | `resolved_intent.energy_level`, unchanged on the 0-to-1 scale |
| `viewer` | `resolved_intent.viewer_profile` |
| `intent_type` | `resolved_intent.intent_type` |
| `time_bucket` | `resolved_intent.time_bucket` |
| `tone` | `observational_signals.tone` |
| `runtime_preference` | `observational_signals.runtime_preference` |
| trusted `viewer_safety`, `viewer_maturity`, or `maturity_gate` | `hard_constraints.maturity_gate` |

The normalizer MUST NOT select an active step, read the clock, inspect
candidates, call adapters, rank, authenticate source labels, invent a missing
signal, or derive new policy. Authority comes from the separate trusted
constraint channel, not from `source` or `hard` fields embedded in plan data.
Soft and interpreted constraints never enter `hard_constraints`.

`viewer_profile` and `maturity_gate` remain independent. A maturity policy
MUST NOT be converted into a soft viewer-ranking signal. The streaming adapter
currently implements only the `maturity_gate=kids` hard-gate behavior, so other
maturity values must fail closed until their execution semantics exist.

Phase 3B owns the deterministic merge of `IntentPlan.current_state` with the
active step, with the active step overriding ordinary intent signals. This is
necessary because most Phase 2 steps inherit `viewer` from plan state rather
than repeating it. Authenticated profile context is a separate trusted input
and overrides protected profile fields such as `viewer`; neither interpreted
plan state nor a step may impersonate the active profile.

Prophecy input uses its own inbound normalization. Finite, non-boolean
`energyLevel` values on the 0-to-100 scale become canonical `energy` on the
0-to-1 scale. Canonical `energy` and the existing `energy_level` custom-schedule
spelling are explicit 0-to-1 forms; simultaneous energy spellings are
ambiguous and must fail. Other bounded JSON fields remain quarantined as
observable metadata until a later phase deliberately consumes them. Prophecy
normalization cannot produce authoritative constraint or time outputs;
similarly named input fields remain observational.

The current `DomainRankingEngine.rank(RankingRequest)` path cannot carry
adapter-specific resolved fields, and `StreamingAdapter.resolve_intent` does
not honor an explicit `intent_type`. Phase 3C therefore requires an additive
resolved-intent execution seam while preserving existing `rank()` behavior.

---

# 15. Intent Orchestrator

Introduce:

```text
intent_engine/agentic/orchestrator.py
```

The orchestrator owns plan execution.

```python
class IntentOrchestrator:

    def start_plan(...):
        ...

    def active_step(...):
        ...

    def advance(...):
        ...

    def execute(...):
        ...

    def observe(...):
        ...

    def complete(...):
        ...
```

The orchestrator does NOT rank candidates itself.

Instead:

```python
step = orchestrator.active_step(plan, now)

context = orchestrator.resolve_context(plan, step)

normalized = normalizer.normalize(
    domain=plan.domain,
    canonical_intent=context,
    authoritative_constraints=trusted_constraints,
)

result = domain_engine.rank_resolved(  # proposed additive Phase 3C seam
    domain=plan.domain,
    resolved_intent=normalized.resolved_intent,
    constraints=normalized.hard_constraints,
    candidates=candidates,
)
```

The actual repository component is `DomainRankingEngine`; the older
`RankingEngine` remains unchanged. The illustrated `rank_resolved` method does
not exist yet and belongs to Phase 3C.

---

# 16. Prophecy Agent V4

The existing Prophecy Agent remains a source of temporal schedule/context
signals. `IntentOrchestrator` owns active-step selection.

V3:

```text
time
→ scheduled intent shift
```

V4:

```text
time + schedule
→ ProphecyContextNormalizer
→ advisory canonical context

IntentPlan + trusted time
→ IntentOrchestrator
→ active IntentStep
```

Example:

```text
19:00

energy=.55

        ↓

19:25

energy=.30

        ↓

19:50

energy=.10
```

The Prophecy Agent MUST NOT create arbitrary ranking changes or activate plan
steps directly. The orchestrator may use separately normalized Prophecy context
without granting it policy or timestamp authority.

---

# 17. Outcome Events

Introduce:

```python
class OutcomeEvent(BaseModel):

    event_type: str

    timestamp: datetime

    plan_id: str

    step_id: str

    metadata: dict[str, Any]
```

Examples:

```text
ITEM_SELECTED
CONTENT_STARTED
CONTENT_COMPLETED
CONTENT_STOPPED
USER_OVERRIDE
PLAN_CANCELLED
SESSION_ENDED
```

V4 does NOT need behavioral ML.

Events initially exist for:

- observability
- plan evaluation
- demo state
- future experimentation

---

# 18. Outcome Evaluation

Introduce:

```text
intent_engine/agentic/outcome_evaluator.py
```

The evaluator answers:

```text
Did execution appear consistent with the stated goal?
```

Initially use deterministic heuristics.

Example:

```python
if objective == "wind_down":
    if selected_item.energy_score <= active_step.intent["energy"]:
        status = "ON_TRACK"
```

Statuses:

```text
ON_TRACK
OFF_TRACK
UNKNOWN
COMPLETE
```

Do NOT claim causal success.

The system may say:

```text
Execution matched the intended low-energy target.
```

It should NOT say:

```text
The recommendation caused the child to calm down.
```

without evidence.

---

# 19. Execution Trace

Every V4 request should generate a trace.

```python
class ExecutionTrace(BaseModel):

    trace_id: str

    goal_request: GoalRequest

    interpretation: ContextInterpretation

    plan: IntentPlan

    validation_results: list

    active_step: IntentStep

    safety_decisions: list

    ranking_trace: Any

    outcome_events: list[OutcomeEvent]

    latency: dict[str, float]
```

This is a major engineering artifact.

The system should be inspectable from request to result.

---

# 20. API

Keep existing `/rank`.

Add:

```text
POST /v4/plan
POST /v4/execute
POST /v4/observe

GET /v4/plans/{plan_id}
GET /v4/traces/{trace_id}
```

---

# 21. POST /v4/plan

Request:

```json
{
  "text": "The kids are wired and bedtime is in an hour.",
  "domain": "streaming",
  "context": {
    "viewer": "kids"
  }
}
```

Response:

```json
{
  "plan_id": "plan_123",

  "objective": "wind_down",

  "confidence": 0.91,

  "assumptions": [
    "Bedtime is approximately 60 minutes away."
  ],

  "steps": [
    {
      "offset_minutes": 0,
      "energy": 0.55
    },
    {
      "offset_minutes": 25,
      "energy": 0.30
    },
    {
      "offset_minutes": 50,
      "energy": 0.10
    }
  ]
}
```

---

# 22. POST /v4/execute

Request:

```json
{
  "plan_id": "plan_123",
  "candidates": [...]
}
```

Response:

```json
{
  "trace_id": "trace_789",

  "active_step": {
    "step_id": "step_1",
    "objective": "reduce_energy"
  },

  "ranking": [...],

  "explanation": {
    "plan_reason":
      "Current step favors familiar, moderate-energy content.",

    "ranking_reason":
      "Candidate ranked first based on deterministic signal multipliers."
  }
}
```

---

# 23. POST /v4/observe

Request:

```json
{
  "plan_id": "plan_123",
  "step_id": "step_1",
  "event_type": "CONTENT_COMPLETED",
  "metadata": {
    "candidate_id": "bluey_s4"
  }
}
```

Response:

```json
{
  "plan_status": "ACTIVE",
  "evaluation": "ON_TRACK",
  "next_transition_minutes": 7
}
```

---

# 24. Frontend V4

Do NOT redesign the entire frontend.

Add an **Agentic Mode** to the existing demo.

Current:

```text
Context Presets
Signal Sliders
Before / After
Formula
```

V4 adds:

```text
┌───────────────────────────────────────┐
│ What are you trying to accomplish?    │
│                                       │
│ Kids are wired and bedtime is in      │
│ an hour. Help them wind down.         │
│                                       │
│              [Create Plan]            │
└───────────────────────────────────────┘
```

Then show:

```text
UNDERSTOOD

Viewer
Kids

Current State
High energy

Goal
Wind down

Time Horizon
60 minutes

Confidence
91%
```

Then:

```text
PLAN

NOW
Moderate / familiar

25 MIN
Calm

50 MIN
Soothing / short

60 MIN
End session
```

---

# 25. Trace UI

Add a collapsible:

```text
WHY DID THIS HAPPEN?
```

Display:

```text
1. User Goal

"The kids are wired..."

↓

2. Agent Interpretation

objective = wind_down
viewer = kids
horizon = 60m

↓

3. Active Plan Step

energy_target = .30

↓

4. Safety

TV-MA → BLOCKED

↓

5. Ranking

Bluey

base       .58
time       .91
viewer    1.20
energy     .90
device    1.10
prophecy  1.32

final      .83

↓

6. Outcome

CONTENT_STARTED
```

This should become the centerpiece of the V4 demo.

---

# 26. Explainability Contract

Separate two types of explanation.

### Agent explanation

Why did the system infer this intent?

Example:

```text
A one-hour bedtime horizon and the phrase
"wind down" produced a progressive low-energy plan.
```

### Ranking explanation

Why did candidate X rank above candidate Y?

This remains deterministic and comes from the existing scoring engine.

Never mix the two.

That distinction is architecturally important.

---

# 27. Security / Safety Invariants

V4 introduces probabilistic input into a deterministic system.

Therefore enforce:

### Invariant 1

LLM output is untrusted input.

### Invariant 2

Hard constraints execute before ranking.

### Invariant 3

Agent output cannot modify system policies.

### Invariant 4

Agent output cannot modify ranking implementation.

### Invariant 5

Unknown applied or execution signals are rejected. Unrecognized metadata may
only be quarantined observationally and cannot affect execution without a
reviewed capability mapping.

### Invariant 6

Missing information is resolved through explicit, observable deterministic
defaults or safe fallback behavior.

### Invariant 7

Agent failure falls back safely.

### Invariant 8

Every agent-generated assumption is observable.

---

# 28. Determinism Contract

Given:

```text
validated IntentPlan
+
timestamp
+
candidate set
+
domain adapter version
+
ranking engine version
```

the ranking output MUST be reproducible.

The planner itself does not need to be deterministic.

The **execution layer does**.

This distinction should be documented prominently.

---

# 29. Suggested Project Structure

```text
backend/
└── intent_engine/
    ├── agentic/
    │   ├── __init__.py
    │   ├── capabilities.py
    │   ├── schemas.py
    │   ├── context_interpreter.py
    │   ├── planner.py
    │   ├── normalizer.py
    │   ├── validator.py
    │   ├── orchestrator.py
    │   ├── outcome_evaluator.py
    │   └── trace.py
    │
    ├── core/
    │   ├── adapter_protocol.py
    │   └── domain_engine.py
    │
    ├── adapters/
    │
    ├── ranking_engine.py
    ├── prophecy_agent.py
    ├── llm_adapter.py
    └── api.py
```

Keep agentic code isolated from the ranking core.

---

# 30. Testing Strategy

The existing test suite MUST remain green.

V4 should add tests in layers.

## Unit Tests

### IntentPlan

```text
valid plan accepted
invalid energy rejected
unknown signal rejected
unordered steps rejected
too many steps rejected
expired plan rejected
```

### Validator

```text
hard constraint cannot be weakened
unsupported signal fails
LLM garbage fails safely
missing required semantic field fails; planner-owned defaults remain explicit
```

### Orchestrator

```text
correct step at T+0
correct step at T+25
correct step at T+50
expired plan stops execution
```

### Safety

```text
kids plan cannot surface adult content
planner cannot override maturity gate
malicious prompt cannot alter policy
```

---

# 31. Determinism Tests

This is critical.

```python
def test_same_validated_plan_produces_same_ranking():

    result_a = execute(plan, candidates, timestamp)

    result_b = execute(plan, candidates, timestamp)

    assert result_a == result_b
```

Also:

```text
same plan
same timestamp
same candidates
same engine version

→ identical ordering
→ identical scores
→ identical explanation
```

---

# 32. Agent Failure Tests

Test:

```text
timeout
malformed JSON
missing fields
unsupported objective
hallucinated signal
invalid range
policy override attempt
empty response
```

Every case should produce:

```text
SAFE_FALLBACK
```

rather than an HTTP 500 or unsafe ranking.

---

# 33. Integration Tests

Example:

```text
"The kids are wired and bedtime is in an hour."
```

Assert:

```text
GoalRequest accepted

IntentPlan created

objective == wind_down

viewer == kids

multiple steps exist

energy decreases across steps

plan validates

adult content blocked

ranking deterministic

trace generated
```

---

# 34. Agentic Evaluation Suite

Create:

```text
tests/evals/
```

with approximately 25 canonical goals.

Examples:

```text
"Keep the kids calm before bed."

"We have 20 minutes before school."

"Family movie night."

"I need something quiet while the baby sleeps."

"Feed four people for under $50."

"I need the fastest reliable ride to the airport."

"Find a useful gift under $40."
```

Each eval defines acceptable intent properties.

Do NOT assert exact LLM wording.

Assert contracts.

Example:

```python
assert plan.objective == "wind_down"

assert any(
    constraint.type in {"viewer_safety", "viewer_maturity", "maturity_gate"}
    and constraint.value == "kids"
    and constraint.hard
    for constraint in plan.constraints
)

assert plan.steps[-1].intent["energy"] < plan.steps[0].intent["energy"]
```

---

# 35. Observability Metrics

Track:

```text
plan_creation_latency_ms

ranking_latency_ms

total_latency_ms

planner_fallback_rate

plan_validation_failure_rate

unsupported_signal_rate

safe_fallback_rate

average_plan_steps

user_override_rate

plan_completion_rate
```

Later:

```text
goal_success_proxy
```

should be added only when the project has a defensible definition of success.

---

# 36. V4 Demo Scenario

Use ONE polished scenario first.

Do not try to demonstrate all five verticals agentically.

## Streaming Pilot

User enters:

```text
"The kids are wired, but bedtime is in an hour."
```

System displays:

```text
GOAL

Wind down before bedtime
```

Then:

```text
PLAN

7:00 PM
Moderate familiar content

7:25 PM
Calm content

7:50 PM
Short soothing content

8:00 PM
Session complete
```

Then execute ranking.

Show:

```text
Engagement Ranking

1 ...
2 ...
3 ...
...
8 Bluey
```

versus:

```text
Intent Ranking

1 Bluey ↑7
2 ...
3 ...
```

Then:

```text
WHY?

Agent:
Interpreted bedtime + high current energy
as a progressive wind-down goal.

Policy:
Kids profile blocked adult content.

Ranker:
Bluey aligned with viewer, energy,
runtime, time and prophecy signals.
```

That is the demo.

---

# 37. Build Sequence

## Phase 1 — Contracts

Build:

```text
GoalRequest
ContextInterpretation
IntentConstraint
IntentStep
IntentPlan
OutcomeEvent
ExecutionTrace
```

Add validation tests.

**Done:**

All contracts typed and tested.

Existing tests remain green.

---

## Phase 2 — Deterministic Planner

Implement:

```text
RuleBasedIntentPlanner
```

Support approximately five goals:

```text
wind_down
focus
family_time
quick_session
high_energy
```

No LLM yet.

**Done:**

Validated canonical interpretations generate valid plans deterministically.
Trusted caller time owns plan creation timestamps, and authoritative
constraints enter the planner separately from interpreted constraints.

---

## Phase 3 — Orchestrator

### Phase 3A — Normalization boundary

Implement:

```text
PlanIntentNormalizer
ProphecyContextNormalizer
```

Keep normalization pure, streaming-only, and unwired from ranking. The plan
normalizer is capability-checked; the Prophecy boundary validates energy
aliases/scales and quarantines all other bounded metadata observationally.

**Phase 3A done:** canonical streaming and Prophecy energy vocabularies are
normalized deterministically; observational signals and authoritative hard
constraints remain separated. Runtime execution is not yet wired.

### Phase 3B — Orchestrator core

Implement:

```text
IntentOrchestrator
```

Own trusted-time active-step selection, expiration, execution-time
revalidation, and the deterministic current-state/active-step merge.

### Phase 3C — Deterministic execution integration

Integrate additively with:

```text
ProphecyAgent
DomainRankingEngine
```

Preserve the existing `DomainRankingEngine.rank()` path and all ranking
behavior.

**Done:**

A multi-step plan can execute across simulated time.

---

## Phase 4 — Execution Trace

Implement full tracing.

**Done:**

One object explains the entire lifecycle:

```text
request
→ interpretation
→ plan
→ validation
→ safety
→ ranking
```

---

## Phase 5 — API

Implement:

```text
/v4/plan
/v4/execute
/v4/observe
/v4/traces
```

**Done:**

Streaming scenario works entirely through backend APIs.

---

## Phase 6 — Frontend Integration

This should also eliminate an existing architectural limitation:

the current demo ranks client-side instead of using the Python backend.

V4 should connect the Streaming pilot UI to the real API.

**Done:**

Frontend no longer simulates the V4 execution path.

---

## Phase 7 — Optional LLM Planner

Only now introduce the LLM.

Pipeline:

```text
rules
 ↓
insufficient?
 ↓
LLM
 ↓
schema
 ↓
validator
 ↓
orchestrator
```

**Done:**

Messy natural language works while malformed model output cannot affect deterministic execution.

---

## Phase 8 — Outcome Loop

Add:

```text
observe()
evaluate()
advance()
complete()
```

**Done:**

The demo visibly progresses through the intent plan.

---

# 38. V4 Scoreboard

V4 is complete when:

| Metric | Target |
|---|---:|
| Existing tests passing | 100% |
| V4 unit/integration tests | 75+ |
| Canonical goal evals | 25+ |
| Deterministic replay success | 100% |
| Invalid agent output safely handled | 100% |
| Hard-policy bypasses | 0 |
| Streaming backend integration | Complete |
| End-to-end execution trace | Complete |
| Multi-step plan demo | Complete |
| LLM required for core operation | No |

---

# 39. Definition of Done

A user can enter:

```text
"The kids are wired and bedtime is in an hour.
Help them wind down."
```

and Intent Engine:

1. interprets the goal,
2. exposes its assumptions,
3. creates a typed multi-step IntentPlan,
4. validates the plan,
5. preserves hard safety constraints,
6. activates the appropriate step,
7. passes structured intent into the existing deterministic engine,
8. ranks candidates deterministically,
9. explains both the agent interpretation and ranking calculation,
10. records an execution trace,
11. accepts outcome events,
12. advances the plan as time/context changes,
13. reproduces the same ranking from the same validated execution state.

At no point does an LLM directly choose the winning candidate.

---

# 40. V4 Positioning

V3:

> Deterministic, explainable intent-aware re-ranking.

V4:

> **Agentic intent planning with deterministic execution.**

Longer architecture description:

> Intent Engine converts human goals into validated, time-aware intent plans, then executes those plans through deterministic, domain-specific ranking infrastructure. Probabilistic reasoning interprets what the user wants; deterministic systems enforce policy, rank candidates, and explain exactly why each decision occurred.

---

# 41. Engineering Story

The important technical problem V4 demonstrates is not:

> "I added an AI agent."

It is:

> **How do you safely put probabilistic reasoning in front of deterministic decision infrastructure without sacrificing reproducibility, policy enforcement, debuggability, or graceful degradation?**

The architecture answers that with:

```text
typed contracts
+
trust boundaries
+
schema validation
+
policy enforcement
+
deterministic execution
+
temporal orchestration
+
fallback behavior
+
end-to-end tracing
```

That is the core of V4.
