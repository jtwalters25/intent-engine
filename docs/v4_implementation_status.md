# V4 Implementation Status

## Current status

Phase 6 streaming frontend integration is complete. `/demo` now offers Agentic
Mode backed by the real `/v4/plan` and `/v4/execute` endpoints. Signal Mode
retains the existing local slider experience. Agentic Mode renders the backend
plan, assumptions, constraints, temporal steps, ranked candidates, safety
evidence, score breakdowns, explanations, and execution reference. It does not
plan or rank locally. Request failures are explicit; future steps cannot be
selected with a simulated client clock.

## Phase 6 implementation record (2026-10-09)

Added `frontend/src/data/agenticApi.ts`,
`frontend/src/components/demo/AgenticMode.tsx`, two frontend test files, and
synthetic shared response fixtures. Updated `frontend/src/pages/Demo.tsx`,
`frontend/vite.config.ts`, `frontend/README.md`, this status document, and the
V4 spec. The unmerged `feat/frontend-agentic-mode` mock branch remains separate;
its mock planner and tests were not adopted into this API-backed feature.

Transport validates backend responses with Zod, maps the existing streaming
catalog into full backend Item inputs, and sends only text/domain/context for
planning or plan ID/candidates for execution. It has a 15-second request
deadline and aborts work on mode unmount. Create/refresh operations clear stale
ranking, show loading state, and retain a successfully created plan after an
execution error so users can retry.

Verification: **931 backend tests**, **16 frontend tests**, production Vite
build, changed-file ESLint, and diff checks passed. A real headless browser
smoke test through Vite's proxy received 200 for plan, execute, and refresh;
adult content was blocked. Desktop/mobile screenshots were inspected, with no
horizontal overflow at 390px. TypeScript checking reports one pre-existing
`CuratedHomeScreen.tsx:106` LearningFocus error; the same error occurs in the
primary checkout, and Phase 6 introduces no additional type errors. Dependency
installation also reports existing lockfile advisories; dependency upgrades
remain a separate maintenance change.

Deployment requires a reachable Python backend: Vite's development proxy uses
`V4_BACKEND_URL` (default localhost:8000); production uses a same-origin backend
route or build-time `VITE_API_BASE_URL`. Static frontend deployment alone does
not deploy Python. Missing configuration/service availability produces a
visible error, never a client-side simulation. Server time remains authoritative
for step selection; automatic polling and outcome lifecycle are deferred.

Recommended next phase: Phase 7 optional LLM planner, with explicit provider
configuration, deterministic validation, tested invalid-output recovery and
safe fallback, and LLM disabled by default. Phase 8 owns observe/outcome lifecycle.
Phase 5B successful streaming execution is complete. `POST /v4/execute` accepts
only a stored `plan_id` and up to 100 typed candidate items. The application
re-resolves server-owned identity/profile/policy, verifies the retained context,
and composes the existing orchestrator, resolved ranker, and trace builder once.
The response exposes trace ID, active step, explained ranked candidates, and a
small explanation projection. Full lifecycle traces remain in process.

Phase 5A deterministic plan creation is complete. `POST /v4/plan` now accepts a
strict natural-language streaming goal request, constructs trusted time and
session evidence server-side, applies a conservative server-owned public-demo
kids profile and maturity gate, interprets the supported pilot vocabulary with
rules only, validates the resulting plan, and stores the exact lifecycle
artifacts in a bounded process-local registry for the later execute boundary.

The endpoint returns the complete typed `IntentPlan`. It accepts no client
timestamp, session identity, interpretation, plan, hard constraint, normalized
intent, candidates, ranking data, or trace metadata. Unsupported or ambiguous
goals and unsupported context fields fail closed with stable 422 errors. The
legacy `/rank` route and its deterministic ranking behavior remain unchanged.

