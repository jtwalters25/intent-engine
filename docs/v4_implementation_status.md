# V4 Implementation Status

## Current status

Phase 2, **deterministic rule-based intent planning**, is implemented on top of
the accepted Phase 1 contracts and validation foundation. The new code remains
additive and isolated under `intent_engine.agentic`; it does not call the
ranking engine, inspect, score, or select candidates, alter domain-adapter
behavior, or change an existing API.

Verification completed with 510 passing backend tests (274 pre-existing, 161
Phase 1, and 75 Phase 2 tests) plus the existing passing frontend test.

## Completed scope

- Added typed Pydantic contracts for `GoalRequest`,
  `ContextInterpretation`, `IntentConstraint`, `IntentStep`, `IntentPlan`,
  `OutcomeEvent`, and `ExecutionTrace`.
- Added a typed `ConstraintSource` with `USER`, `SYSTEM`, `DOMAIN`, and
  `INFERRED` values.
- Added intrinsic contract validation for required and non-blank fields,
  confidence values in the inclusive range 0 through 1, nonnegative temporal
  offsets, unique step IDs, strictly ordered steps, one to five plan steps,
  compatible plan timestamps, JSON-compatible constraint values, and
  nonnegative trace latency values. Dynamic JSON data is bounded to 64 nesting
  levels and 10,000 visited values so cyclic or adversarially deep structures
  fail validation instead of escaping as recursion errors.
- Added fail-closed semantic plan validation with structured validation issues.
  It validates domain-supported signals and constraints, signal types and
  ranges, plan expiration, preservation of authoritative hard constraints,
  conflicting constraint aliases/sources, and the prohibition on candidate
  selection or scoring fields in plan steps.
- Added an immutable, injectable domain-capability registry for the five
  existing domains. Validation does not import or execute ranking code.
- Added deterministic canonical JSON generation for validated plans.
- Kept the existing deterministic rankers, hard safety gates, domain adapters,
  Prophecy Agent, LLM adapter, and `/rank` API unchanged.
- Added a deterministic `RuleBasedIntentPlanner` for the streaming-domain
  pilot. It supports `wind_down`, `focus`, `family_time`, `quick_session`, and
  `high_energy` and produces only intent state and temporal progression.
- Added a runtime-checkable `IntentPlanner` protocol and stable, content-derived
  plan/step identifiers so identical inputs produce identical plans.
- Required trusted caller-supplied `now` for `created_at` and plan expiration;
  interpreted timestamps are ignored and cannot acquire execution authority.
- Kept authoritative constraints in a separate caller-supplied input. The
  planner preserves trusted hard constraints exactly and rejects attempts by
  interpreted data to claim hard, `SYSTEM`, or `DOMAIN` authority.
- Added explicit, observable defaults for safe missing values. Defaults are
  recorded in plan assumptions; missing information without a safe default
  fails closed.
- Routed both the draft and final planner result through the Phase 1 validator.

## Files added

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/agentic/capabilities.py`
- `backend/intent_engine/agentic/schemas.py`
- `backend/intent_engine/agentic/validator.py`
- `backend/tests/agentic/__init__.py`
- `backend/tests/agentic/test_schemas.py`
- `backend/tests/agentic/test_validator.py`
- `docs/v4_implementation_status.md`

No existing ranking, adapter, API, LLM, Prophecy Agent, or frontend files were
modified for Phase 1.

## Phase 2 files added or modified

Added:

- `backend/intent_engine/agentic/planner.py`
- `backend/tests/agentic/test_planner.py`

Modified:

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/agentic/schemas.py`
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No ranking, domain-engine, adapter, Prophecy Agent, LLM, API, or frontend code
was modified for Phase 2.

## Tests added

The Phase 1 tests cover:

- Valid contracts and valid plan acceptance.
- Required fields, forbidden extra fields, and isolated collection defaults.
- Confidence boundaries and invalid confidence values.
- Negative, duplicate, and unordered temporal steps.
- Empty plans, the five-step limit, and excessive plans.
- Creation/expiration ordering and expiration relative to an explicitly
  supplied validation time.
- Supported signal values, invalid ranges and types, and unknown signals.
- Rejection of candidate-selection and candidate-scoring keys in intent steps.
- Constraint sources, strict hard flags, malformed constraints, unknown
  constraints, semantic alias conflicts, and exact preservation of
  authoritative hard constraints.
- Payload parsing and structured schema/semantic validation errors.
- Outcome and trace contract construction.
- Serialization/deserialization round trips.
- Stable canonical representation across equivalent mapping insertion orders
  and repeated validation.

Test results:

- Phase 1 agentic tests: **161 passed**.
- Phase 2 planner tests: **75 passed**.
- All agentic tests: **236 passed**.
- Full backend suite: **510 passed** (274 existing plus 236 agentic).
- Frontend suite: **1 passed**.
- Combined repository test total: **511 passed**.
- Python bytecode compilation: **passed**.

