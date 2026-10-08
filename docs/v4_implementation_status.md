# V4 Implementation Status

## Current status

The Phase 3 deterministic plan-to-ranking path and its multi-step execution
criterion are complete for the streaming pilot. Phase 3C adds an internal,
keyword-only `DomainRankingEngine.rank_resolved` seam that consumes the
adapter-ready intent and authoritative hard constraints prepared by the
orchestrator. The legacy
`rank(RankingRequest)` path now delegates only its scoring stage to the same
private implementation; its intent resolution, response metadata, hard gates,
scoring formulas, diversity behavior, adapters, and `/rank` API remain
unchanged. The original Phase 3 heading also named Prophecy integration; that
runtime merge is an explicit, safety-motivated deviation until context
precedence is specified.

Verification completed with 765 passing backend tests (274 pre-V4, 447 through
Phase 3B, and 44 Phase 3C tests) plus the existing passing frontend test.

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
- Added a pure streaming `PlanIntentNormalizer` that maps canonical plan
  vocabulary into immutable resolved adapter intent, hard-constraint, and
  observational mappings. It does not import or execute adapters or ranking.
- Added a separate `ProphecyContextNormalizer` with explicit scale handling:
  `energyLevel` 0-to-100 becomes canonical `energy` 0-to-1; canonical `energy`
  and the existing custom-schedule `energy_level` spelling remain 0-to-1.
- Canonicalized the three maturity constraint aliases into the adapter's
  `maturity_gate`, but only through the separately supplied authoritative hard
  constraint channel. Soft, inferred, malformed, or conflicting authority
  fails closed.
- Kept `tone` and `runtime_preference` observable without assigning them an
  invented ranking effect.
- Restricted Phase 3A hard-gate output to `maturity_gate=kids`, the only
  maturity value the current streaming adapter actually enforces.
- Added a deterministic `IntentOrchestrator.prepare_execution` boundary that
  revalidates every plan at execution time using caller-supplied trusted time
  and separately supplied authoritative constraints.
- Added exact temporal selection of the latest started plan step, with
  fail-closed behavior before plan start, before the first step, at expiration,
  and for timezone-incompatible clocks.
- Added deterministic context precedence: validated `current_state`, then the
  active step for ordinary signals, then caller-authenticated profile context
  for the protected canonical `viewer` signal.
- Returned an immutable `PreparedPlanExecution` containing the active step,
  immutable canonical intent, and immutable `NormalizedAdapterInput`. It is an
  in-process value container, not proof of external authentication.
- Snapshotted and contract-revalidated authoritative constraints once before
  both plan validation and normalization, preventing mutable or stateful caller
  sequences from dropping a gate between the two boundaries.
- Rejected hard plan constraints not exactly corroborated by the separate
  authoritative channel, and rejected soft plan constraints that claim
  `SYSTEM` or `DOMAIN` provenance.
- Required a caller-authenticated kids profile to be paired with a separately
  authoritative kids maturity gate. This is a coherence check; the orchestrator
  does not derive policy from soft viewer intent.
- Made the prepared active step deeply immutable so it cannot diverge from the
  frozen canonical and normalized execution inputs.
- Normalized aware timestamp comparison and duration arithmetic to UTC instants
  so plan creation, expiration, and step selection remain correct across
  daylight-saving gaps and folds.
- Added `DomainRankingEngine.rank_resolved` for already-normalized intent and
  authoritative hard constraints. It bypasses `resolve_intent`, accepts only
  the streaming domain in this phase, takes bounded deep snapshots of its
  mappings and candidates, supplies pristine per-call adapter inputs, and
  accepts no plan, clock, profile, observational, Prophecy, or LLM inputs.
- Extracted the existing hard-gate, multiplier-chain, diversity, explanation,
  and response-building code into one private implementation used by both the
  legacy and resolved paths. No ranking formula was duplicated or changed.
- Demonstrated planner-to-orchestrator-to-ranking execution for the streaming
  wind-down plan at T+0, T+25, and T+50 with deterministic replay and an
  authoritative kids maturity gate applied at every step.

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