`ExecutionTraceBuilder` is observational. It contract-revalidates and snapshots its
typed inputs, checks that their plan, domain, step, intent, rank, score, and
blocked evidence agree, and does not call validation, normalization, an adapter,
or ranking. It consumes the new engine-produced `ResolvedRankingExecution`,
which correlates the exact resolved intent, hard constraints, input candidates,
and response from one `rank_resolved_execution` call.
`canonical_execution_decision_json` provides deterministic replay material
while excluding the caller-supplied trace ID, measured latency, and outcome
events. Ranking behavior, existing APIs, Prophecy, and the frontend remain
unchanged.

Phase 4 successful-execution tracing remains the in-process execution evidence
boundary. Trace retrieval and outcome observation remain deferred as documented
below. The streaming plan-and-execute scenario now works through backend APIs.

## Phase 5B implementation record (2026-10-09)

Changed `agentic/application.py`, `api_v4.py`, `tests/test_v4_api.py`, this status
document, and the V4 spec. Added `tests/test_v4_execute_api.py` (33 tests).
The earlier route-absence test was updated because execute is now implemented;
observe and retrieval remain absent. Full backend suite: **931 passed**.
`git diff --check` passed. All ranking code and legacy API contracts are unchanged.

Tests cover T+0/T+25/T+50 selection, authoritative blocking, direct-ranking
equivalence, canonical replay equality, distinct trace IDs, bypassing raw intent
resolution, malformed/oversized/duplicate candidates, forged authority fields,
missing/foreign/expired plans, pre-start execution, policy drift, and generic
internal errors. Streaming candidates require a known maturity label, finite
numeric fields, and bounded calm/complexity values. Base scores are bounded to
0–1,000,000 at this new HTTP boundary; legacy Item validation is unchanged.

HTTP errors: request validation 422; missing, foreign, evicted, or expired records
404 with identical messages; pre-start or policy/session changes 409; unexpected
ranking/trace faults generic 500. Expired records are removed by the Phase 5A
registry, so this implementation deliberately does not distinguish expiration
from absence. The trace ID is generated server-side; replay versions are
server-owned semantic labels (`v4-domain-engine-1`, `v4-streaming-adapter-1`) that
must be revised alongside future scoring/adapter behavior changes.

Limitations: fixed public demo owner/session is not user authentication; clients
provide candidate metadata, whose real-world accuracy is outside the ranking
contract. Production requires trusted retrieval and real identity/profile
resolution. Plans remain bounded and process-local; restart/eviction loses them.
Full traces are returned only inside the process and are neither persisted nor
retrievable. Redaction, durable storage, access control, partial/failure traces,
Prophecy merging, and outcome lifecycle remain deferred.

Recommended next PR: Phase 6 streaming frontend integration with the real
`/v4/plan` and `/v4/execute` APIs, replacing the client-side V4 planning/ranking
simulation while preserving the existing signal demo. Do not add trace retrieval
or observation as part of frontend wiring.

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
- Replaced the loose Phase 1 trace internals with typed validation,
  intent-application, candidate-safety, ranking-multiplier, ranking-score,
  ranked-candidate, ranking-decision, and latency contracts.
- Added `ExecutionTraceBuilder` for a completed successful execution. It accepts
  exact typed artifacts already produced in process, takes bounded defensive
  snapshots, and fails closed on cross-artifact domain, plan, active-step,
  applied-intent, hard-constraint, candidate input/output, score, rank-order, or
  blocked-evidence mismatches.
- Added the additive `DomainRankingEngine.rank_resolved_execution` seam. It
  executes the same resolved-ranking implementation once and returns a frozen
  `ResolvedRankingExecution` correlation envelope containing exact snapshotted
  intent, constraints, full input candidates, and the resulting response.
  Existing `rank_resolved` callers and ranking behavior remain unchanged.
- Kept canonical intent, adapter-ready applied intent, applied authoritative
  hard constraints, and deliberately non-applied observational signals in
  separate trace fields.
- Recorded only generic per-candidate hard-gate evidence. The current adapter
  protocol does not identify which individual hard constraint caused a block,
  so Phase 4 does not invent per-constraint causality. Safety records include
  output rank so repeated item IDs remain distinguishable.
- Required caller-supplied nonblank engine and adapter version labels in the
  ranking decision record. The builder records but does not discover or
  authenticate these labels.