The Phase 2 tests cover all five objectives, deterministic output and IDs,
trusted timestamp ownership, interpreted timestamp non-authority, explicit
defaults and their observable assumptions, unknown objectives/domains,
malformed interpretations, canonical vocabulary enforcement, authoritative
constraint preservation, interpreted constraint non-authority, Phase 1
validation of every returned plan, absence of a candidate input, monotonic
wind-down/high-energy progressions, and plan-step limits.

## Phase 2 default behavior

The planner uses defaults only when the corresponding value is absent; the
Pydantic contracts do not manufacture semantic intent:

- Current `energy`: `0.5` (neutral).
- `viewer`: `family`. This is an intent signal, not a safety-policy grant and
  does not replace a trusted maturity constraint.
- Objective horizons: `wind_down` 60 minutes, `focus` 45 minutes,
  `family_time` 90 minutes, `quick_session` 20 minutes, and `high_energy` 45
  minutes.

Each applied default is appended to `IntentPlan.assumptions`. The planner
rejects unknown entries in `missing_information` because it has no documented
safe default for them.

## Trust ownership

- **Time:** `RuleBasedIntentPlanner.create_plan` requires `now` from its trusted
  caller and uses it for `created_at`; `expires_at` is calculated from that
  value and the deterministic horizon. Timestamps embedded in interpreted
  entities or inferred context have no effect.
- **Constraints:** authoritative constraints are supplied separately from
  `ContextInterpretation`. They must already be typed, hard, and not
  `INFERRED`. Interpreted constraints may remain soft and carry only `USER` or
  `INFERRED` provenance; interpreted hard constraints and claims of `SYSTEM` or
  `DOMAIN` authority fail closed. A source enum value is provenance metadata,
  not proof of authority—the separate trusted input channel is the authority
  boundary.

## Deviations and clarifications from the proposed spec

- **Domain type:** Contract `domain` fields use the repository's existing
  `Domain` enum rather than an unconstrained string. This prevents plans for
  domains with no registered validation contract while reusing an established
  repository type.
- **Untrusted-input boundary:** Agentic models forbid unknown fields. Mutable
  collection defaults use `default_factory` rather than the mutable literals
  shown in the pseudocode.
- **Declared fields remain required:** The spec's JSON examples omit fields
  that its class declarations mark as required, including `created_at`,
  constraint `source`, step `step_id`, and `transition_reason`. The Phase 1
  contracts follow the declared schemas, not the abbreviated examples.
- **Explicit validation clock:** Expiration validation receives an injected
  `now` value. It does not read the system clock, which keeps validation and
  tests reproducible. Timestamp awareness must match before values are
  compared.
- **Canonical V4 signal names:** The capability registry uses V4-facing signal
  names, including streaming `energy` and `viewer`. It is separate from the
  current adapters, whose names differ. Translation into adapter input is
  intentionally deferred.
- **Separate capability registry:** Existing `DomainAdapter` implementations do
  not expose supported signal names, types, or ranges. Phase 1 therefore uses
  an injectable, immutable registry instead of extending the runtime adapter
  protocol and coupling validation to ranking implementations.
- **Typed constraint source:** `IntentConstraint.source` is a constrained enum
  rather than a free string, matching the four sources enumerated by the spec.
- **Temporal ordering:** "Ordered" is implemented as strictly increasing,
  nonnegative offsets. Step IDs must also be unique so later orchestration can
  address a step unambiguously.
- **Hard-constraint validation:** Whether a hard constraint was weakened cannot
  be determined from a plan alone. The validator accepts authoritative
  constraints separately and requires each authoritative hard constraint to
  be preserved exactly in the plan. The three maturity names used by the spec
  and existing adapters are treated as one semantic policy for conflict
  detection.
- **Required interpretation objective:** `ContextInterpretation.objective` is
  now a required non-optional string. The proposed `str | None` annotation
  conflicted with both `Field(...)` and the Phase 2 requirement that every
  supported interpretation identify an objective.
- **Narrow domain pilot:** Although the Phase 1 contracts cover all existing
  domains, the Phase 2 rule-based objective templates intentionally support
  only streaming. Other domains fail with `unsupported_domain` until their
  semantics are deliberately designed.
- **Planner trust inputs:** The planner protocol extends the original sketch
  with caller-supplied `now` and `authoritative_constraints`. This implements
  the reviewed trust-boundary decisions without adding orchestration.
- **Deterministic identifiers:** The repository has no applicable plan-ID
  convention, so IDs are SHA-256-derived from canonical plan semantics. This
  avoids random IDs breaking deterministic replay.