## Phase 3A files added or modified

Added:

- `backend/intent_engine/agentic/normalizer.py`
- `backend/tests/agentic/test_normalizer.py`

Modified:

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/agentic/capabilities.py`
- `backend/intent_engine/agentic/schemas.py`
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No orchestrator, ranking engine, adapter, Prophecy Agent, LLM, API, or frontend
code was modified for Phase 3A.

## Phase 3B files added or modified

Added:

- `backend/intent_engine/agentic/orchestrator.py`
- `backend/tests/agentic/test_orchestrator.py`

Modified:

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/agentic/planner.py`
- `backend/intent_engine/agentic/schemas.py`
- `backend/intent_engine/agentic/validator.py`
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No ranking engine, domain engine, adapter, Prophecy Agent, LLM, API, or
frontend code was modified for Phase 3B.

## Phase 3C files added or modified

Added:

- `backend/tests/core/test_domain_engine_resolved.py`
- `backend/tests/agentic/test_execution_integration.py`

Modified:

- `backend/intent_engine/core/domain_engine.py`
- `backend/intent_engine/agentic/normalizer.py` (documentation only)
- `backend/intent_engine/agentic/orchestrator.py` (documentation only)
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No adapter, legacy `RankingEngine`, Prophecy Agent, API, schema, planner, LLM,
or frontend behavior was modified for Phase 3C.

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
- Phase 3A normalization tests: **144 passed**.
- Phase 3B orchestrator tests: **65 passed**.
- Phase 3B cross-cutting time-ordering regression tests: **2 passed**.
- Phase 3C resolved-ranking tests: **42 passed**.
- Phase 3C execution-integration tests: **2 passed**.
- All agentic tests: **449 passed**.
- Full backend suite: **765 passed** (721 prior plus 44 Phase 3C tests).
- Frontend suite: **1 passed**.
- Combined repository test total: **766 passed**.
- Python bytecode compilation: **passed**.

The Phase 2 tests cover all five objectives, deterministic output and IDs,
trusted timestamp ownership, interpreted timestamp non-authority, explicit
defaults and their observable assumptions, unknown objectives/domains,
malformed interpretations, canonical vocabulary enforcement, authoritative
constraint preservation, interpreted constraint non-authority, Phase 1
validation of every returned plan, absence of a candidate input, monotonic
wind-down/high-energy progressions, and plan-step limits.

The Phase 3A tests cover canonical-to-adapter signal mappings, all five Phase 2
objectives, observational-signal isolation, unknown and candidate-selection
signals, signal ranges and types, deterministic and immutable results,
maturity alias canonicalization, authoritative-channel separation, duplicate
and conflicting constraints, fail-closed unsupported maturity semantics,
Prophecy scale conversion and ambiguity, current Prophecy defaults, and the
absence of candidate, clock, adapter, and authority inputs at the wrong
boundaries.

The Phase 3B tests cover exact active-step boundaries at T+0, T+25, and T+50,
sub-minute and expiration boundaries, pre-start/no-active-step failures,
timezone compatibility, execution-time mutation detection, deterministic
state/step/profile precedence, authoritative-channel isolation, malformed,
soft, and inferred authority, copy-safe and immutable outputs, deterministic
replay, one-pass constraint snapshots, forged authority rejection,
profile-policy coherence, injected capability registries, daylight-saving
fold/gap behavior, and the absence of candidate, ranker, adapter, Prophecy, or
system-clock inputs at the orchestration boundary.

