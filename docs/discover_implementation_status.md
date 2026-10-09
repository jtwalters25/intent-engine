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
  `schemas.py` (Phase 1) and the `evaluation/` subpackage (§16 reference).
- Full backend suite is green: **902 tests passing** (`cd backend && python3 -m
  pytest tests/ -q`).

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

1. **Provenance is defined twice.** `discover/schemas.py` is now the canonical
   home for `AttributeProvenance`/`EvidenceStatus`; `evaluation/contracts.py`
   still carries a byte-compatible copy (it predates schemas). Follow-up: make
   evaluation import from `schemas` and delete the duplicate. Low risk — the
   definitions are identical; sequenced after Phase 3 so the evaluation suite is
   touched once.
2. **No Discover→V4 translation boundary** (`service.py` / `ranking_bridge.py`).
   `DiscoveryRequest` is not yet translated into a validated `IntentPlan`.
3. **No normalization signals** for Discover (`family_friendly`,
   `educational_value`, `budget_fit`, `distance_fit`, `schedule_fit`,
   `duration_fit`) — each needs a documented meaning, range, deterministic
   calc, missing-value handling, and tests (spec §10).
4. **No three-state hard constraints** (`constraints.py`) implementing PASS /
   FAIL / UNKNOWN with the budget-basis distinction (spec §11).
5. **Providers completed in Phase 2.** Ticketmaster and Google Places normalize
   one response page into candidates with explicit provenance. Live credentials,
   provider terms/display review, and multi-provider retrieval composition remain
   later readiness/service work.
6. **No API endpoints** (`/discover`, feedback) or frontend `Discover.tsx` (§14,
   §15). Note the frontend **Agentic Mode** demo on this branch is a separate
   streaming-pilot artifact, not the Discover frontend.
7. **No `evaluation/baselines.py`** — the relevance and LLM-only arms (§16).

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
- Nothing blocks the next code phases (schemas → bridge → constraints), which are
  all pure/offline and reuse merged V4.

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
- [ ] **Phase 3 — Normalization + constraints.** Dedup; the six Discover signals
  with documented range/calc/missing-value rules; three-state hard constraints
  with budget-basis handling. _Fold in gap #1 (dedupe provenance) here._
- [ ] **Phase 4 — Intent Engine integration.** Translate `DiscoveryRequest` →
  `IntentPlan` via `RuleBasedIntentPlanner` + `PlanValidator`, bridge to the
  deterministic ranker; assert reproducible `ranking_fingerprint`.
- [ ] **Phase 5 — Discover API.** `/discover` + feedback endpoints; end-to-end
  mocked pipeline test (request→intent→retrieval→normalize→constraints→rank→
  explain→response).
- [ ] **Phase 6 — Frontend.** `Discover.tsx` + components (input, results, why,
  source links, compare, feedback).
- [ ] **Phase 7 — Feedback + evaluation.** `evaluation/baselines.py` (relevance,
  LLM-only arms); wire `metrics.py` + `decide()` to the three-arm harness.
- [ ] **Phase 8 — Pilot readiness.** Deployment, privacy, cost, reliability.

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

Gap #1 remains a **Phase 3 follow-up**: deduplicate
`AttributeProvenance`/`EvidenceStatus` in `evaluation/contracts.py` by importing
the canonical Discover schemas. Phase 3 also owns normalization, deduplication,
and three-state constraints. Phase 4 will reuse `RuleBasedIntentPlanner` and
`PlanValidator`; neither is called by providers.