- **Interpretation remains out of scope:** Phase 2 accepts a validated
  `ContextInterpretation`; it does not convert natural language into one. The
  Phase 2 build-sequence wording was clarified accordingly.

## Technical debt and risks

- **Capability-registry drift:** Signal and constraint metadata currently lives
  beside, rather than on, domain adapters. It can drift as adapters evolve.
  A later phase should establish one source of truth without making validators
  execute ranking code.
- **Energy naming and scale:** The V4 contract uses `energy` on a 0-to-1 scale;
  domain adapters currently use `energy_level`, also as an implied 0-to-1
  value; Prophecy Agent templates use camel-case `energyLevel` on a 0-to-100
  scale. The Phase 3 boundary will need an explicit, tested conversion.
- **Constraint translation:** V4 represents constraints as typed objects, while
  existing adapters receive dictionaries such as `maturity_gate`,
  `block_explicit`, `surge_cap`, and `allergens`. Policy-authoritative
  translation and merge behavior remains undefined and must precede execution.
  In particular, future translation must pass only authoritative hard
  constraints to adapter hard-gate dictionaries; soft constraints must never
  become hard gates accidentally.
- **Capability versus consumption:** Some canonical V4 signals, such as
  streaming `tone` and `runtime_preference`, are valid plan vocabulary but are
  not consumed by the current adapter. Phase 3 must either translate them to a
  supported deterministic effect or explicitly leave them observational.
- **Planner/adapter vocabulary boundary:** The planner emits canonical V4
  `energy` (0-to-1) and `viewer`, while streaming adapters consume
  `energy_level` and `viewer_profile`, and Prophecy Agent emits `energyLevel`
  on a 0-to-100 scale. Direct wiring would silently drop or mis-scale intent.
- **Local objective vocabulary:** Phase 2 objective aliases are intentionally
  local to the planner. If a later deterministic context interpreter also owns
  aliases, the vocabulary must be centralized to prevent drift.
- **Constraint provenance enforcement:** Phase 2 separates trusted constraints
  by API channel, but only a future orchestrator can authenticate the profile,
  session, system, or domain-policy source before calling the planner.
- **Streaming-only behavior:** The objective names are broadly useful, but
  reusing the current templates for other domains would invent unreviewed
  semantics. Domain-specific templates remain necessary.
- **Loose trace internals:** `validation_results` and `safety_decisions` remain
  generic dictionaries and `ranking_trace` remains unconstrained because the
  spec does not define their structures. These should become explicit
  contracts during Phase 4.
- **Plan-level outcome events:** The proposed `OutcomeEvent` requires a
  `step_id`, although events such as `PLAN_CANCELLED` and `SESSION_ENDED` may be
  plan-scoped. This should be resolved before the outcome API is introduced.

## Recommended Phase 3

Implement a narrow deterministic `IntentOrchestrator` plus a pure,
domain-specific `PlanIntentNormalizer` boundary. Its outbound normalization
should consume only a validated active `IntentStep` and trusted hard
constraints, then produce the existing adapter input vocabulary without
ranking or policy decisions. For the initial streaming path it should:

1. map canonical `energy` directly to adapter `energy_level` on the 0-to-1
   scale;
2. map canonical `viewer` to adapter `viewer_profile` without weakening a
   trusted maturity gate;
3. deliberately translate `tone` and `runtime_preference` into supported
   adapter signals, or reject/record them as observational rather than silently
   dropping them;
4. translate only separately authenticated hard constraints into adapter hard
   gates such as `maturity_gate`.

Add a separate inbound context-normalization function for Prophecy Agent data:
`energyLevel / 100 -> energy`, with bounds checks, before planning. Do not put
that scale conversion in `PlanIntentNormalizer` or ranking.

Keep the normalizer pure, injectable, capability-checked, and covered by
round-trip/scale/boundary tests. Then have the orchestrator select the active
step by trusted time, validate again, normalize, and delegate candidate scoring
unchanged to the existing deterministic `DomainRankingEngine`. Do not add an
LLM planner in Phase 3.

## Intentionally deferred

- Context-interpreter behavior and probabilistic interpretation.
- Orchestration, active-step selection, normalization, and integration with
  Prophecy Agent, `DomainRankingEngine`, or the existing rankers (Phase 3).
- Full execution-trace creation and strongly typed trace internals (Phase 4).
- `/v4/plan`, `/v4/execute`, `/v4/observe`, plan retrieval, and trace retrieval
  APIs (Phase 5).
- Frontend Agentic Mode and frontend-to-backend execution wiring (Phase 6).
- Optional LLM planner, malformed-model-output recovery, and runtime safe
  fallback behavior (Phase 7).
- Outcome evaluation and the observe/advance/complete loop (Phase 8).
- Any change to ranking formulas, diversity behavior, hard safety gates,
  candidate selection, existing domain-adapter execution, or existing APIs.