The Phase 3C tests prove that resolved intent bypasses `resolve_intent`, exact
hard constraints reach the adapter gate, caller inputs are deeply snapshotted
without mutation, malformed or cyclic boundary shapes fail closed, and the
legacy path still resolves exactly once. Adversarial adapters cannot delete a
gate for a later candidate, mutate later intent, or leak item mutation into the
caller or response. Tests also reject post-construction-invalid candidates,
unreviewed non-streaming execution, mismatched adapter registration,
non-boolean gate results, invalid multiplier outputs, non-finite candidate
values, and score overflow. Both entry points share identical ranked-item
outputs for equivalent intent while preserving the multiplier product,
hard-gate behavior, explanations, stable ties, and global repeated-key
diversity behavior. End-to-end tests execute a streaming plan at T+0, T+25,
and T+50, reproduce identical ranked results, quarantine observational
signals, and verify that an adult candidate is marked blocked at every step.

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
  boundary. Phase 3B snapshots this channel once and rejects any hard plan
  constraint that is not exactly corroborated by it.
- **Execution time:** `IntentOrchestrator.prepare_execution` requires `now`
  explicitly, revalidates expiration against it, and never reads the system
  clock. It rejects execution before `created_at` and selects the latest step
  whose offset has begun.
- **Active profile:** authenticated active-profile context is a separate,
  required caller channel. For the streaming pilot it may contain only the
  canonical protected `viewer` signal, which takes final precedence over plan
  state and step intent. The orchestrator does not authenticate the mapping;
  that remains an application-boundary responsibility. A trusted kids profile
  without a separately authoritative kids maturity gate fails closed.
- **Resolved ranking:** `rank_resolved` is an in-process deterministic scoring
  seam, not an authentication boundary. Its mappings must come from the
  orchestrator's normalized result, and its hard-constraint dictionary retains
  only the authority established by the separate application-owned constraint
  channel. The method is not exposed through an API.

## Phase 3A normalization behavior

`PlanIntentNormalizer` accepts a caller-resolved canonical intent mapping. It
does not select an active step or merge plan state. Phase 3B now performs that
work atomically: `IntentPlan.current_state` is merged with the active step,
with step values winning for ordinary signals, and separately authenticated
profile context taking final precedence for protected `viewer` state.

| Canonical input | Phase 3A output |
|---|---|
| `energy` | resolved `energy_level` on the same 0-to-1 scale |
| `viewer` | resolved `viewer_profile` |
| `intent_type` | resolved `intent_type` |
| `time_bucket` | resolved `time_bucket` |
| `tone` | observational only |
| `runtime_preference` | observational only |
| trusted maturity aliases | hard `maturity_gate`, currently only `kids` |

The output is the adapter-ready intent consumed by the Phase 3C direct scoring
seam; it is not raw input for `StreamingAdapter.resolve_intent`. Maturity policy
does not manufacture or override `viewer_profile`, because doing so would turn
a hard policy into an unintended soft ranking signal.

`ProphecyContextNormalizer` is a separate inbound boundary. It converts
`energyLevel / 100` and explicitly recognizes the existing 0-to-1 `energy` and
`energy_level` forms. Multiple spellings in one payload fail as ambiguous. All
other fields remain observational, so Prophecy data cannot create hard
constraints or timestamps.

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
  current adapters, whose names differ. Pure streaming translation now feeds
  the internal Phase 3C seam; the legacy API and other domains remain separate.
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
- **Resolved, not raw, adapter intent:** The proposed spec did not distinguish
  adapter input stages. Phase 3A emits the vocabulary consumed by
  `compute_multipliers`, not the raw vocabulary consumed by `resolve_intent`.
  This preserves the already-planned `intent_type` rather than asking the
  adapter to infer it again.
- **Explicit lossy translation:** `tone` and `runtime_preference` are retained
  as observational signals because the streaming adapter does not consume
  them. A round trip is intentionally not promised.
- **Narrow executable safety semantics:** Phase 1 capability metadata accepts
  four maturity labels, but the current streaming hard gate implements only
  `kids`. Phase 3A rejects other authoritative maturity values instead of
  claiming that an unenforced policy was applied.
- **Prophecy compatibility alias:** In addition to the spec's camel-case
  0-to-100 `energyLevel`, Phase 3A explicitly supports the existing custom
  schedule spelling `energy_level` on the 0-to-1 scale. Supplying more than one
  spelling fails rather than guessing precedence or scale.