- Added `canonical_execution_decision_json`, which produces stable sorted JSON
  for the decision fields and deliberately excludes `trace_id`, latency, and
  outcome events.
- Kept Phase 4 traces in process and success-only. The builder emits an empty
  outcome-event collection and adds no API, persistence, retrieval, redaction,
  retention, failed-attempt trace, or outcome-lifecycle behavior.
- Added a deterministic `RuleBasedContextInterpreter` for the streaming pilot.
  It recognizes only the five existing planner objectives and the canonical
  `viewer`, `energy`, and `horizon_minutes` context fields, rejects unsupported
  or ambiguous goals, and never calls an LLM, adapter, or ranker.
- Added a `V4PlanningService` application boundary. One injected server clock
  owns goal and plan time, and an injected policy resolver supplies ownership,
  session identity, protected profile context, and authoritative constraints.
- Bound the unauthenticated public pilot to a conservative server-owned kids
  profile and hard kids maturity gate. Client viewer context remains goal input
  but cannot weaken or replace that profile or policy.
- Added a bounded, thread-safe, process-local `InMemoryPlanRegistry`. It stores
  detached snapshots of the goal, effective interpretation, validated plan,
  profile, authoritative constraints, and owner scope; records expire no later
  than plan expiry or the configured retention ceiling.
- Added strict `POST /v4/plan`. The transport accepts only `text`, `domain`, and
  bounded canonical context; returns the full typed plan; maps expected
  interpretation and planning failures to stable 422 responses; and returns a
  generic non-leaking 500 for unexpected faults.
- Kept `/v4/execute`, `/v4/observe`, plan retrieval, and trace retrieval absent.
  No request can deserialize a prepared execution, normalized intent, policy
  authority, ranking result, or trace as trusted state.

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

## Phase 4 files added or modified

Added:

- `backend/intent_engine/agentic/trace.py`
- `backend/tests/agentic/test_trace.py`

