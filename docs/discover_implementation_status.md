# Discover Pilot — Implementation Status

_Spec: `IntentEngine_Discover_Pilot_Spec.md`. Phase 0 is the mandatory repository
assessment that must precede Discover code (spec §20). Last updated 2026-10-09._

This document is the standing answer to the seven Phase-0 questions. It is kept
current as phases land so work can resume without re-deriving context.

## Session handoff (2026-10-09, Claude → Codex)

Claude did interim work while Codex was offline. Current branch layout:

- **`feat/frontend-agentic-mode`** (commit `0abfafa`): streaming-demo Agentic
  Mode only (frontend). Separate deliverable; 8 vitest tests pass. Not Discover.
- **`feat/discover-foundation`** (commit `1a05477`): Discover spec + this Phase 0
  doc + **Phase 1 schemas** (`discover/schemas.py`, 33 tests) + the `evaluation/`
  contracts. Backend suite green at **852 passed**.

Delivered this session: the branch split above, Phase 0 assessment (this doc),
and Phase 1 schemas. **Phase 2 was started as a scaffold, not finished** — see
the checklist below.

**Phase 2 scaffold (`discover/providers/base.py`, committed as WIP):** a
`BaseProvider` template (config validation → single bounded HTTP call → typed
error translation → per-item-safe parse), an injectable `HttpTransport` seam with
a real `HttpxTransport` + offline-friendly fake, typed errors
(`ProviderConfigError`/`ProviderTimeout`/`ProviderRateLimited`/`ProviderResponseError`),
and `_verified()`/`_extracted()` provenance helpers. It **imports cleanly but has
no tests yet.** Codex should review and either build on it or replace it — it is a
suggestion, not a commitment. No `providers/__init__.py`, `ticketmaster.py`,
`google_places.py`, or `test_providers.py` exist yet.