- **Atomic orchestration preparation:** The broad target sketch lists separate
  `active_step`, `execute`, `observe`, and lifecycle methods. Phase 3B exposes
  only `prepare_execution` so validation, temporal selection, precedence, and
  normalization share one trusted-time boundary. Phase 3C consumes that result
  without adding ranking to the orchestrator; outcome lifecycle methods remain
  Phase 8 work.
- **Explicit trust parameters:** `active_profile_context` and
  `authoritative_constraints` are required keyword arguments even when empty.
  This makes caller ownership visible and prevents defaults from implying that
  profile or policy resolution occurred.
- **Elapsed-time semantics:** Aware plan timestamps are ordered as UTC instants
  rather than same-zone wall times. Planner horizons and orchestrator step
  offsets therefore retain their elapsed-minute meaning across daylight-saving
  gaps and folds; naive timestamps preserve their prior deterministic behavior.
- **Prepared step snapshot:** `PreparedPlanExecution.active_step` uses a frozen
  `ActivePlanStep` projection instead of exposing the mutable Pydantic
  `IntentStep`. Phase 4 can still record the selected step without permitting
  the prepared execution envelope to become internally inconsistent.
- **Resolved response compatibility:** The existing `RankingResponse` requires
  a legacy `Intent` and supports `mode_used`, although the resolved seam does
  not receive a legacy request. Phase 3C projects only the normalized
  `intent_type`, reports `advanced` mode, and uses zero intent-parsing latency.
  These fields are compatibility metadata, not policy or authentication.
- **Prophecy execution remains deferred:** The Phase 3 heading proposed both
  Prophecy and ranking integration, but it did not define whether advisory
  Prophecy context precedes plan state, the active step, or authenticated
  profile context. Phase 3C integrates deterministic ranking only rather than
  inventing precedence that could override validated plan intent.
- **One shared scoring implementation:** Phase 3C factors the existing scoring
  body into a private method used by both `rank()` and `rank_resolved()`.
  Formula, hard-gate, call-order, diversity, explanation, and response behavior
  are intentionally preserved rather than reimplemented.

## Technical debt and risks

- **Capability-registry drift:** Signal and constraint metadata currently lives
  beside, rather than on, domain adapters. It can drift as adapters evolve.
  A later phase should establish one source of truth without making validators
  execute ranking code.
- **Energy naming and scale:** The V4 contract uses `energy` on a 0-to-1 scale;
  domain adapters currently use `energy_level`, also as an implied 0-to-1
  value; Prophecy Agent templates use camel-case `energyLevel` on a 0-to-100
  scale. Phase 3A converts these explicitly and Phase 3C consumes normalized
  plan intent, but runtime Prophecy merging remains unimplemented.
- **Constraint translation:** V4 represents constraints as typed objects, while
  existing adapters receive dictionaries such as `maturity_gate`,
  `block_explicit`, `surge_cap`, and `allergens`. Phase 3A implements only the
  streaming maturity aliases and only from the separate authoritative channel.
  Other domains remain undefined and must be reviewed before execution.
- **Capability versus consumption:** Some canonical V4 signals, such as
  streaming `tone` and `runtime_preference`, are valid plan vocabulary but are
  not consumed by the current adapter. Phase 3A leaves them explicitly
  observational; Phase 4 traces must distinguish observed from applied data.
- **Planner/adapter vocabulary boundary:** The planner emits canonical V4
  `energy` (0-to-1) and `viewer`, while streaming adapters consume
  `energy_level` and `viewer_profile`, and Prophecy Agent emits `energyLevel`
  on a 0-to-100 scale. Plan normalization and direct resolved ranking are now
  wired, but the fixed legacy ranking request intentionally remains unable to
  carry V4 execution state.
- **Internal-only resolved seam:** `rank_resolved` accepts adapter-ready value
  mappings and cannot authenticate how they were produced. It must remain an
  in-process consumer of orchestrator output. A future V4 API must reconstruct
  trusted profile and policy context server-side rather than accepting a
  client-authored normalized result or `hard=true` claim.