Modified:

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/agentic/schemas.py`
- `backend/intent_engine/core/domain_engine.py`
- `backend/tests/agentic/test_schemas.py`
- `backend/tests/core/test_domain_engine_resolved.py`
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No adapter, legacy `RankingEngine`, planner, normalizer, orchestrator, Prophecy
Agent, LLM, API, or frontend behavior was modified for Phase 4. The domain
engine change is an additive execution-correlation return path over the shared
resolved-ranking implementation; existing `rank` and `rank_resolved` behavior
and return types remain unchanged.

## Phase 5A files added or modified

Added:

- `backend/intent_engine/agentic/context_interpreter.py`
- `backend/intent_engine/agentic/application.py`
- `backend/intent_engine/api_v4.py`
- `backend/tests/agentic/test_context_interpreter.py`
- `backend/tests/agentic/test_application.py`
- `backend/tests/test_v4_api.py`

Modified:

- `backend/intent_engine/agentic/__init__.py`
- `backend/intent_engine/api.py` (router inclusion only)
- `docs/IntentEngine_v4_Spec.md`
- `docs/v4_implementation_status.md`

No ranking engine, domain engine, adapter, normalizer, orchestrator, Prophecy
Agent, LLM, existing request contract, or frontend behavior was modified for
Phase 5A.

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

The Phase 4 tests cover strict nested trace contracts; validation-status and
issue consistency; applied-versus-observational isolation; generic blocked
evidence with duplicate-ID-safe ranking positions; full input/output candidate
preservation and contiguous rank order; finite score, multiplier, and latency
values; JSON round trips with the full `Item` replay fields; construction from
a real planner/orchestrator/ranker execution envelope;
defensive snapshots against later caller mutation; rejection of malformed or
cross-lifecycle plan, domain, step, intent, candidate, score, and safety data;
caller-supplied trace and version metadata; and stable canonical decision JSON
that excludes trace ID, measured latency, and outcome events.

Current Phase 4 verification:

- Phase 4 trace-builder tests: **25 passed**.
- Trace contract tests: **107 passed**.
- Resolved-ranking boundary tests: **43 passed**.
- All agentic tests: **478 passed**.
- Full backend suite: **795 passed**.
- Frontend suite: **1 passed**.
- Combined repository test total: **796 passed**.
- Python bytecode compilation: **passed**.

The Phase 5A tests cover deterministic interpretation of the five supported
streaming objectives; natural-language and explicit-context extraction;
unsupported, conflicting, ambiguous, malformed, and candidate-shaped input;
server-clock ownership; server profile and hard-policy precedence; immutable
record snapshots; owner-scoped lookup; bounded capacity; plan/retention expiry;
collision handling; full plan serialization; stable public 422 errors; generic
non-leaking 500 errors; rejection of client-authored authority and later-phase
fields; preservation of `/rank`; and the intentional absence of execute,
observe, and retrieval routes.

Current Phase 5A verification (2026-10-09): **899 backend tests passed**, including
104 new interpreter/application/API tests. `git diff --check` passed. No live
provider or LLM calls were made.

The application derives API plan IDs from the complete goal, owner scope, and
validated planner output. This preserves deterministic replay at fixed trusted
time while keeping distinct original goals in separate lifecycle records, even
when their intent semantics match. Interpreter constraints are checked for
forged hard or privileged authority before protected-profile reconciliation.

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

- **API goal time and session:** `POST /v4/plan` accepts neither a timestamp nor
  a session identifier. `V4PlanningService` reads one injected aware server
  clock value and a server-owned planning context, then uses those values for
  both the retained `GoalRequest` and the generated plan.
- **Public pilot profile/policy:** until authenticated principals exist, the
  public V4 route is deliberately bound to one fixed server-owned kids profile
  and corroborating hard maturity gate. Request context cannot select an adult
  profile, remove the gate, or manufacture `SYSTEM`/`DOMAIN` authority.
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
- **Trace evidence:** `ExecutionTraceBuilder` is an in-process observer, not an
  authority boundary. The caller must supply the exact goal, interpretation,
  plan, prepared execution, and engine-produced `ResolvedRankingExecution` from
  one execution. The engine envelope correlates its exact snapshotted applied
  intent, constraints, input candidates, and response; the builder additionally
  requires those applied inputs to match the prepared execution. Neither Python
  type is external authentication, and the builder does not verify
  caller-supplied version labels.

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
- **Rules-only interpretation is now narrow:** Phase 2 correctly remained a
  structured planner. Phase 5A adds the separate target-architecture context
  interpreter needed by the natural-language API, but only for the five
  reviewed streaming objectives and three canonical context fields. Unknown or
  ambiguous goals fail closed; probabilistic/LLM fallback remains Phase 7.
- **Server-owned API fields:** The target `/v4/plan` example omits the required
  `GoalRequest.timestamp` and uses `context` rather than the contract's
  `explicit_context`. Phase 5A keeps the concise transport shape, maps `context`
  internally, and creates timestamp and session evidence server-side.
- **Full plan response:** The spec's `/v4/plan` response is an abbreviated
  projection. Phase 5A returns the complete validated `IntentPlan` at the top
  level so constraints, state, expiry, planner version, and transition reasons
  are not silently discarded.
- **Conservative unauthenticated pilot:** No account principal or profile store
  exists in the repository. Instead of trusting request context as policy,
  Phase 5A binds the public route to a fixed kids profile and hard gate. A real
  authenticated resolver must replace it before multi-profile production use.
- **Ephemeral plan state:** `/v4/execute` is specified by plan ID but the repo
  had no plan store. Phase 5A introduces only a bounded, owner-scoped,
  process-local registry with defensive copies and expiry. It is sufficient to
  compose Phase 5B in one process, not durable or distributed persistence.
- **Staged Phase 5 surface:** `/v4/execute` follows in Phase 5B. Plan/trace
  retrieval remains blocked on storage, redaction, retention, and access
  control; `/v4/observe` remains blocked on Phase 8 event/lifecycle semantics.
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
  `IntentStep`. Phase 4 copies that snapshot into a revalidated `IntentStep` and
  requires it to match exactly one step in the traced plan.
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
- **Successful executions only:** The target statement that every V4 request is
  observable is broader than the Phase 1 envelope, which requires a plan,
  active step, and ranking result. Phase 4 therefore implements a strict trace
  for completed successful executions. A failed or partial request needs a
  separate lifecycle shape rather than fabricated missing artifacts.
- **Observational trace builder:** `ExecutionTraceBuilder` never reruns plan
  validation, normalization, an adapter, or ranking. A
  `PreparedPlanExecution` is the correlation value returned by the in-process
  preparation boundary, not independent proof of validation or authority. The
  builder records that boundary as completed and validates coherence of the
  supplied evidence without creating new execution authority.
- **Typed trace stages:** The spec's generic `validation_results`,
  `safety_decisions`, `ranking_trace`, and latency dictionary are replaced with
  explicit contracts. `IntentApplicationTrace` keeps canonical intent, applied
  adapter intent, applied authoritative hard constraints, and observational
  signals separate, and rejects overlap between applied and observational
  signal names.
- **Phase 1 trace migration:** Phase 4 intentionally tightens the exported
  `ExecutionTrace` constructor and serialized nested shapes. The field names
  remain recognizable, but generic dictionaries and `Any` ranking data are no
  longer accepted, and `intent_application` is now required. No existing API
  exposed the Phase 1 trace envelope.
- **Generic safety evidence:** Existing adapters return only a blocked boolean,
  while the ranker emits a generic block reason. Candidate safety trace entries
  therefore record exactly that evidence and do not claim which constraint
  caused the block.
- **Explicit replay versions:** The existing engine and adapter expose no
  version identifiers. Phase 4 requires nonblank caller-supplied engine and
  adapter version labels rather than deriving unstable class names or silently
  omitting replay metadata. The labels are recorded, not authenticated.
- **Deterministic decision projection:** Full traces include volatile IDs,
  measured latency, and a future-facing outcome-event list.
  `canonical_execution_decision_json` excludes those three fields while
  retaining request, interpretation, plan, validation, active step, intent
  application, safety evidence, ranked decisions, and replay versions.
- **Ranking-only latency:** The current ranking response measures intent
  parsing, scoring, diversity, and their ranking-pipeline total. Phase 4 names
  that aggregate `ranking_total_ms`; it does not claim to measure goal
  interpretation, planning, validation, or full request latency.
- **Empty outcome collection:** The builder always creates a successful
  execution trace with no outcome events. This preserves the Phase 1 envelope
  without choosing plan-level versus step-level event identity or implementing
  Phase 8 lifecycle behavior.

## Technical debt and risks

- **Demo-only identity:** Phase 5A's fixed public owner/session and kids profile
  are a safe conservative boundary, not authentication. Phase 5B must keep
  ownership and policy injectable, and production exposure requires a real
  principal/profile resolver before plans can be isolated per user or tenant.
- **Process-local plan availability:** The bounded registry loses plans on
  restart and does not coordinate across workers. It intentionally has no
  retrieval API. Durable/distributed storage needs explicit encryption,
  redaction, retention, deletion, collision, and authorization policy.
- **Objective vocabulary duplication:** The context interpreter and planner
  both recognize the five pilot objectives. Their constants should move to one
  non-ranking vocabulary module before either surface expands to new domains.
- **HTTP deployment limits:** Pydantic caps goal text and bounds nested context,
  but application-level body-size limits and tightened CORS are still required
  before authenticated or internet-scale deployment. Existing permissive CORS
  was preserved to avoid changing the legacy API in this phase.
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
  observational; Phase 4 now records them separately from applied intent.
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
- **Trace composition provenance:** `rank_resolved_execution` correlates the
  exact snapshotted ranking inputs and response from one engine call, and the
  builder requires those inputs to match the prepared execution. These Python
  value containers are still not authentication or tamper-proof audit storage.
  Keep them behind the in-process application composition boundary; Phase 5
  must not accept prepared or normalized trace evidence from a client.
- **Replay-version provenance:** Engine and adapter version labels are currently
  caller supplied because those components expose no stable version contract.
  They are useful replay metadata, not authenticated build provenance. A later
  release/version policy should define their authoritative source.
- **Success-only trace shape:** `ExecutionTrace` represents a completed
  execution and therefore requires a plan, active step, and ranking. Planning,
  validation, orchestration, or ranking failures need a separate partial trace
  contract before the target of tracing every request can be met.
- **Trace privacy and retention:** Successful traces contain goal text, explicit
  and inferred context, full candidate items and attributes, and ranking
  evidence. No persistence, retrieval, redaction, retention, or access-control
  policy exists yet. Those policies must be defined before Phase 5 exposes
  traces outside the process.
- **Plan-level outcome events:** The proposed `OutcomeEvent` requires a
  `step_id`, although events such as `PLAN_CANCELLED` and `SESSION_ENDED` may be
  plan-scoped. This should be resolved before the outcome API is introduced.

## Completed Phase 5A plan path and Phase 5B composition

The successful streaming path is now observable without making the orchestrator
a ranker or the trace builder an executor:

1. `IntentOrchestrator` revalidates the plan at trusted execution time, selects
   the active step, applies context precedence, and normalizes intent and
   separately authoritative hard constraints;
2. `DomainRankingEngine.rank_resolved_execution` snapshots the adapter-ready
   intent, hard constraints, and candidates, bypasses raw intent resolution,
   and returns the response with those exact correlation inputs;
3. both the legacy and resolved ranking paths execute the same hard gates,
   multipliers, diversity pass, explanations, and response construction;
4. `ExecutionTraceBuilder` snapshots the completed preparation and ranking
   artifacts into one coherent typed successful-execution trace; and
5. `canonical_execution_decision_json` separates replayable decision evidence
   from generated trace identity, measured latency, and later outcomes.

Phase 5A now adds the request-to-plan half of that boundary:

1. a strict transport accepts only goal text, domain, and bounded canonical
   context;
2. one trusted server clock and one server-owned profile/policy context create
   the retained goal evidence;
3. deterministic interpretation produces a typed, non-authoritative
   `ContextInterpretation` or fails closed;
4. protected viewer context and the hard kids gate are applied through separate
   trusted channels before deterministic planning; and
5. detached lifecycle snapshots enter a bounded, owner-scoped registry while
   the complete validated plan is returned to the caller.

Phase 5B implements `POST /v4/execute`. It accepts only
`plan_id` and bounded full `Item` candidates, resolve the current principal,
profile, policy, trusted time, trace ID, and version labels server-side, load
the exact retained lifecycle record, then compose
`IntentOrchestrator.prepare_execution` →
`DomainRankingEngine.rank_resolved_execution` → `ExecutionTraceBuilder` in
process. The response should be a safe execution projection, not the full
sensitive trace. Missing and foreign plans should be indistinguishable; known
expired/pre-start/policy-drift states need stable non-500 semantics.

Trace retrieval still requires explicit durable-storage, redaction, retention,
and access-control decisions. Failure traces and outcome lifecycle behavior
remain separate rather than weakening the completed success-trace contract.

## Intentionally deferred

- Probabilistic/LLM interpretation fallback, confidence escalation, and
  malformed model-output recovery.
- Runtime Prophecy merging until its precedence relative to plan state, the
  active step, and authenticated profile context is explicitly defined.
- Normalization for music, e-commerce, ride matching, or food delivery.
- Failed and partial lifecycle traces for requests that do not reach a completed
  ranking.
- Plan/trace retrieval (a later privacy/storage slice) and `/v4/observe` (Phase 8).
- Trace persistence, retrieval storage, redaction, retention, and access-control
  policy (required before externally exposing traces).
- Optional LLM planner, malformed-model-output recovery, and runtime safe
  fallback behavior (Phase 7).
- Outcome-event ingestion, plan-level versus step-level event identity, outcome
  evaluation, and the observe/advance/complete loop (Phase 8).
- Any change to ranking formulas, diversity behavior, hard safety gates,
  candidate selection, existing domain-adapter execution, or existing APIs.