Follow-up noted (gap #1): `AttributeProvenance`/`EvidenceStatus` are now canonical
in `discover/schemas.py`; `evaluation/contracts.py` still carries a byte-compatible
copy to dedupe later.

## 1. Repository inspection

- `backend/intent_engine/` — legacy ranking core (`schemas`, `simple_ranker`,
  `rules_translator`, `intent_parser`, `ranking_engine`, `llm_adapter`, `api`).
- `backend/intent_engine/core/` — V3 `adapter_protocol.py` (`DomainAdapter`
  Protocol) and `domain_engine.py` (multiplier-chain ranker).
- `backend/intent_engine/adapters/` — 5 V3 vertical adapters (streaming,
  ride_matching, food_delivery, music, ecommerce).
- `backend/intent_engine/agentic/` — **V4 intent layer** (see §2).
- `backend/intent_engine/discover/` — **this pilot.** Present today:
  `schemas.py` (Phase 1), `providers/` (Phase 2), `normalization.py` +
  `constraints.py` (Phase 3), `signals.py` + `ranking.py` + `explain.py`
  (Phase 4), `service.py` + `router.py` (Phase 5), `config.py` (Phase 8), and the
  `evaluation/` subpackage (§16, incl. Phase 7 `baselines.py`).
- Branch `feat/discover-foundation` is rebased onto current `main` (V4 through
  Phase 7). Full backend suite green: **1192 tests passing** (203 Discover,
  including an end-to-end integration test through the real provider adapters,
  spec §19); the frontend suite is **26 passing**. **All eight Discover phases
  are complete**
  (see the plan below); remaining work is the external/ops prerequisites in
  `discover_pilot_readiness.md` (API keys, provider ToS, feedback persistence,
  real LLM client, deploy).

## 2. Current V4 implementation status

V4 (the `agentic` package) is substantially complete and merged to `main`
(PRs #3–#8, phases 1–4). Available, tested building blocks:

| Module | Key exports | Role for Discover |
|---|---|---|
| `agentic/schemas.py` | `GoalRequest`, `ContextInterpretation`, `IntentPlan`, `IntentStep`, `IntentConstraint`, trace contracts | Canonical intent contracts to translate into |
| `agentic/planner.py` | `IntentPlanner` (Protocol), `RuleBasedIntentPlanner` | **Reuse** — do not duplicate the planner (spec §10) |
| `agentic/validator.py` | `PlanValidator`, `canonical_plan_json` | Plan validation + canonical form for determinism |
| `agentic/normalizer.py` | `PlanIntentNormalizer`, `ProphecyContextNormalizer` | The intent→signals normalization boundary |
| `agentic/orchestrator.py` | `IntentOrchestrator`, `PreparedPlanExecution` | Deterministic plan execution seam |
| `agentic/trace.py` | `ExecutionTraceBuilder`, `canonical_execution_decision_json` | Grounded explanation + replay fingerprint source |
| `agentic/capabilities.py` | `DomainCapabilities`, `ValueRule` | Declares which signals a domain supports |

Not yet present in V4: a Discover domain registration. Per spec §10, add a
**narrowly scoped translation boundary**, not a new planning framework.

## 3. Existing reusable components

- **Planner:** `RuleBasedIntentPlanner` exists → reuse it (spec §10 is explicit).
- **Validation + determinism:** `PlanValidator` + `canonical_plan_json` +
  `ranking_fingerprint` (already in `discover/evaluation/contracts.py`) cover the
  `ranking_reproducibility = 1.00` endpoint (§16).
- **Ranking:** V3 `DomainRankingEngine` / `DomainAdapter` is the deterministic
  multiplier-chain ranker to bridge into (spec §12), via a Discover adapter.
- **Evidence contracts:** `discover/evaluation/contracts.py` already implements
  `AttributeProvenance`, `EvidenceStatus`, `ExplanationClaim`, `GroundTruthLabel`,
  `EvaluationSession`, and fingerprints (§7.1, §13.1, §16, §16.1).
- **Schemas (Phase 1, done):** `discover/schemas.py` — `DiscoveryRequest`,
  `DiscoveryCandidate`, `AttributeProvenance`/`EvidenceStatus` (canonical),
  `DiscoveryFeedback`.

## 4. Integration gaps

1. **Resolved.** `AttributeProvenance`, `EvidenceStatus`, `ConstraintState`, and
   (Phase 4) `ClaimKind` + `ExplanationClaim` are defined once in
   `discover/schemas.py`; `constraints.py` and `evaluation/contracts.py` import
   and re-export them (back-compatible import paths preserved). Single canonical
   class each; suite green.
2. **No Discover→V4 translation boundary** (`service.py` / `ranking_bridge.py`).
   `DiscoveryRequest` is not yet translated into a validated `IntentPlan`.
3. **Done (Phase 4, `signals.py`).** All six ranking signals (`family_friendly`,
   `educational_value`, `budget_fit`, `distance_fit`, `schedule_fit`,
   `duration_fit`) — deterministic 0–1 fit from candidate evidence, explicit
   missing-value handling (neutral + `known=False`), per-signal evidence basis
   for explanation grounding (spec §10). Remaining Phase 4: the adapter + ranking
   + fingerprint (see plan).
4. **Done (Phase 3).** Candidate deduplication (`normalization.py`, spec §9) and
   three-state hard constraints (`constraints.py`: PASS/FAIL/UNKNOWN with the
   budget-basis distinction, spec §11).
5. **Providers completed in Phase 2.** Ticketmaster and Google Places normalize
   one response page into candidates with explicit provenance. Live credentials,
   provider terms/display review, and multi-provider retrieval composition remain
   later readiness/service work.
6. **Done.** Backend API (Phase 5) via a self-contained `discover/router.py`
   (one `include_router` in `api.py`, mirroring the V4 router); frontend (Phase
   6) at `frontend/src/pages/Discover.tsx` on the `/discover` route, with a
   zod-validated `discoverApi.ts` client.
7. **Done (Phase 7).** `evaluation/baselines.py` — relevance arm, LLM-only arm
   (injected client), and a faithful `intent_engine` arm bridge; feeds the
   existing `metrics.py` + `decide()`. The real LLM client is deferred (needs a
   configured gateway); the arm is injectable/mockable.

## 5. Provider requirements

- **Ticketmaster Discovery API** (`TicketmasterProvider.search`) — event name,
  category, date/time, venue, location, price range _when available_, official
  URL. Structured `priceRanges` → VERIFIED provenance.
- **Google Places API** (`GooglePlacesProvider.search`) — museums, parks,
  attractions, family/educational venues. Many ranking-relevant attributes
  (age suitability, total price) are not structured → EXTRACTED or UNKNOWN, never
  VERIFIED.
- Both require API keys. **Standard test suite must not hit live APIs** (spec
  §19): use recorded/synthetic fixtures and mocked clients. Handle missing keys,
  timeouts, rate limits, empty results, malformed responses, and prompt injection
  in descriptions (treat all provider text as untrusted data — spec §18).

## 6. Blockers

- **API keys** (Ticketmaster, Google Places) required for live retrieval and the
  Experiment E / cost endpoints — not for Phases 1–4, which are fixture-driven.
- **LLM-only arm** (§16 arm B) needs the `llm_adapter` stub replaced with a real
  call (also an open core task). Evaluation harness can be built and unit-tested
  against recorded arm outputs before then.
- Nothing blocks the remaining pure/offline work. The next phase (4, Intent
  Engine integration) is where the V4 dependency begins — and V4 today is
  **streaming-domain only, in-process, with no HTTP API**. Compose it in-process
  and add a narrowly scoped Discover domain/translation boundary (spec §10); do
  not try to reuse the streaming planner objectives for events/places.

## 7. Concrete implementation plan

One phase at a time (spec §20); do not auto-implement later phases.

- [x] **Phase 1 — Discover schemas.** `discover/schemas.py` + `test_schemas.py`
  (33 tests). Contracts and validation for request/candidate/provenance/feedback.
- [x] **Phase 2 — Providers.** Both async adapters work with injected mocked
  transport. Ticketmaster structured price ranges carry VERIFIED evidence;
  descriptions carry EXTRACTED evidence; absent prices, age suitability,
  availability, duration, and price basis remain UNKNOWN. Google `price_level`
  is retained only as opaque metadata, never converted to dollars. Tests cover
  configuration, environment keys, parse/provenance, missing data, timeouts,
  HTTP/application rate limits and errors, safe partial results, malformed
  envelopes, bounded results, request parameters, source URLs, and injection
  text. Full suite: **902 passed**, including **50 provider tests**, entirely
  offline. Phase 3 has not started.
- [x] **Phase 3 — Normalization + constraints.** `normalization.py`
  (`deduplicate_candidates`: exact-id + conservative cross-provider merge that
  only *adds* a missing VERIFIED attribute, never overwrites or fabricates) and
  `constraints.py` (three-state hard constraints — date window, budget with
  price-basis handling, minimum age, availability; `filter_candidates` partitions
  verified / needs-verification / excluded). 26 tests; full suite **928 passed**.
  The six ranking signals moved to Phase 4; gap #1 dedup resolved (see §4).
- [x] **Phase 4 — Intent Engine integration.** `signals.py` (six ranking
  signals) + `constraints.verified_total_range`; `ranking.py` — a standalone
  deterministic Discover ranker (`final = base × ∏ signal_multipliers` +
  diversity penalty, stable tie-break, reproducible `ranking_fingerprint`),
  hard-FAILs excluded, needs-verification flagged; `explain.py` — grounded
  `ExplanationClaim`s (§13.1: one claim per known signal / PASS constraint;
  mandatory caveat per eligibility-affecting UNKNOWN; EXTRACTED hedged, VERIFIED
  stated as fact). 42 tests; full suite **1098 passed**. **Design decision:** a
  standalone ranker in `discover/`, not the legacy `DomainRankingEngine` — the
  `DiscoveryCandidate`/evidence-signal shape does not fit the fixed five-slot
  `MultiplierSet`, and registering a `Domain.discover` would edit shared
  `core/`/`schemas.py` (conflict surface + broad blast radius). §12 permits "the
  existing engine OR its supported extension points."
- [x] **Phase 5 — Discover API.** `service.py` composes the pipeline
  (retrieve→deduplicate→constraints→rank→explain) with concurrent retrieval,
  partial-failure warnings, and a hard RetrievalError when all providers fail
  (no fabrication, §18). `router.py` exposes `POST /discover/search` +
  `/discover/feedback` with an injectable provider dependency; mounted via one
  `include_router` in `api.py` (isolated from legacy/V4, mirroring `api_v4`). 12
  tests (pipeline + TestClient, mocked providers, no live calls); full suite
  **1110 passed**.
- [x] **Phase 6 — Frontend.** `discoverApi.ts` (zod-validated client: `/discover/
  search` + `/discover/feedback`, timeout-bounded, no fabricated fallback) and
  `pages/Discover.tsx` on the `/discover` route: query/location/budget form,
  ranked results with status + score, grounded explanation text + evidence-tinted
  claim badges, source links, and a separate "needs verification" section. 10
  frontend tests (client + page); full frontend suite **26 passed**.
- [x] **Phase 7 — Feedback + evaluation.** `evaluation/baselines.py`: relevance
  arm (keyword/popularity, asserts nothing), LLM-only arm (injected `LLMClient`,
  real client deferred), and a faithful `intent_engine` arm that asserts only
  VERIFIED facts from PASS constraints and caveats unknowns. `candidate_to_snapshot`
  builds the shared pool; `stated_from_request` maps the hard-constraint subset.
  Feeds the existing `compute_arm_report`/`decide`. 7 tests (incl. a reckless-LLM
  case caught by `critical_factual_error_count`, engine scoring 0); full suite
  **1117 passed**.
- [x] **Phase 8 — Pilot readiness (code/docs).** `config.py` centralizes
  env-based keys + cost controls (per-provider timeout, `max_results` cap, LLM
  off by default) and builds only key-configured providers (graceful
  degradation). Reliability behaviors (partial failure, all-fail→502, untrusted
  provider text, determinism) are in place. Ops reference:
  `docs/discover_pilot_readiness.md`. 12 config tests; full suite **1129 passed**.
  External prerequisites (API keys, provider ToS review, feedback persistence +
  retention job, real LLM client, deploy, frontend) are listed in the readiness
  doc — out of code scope.

## Phase 2 completion (2026-10-09)

Files added: `providers/__init__.py`, `providers/ticketmaster.py`,
`providers/google_places.py`, and `tests/discover/test_providers.py`.
Files updated: `providers/base.py`, backend dependency manifests (httpx is now
a runtime dependency), and this status document. Ranking, V4 planning, APIs,
frontend, and evaluation contracts were not changed.

The suggested base scaffold was retained and hardened: finite positive timeout,
bounded `max_results` (1–200), an enforced async deadline, aware retrieval clock,
typed sanitized transport failures, and per-item logs that omit external text
and secrets. Each search makes one HTTP call; pagination and details calls are
intentionally absent. Parsing preserves provider order and skips invalid items.
No cache, persistence, filtering, ranking, or cross-provider deduplication was
added. Date-only requests use Ticketmaster's local date window and do not invent
a timezone. Its coordinate filter currently uses documented but deprecated
`latlong`; migration to `geoPoint` is a readiness follow-up.

Google uses official Text Search (Legacy), matching the scaffold's GET seam and
the specified `price_level` response. Live rollout must verify project
eligibility or migrate to Places API (New); this phase makes no live calls.
Search has no canonical listing URL, so a Google Maps link is constructed from
the structured place ID and name. `html_attributions` are preserved. Places
display/attribution and retention restrictions must be resolved before UI or
evaluation persistence; the adapters do not store provider content. See
[Google Text Search documentation](https://developers.google.com/maps/documentation/places/web-service/legacy/search-text)
and [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies).

Gap #1 remains a **follow-up**: deduplicate
`AttributeProvenance`/`EvidenceStatus` in `evaluation/contracts.py` by importing
the canonical Discover schemas. Phase 4 will reuse `RuleBasedIntentPlanner` and
`PlanValidator`; neither is called by providers.

## Phase 3 completion (2026-10-09)

Files added: `discover/normalization.py`, `discover/constraints.py`,
`tests/discover/test_normalization.py`, `tests/discover/test_constraints.py`
(26 tests). No provider, schema, evaluation, V4, API, or frontend code changed.

Scope decision: Phase 3 covers candidate normalization and hard-constraint
filtering only. The spec §10 ranking signals (`family_friendly`, `budget_fit`,
…) are the intent→signal boundary and were moved to Phase 4, keeping Phase 3
free of any V4 dependency.

`constraints.py` enforces the evidence discipline: a hard constraint FAILs only
on a VERIFIED attribute; EXTRACTED/UNKNOWN routes to UNKNOWN (never a silent pass
or a confirmed violation). Budget is UNKNOWN unless a VERIFIED price basis (plus
party size for per-head bases) establishes a real total — a price range that
straddles the budget is UNKNOWN, not PASS. `filter_candidates` excludes any FAIL
and surfaces UNKNOWN-on-a-stated-constraint candidates separately as
"needs verification" (spec §11), never mixed into verified results.

`normalization.py` merges duplicates conservatively: exact `candidate_id`
repeats collapse; cross-provider matches require a normalized title plus a strong
discriminator (verified event date or coarse coordinates), so title-only
collisions are never fused. The surviving primary (most VERIFIED attributes, then
a deterministic tie-break) only *gains* a VERIFIED attribute another member had
and it lacked — each kept with its own provenance; nothing is overwritten.

Known limitation: distance is not a hard constraint here — the request contract
carries no strict distance limit and providers return coordinates, not verified
travel time. Distance stays a Phase 4 ranking signal (`distance_fit`).

Follow-up resolved: gap #1 provenance/`ConstraintState` dedup — `schemas.py` is
now the single canonical home; `constraints.py` and `evaluation/contracts.py`
import and re-export. Verified single-class identity; full suite 928 passed.