- **Prepared execution is not ranking authority:** `PreparedPlanExecution` is a
  copy-safe in-process result, but its Python type is not authentication. Phase
  3C consumes its normalized values only through in-process composition; a
  future boundary must not deserialize the type as proof of profile or
  constraint trust.
- **Partial maturity semantics:** The capability registry permits `kids`,
  `teen`, `family`, and `adult`, while the streaming adapter only enforces the
  `kids` gate. Phase 3A fails closed for the other values; later domain-policy
  work must define them before they can execute.
- **Local objective vocabulary:** Phase 2 objective aliases are intentionally
  local to the planner. If a later deterministic context interpreter also owns
  aliases, the vocabulary must be centralized to prevent drift.
- **Constraint provenance enforcement:** Phase 3B accepts, preserves, and
  revalidates a separate authoritative channel and never treats a `source`
  enum label in the plan as proof. Only a future API/application policy resolver
  can authenticate the profile, session, system, or domain-policy source and
  must persist and re-supply those constraints for each execution.
- **Normalized result provenance:** The exported normalized-result dataclasses
  provide immutable value containers, not authentication. Phase 3C accepts
  their values only from the in-process orchestrator/normalizer path and must
  never deserialize them from an external request as proof of policy
  authority.
- **Existing diversity semantics:** The engine counts every prior occurrence
  of a diversity key, even when equal keys are separated by another key. Phase
  3C preserves this existing behavior and corrects its misleading code comment;
  any semantic change requires a separately reviewed ranking change.
- **Legacy adapter trust:** The resolved seam validates and isolates adapter
  inputs and outputs, but the legacy `rank()` path intentionally retains its
  existing mutable adapter contract for backward compatibility. Tightening the
  legacy path requires a separate behavior-change review.
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

## Completed Phase 3 ranking path and recommended Phase 4

Phase 3 now composes the deterministic streaming path without making the
orchestrator a ranker:

1. `IntentOrchestrator` revalidates the plan at trusted execution time, selects
   the active step, applies context precedence, and normalizes intent and
   separately authoritative hard constraints;
2. `DomainRankingEngine.rank_resolved` snapshots only the adapter-ready intent,
   hard constraints, and candidates, then bypasses raw intent resolution;
3. both the legacy and resolved ranking paths execute the same hard gates,
   multipliers, diversity pass, explanations, and response construction; and
4. a wind-down plan executes at T+0, T+25, and T+50 with deterministic replay
   and the kids maturity gate blocking adult content at every step.

The recommended Phase 4 is a separate execution-trace PR. First replace the
generic `validation_results`, `safety_decisions`, and `ranking_trace` payloads
with explicit typed structures that distinguish interpreted, validated,
normalized, applied, observational, and blocked data. Then build traces from
trusted in-process execution values without changing ranking behavior or
exposing a V4 API. Keep deterministic decision data separate from measured
latency and generated trace identifiers. Resolve plan-level versus step-level
event identity before adding lifecycle events.

## Intentionally deferred

- Context-interpreter behavior and probabilistic interpretation.
- Runtime Prophecy merging until its precedence relative to plan state, the
  active step, and authenticated profile context is explicitly defined.
- Normalization for music, e-commerce, ride matching, or food delivery.
- Full execution-trace creation and strongly typed trace internals (Phase 4).
- `/v4/plan`, `/v4/execute`, `/v4/observe`, plan retrieval, and trace retrieval
  APIs (Phase 5).
- Frontend Agentic Mode and frontend-to-backend execution wiring (Phase 6).
- Optional LLM planner, malformed-model-output recovery, and runtime safe
  fallback behavior (Phase 7).
- Outcome evaluation and the observe/advance/complete loop (Phase 8).
- Any change to ranking formulas, diversity behavior, hard safety gates,
  candidate selection, existing domain-adapter execution, or existing APIs.
