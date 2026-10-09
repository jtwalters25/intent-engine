# Discover Pilot — Readiness (Phase 8)

_Spec: `IntentEngine_Discover_Pilot_Spec.md` §18 (reliability/safety), §21 (cost),
§17 (privacy), §22 (pilot readiness). Last updated 2026-10-09._

Operational reference for running the Discover backend pilot. The code-side
readiness (config, cost controls, reliability behaviors) is in place; the items
under "Before a live pilot" require credentials/decisions that are out of code
scope.

## Configuration (environment)

All read by `discover/config.py` → `DiscoverConfig.from_env()`. Secrets are never
logged. A provider with no key is simply not constructed (graceful degradation).

| Variable | Default | Purpose |
|---|---|---|
| `TICKETMASTER_API_KEY` | — | Enables the Ticketmaster provider |
| `GOOGLE_PLACES_API_KEY` | — | Enables the Google Places provider |
| `DISCOVER_PROVIDER_TIMEOUT` | `5.0` | Per-provider request timeout (s); finite, > 0 |
| `DISCOVER_MAX_RESULTS` | `20` | Candidate cap per provider; 1–200 (cost control) |
| `DISCOVER_LLM_GATEWAY_URL` | — | Enables the LLM-only evaluation arm (off by default) |
| `DISCOVER_FEEDBACK_RETENTION_DAYS` | `30` | Documented feedback retention window |
| `DISCOVER_DEMO_MODE` | `off` | Serve the offline fixture provider — no keys/network (demos only) |

No key for either provider → `/discover/search` returns **502** (retrieval
error), never fabricated results.

### Demo mode (no API keys)

Set `DISCOVER_DEMO_MODE=1` to serve a curated offline fixture pool
(`providers/fixtures.py`) instead of live providers — the whole pipeline
(constraints, ranking, explanations) runs with zero keys and no network, so the
`/discover` page is fully demoable. Fixtures keep the same provenance discipline
as real data (structured facts VERIFIED, `price_basis` UNKNOWN, descriptions
EXTRACTED), so demo behavior matches production. **Do not enable in production** —
it serves fake data and is clearly labeled (`provider: "fixture"`, `demo: true`).

## Cost controls (§21)

- Exactly **one HTTP call per provider per search** — no pagination or details
  fan-out.
- `max_results` bounds candidates per provider (1–200).
- Explicit per-provider timeouts; the request is also deadline-bounded.
- The LLM-only arm is **evaluation-only and disabled by default** (no gateway →
  not available), so normal search spends nothing on an LLM.

## Reliability & safety (§18)

- Typed provider errors (`ProviderConfigError` / `Timeout` / `RateLimited` /
  `ResponseError`); partial failure returns the healthy providers' results with a
  warning, and **all-fail raises `RetrievalError` → 502** (no fabrication).
- Missing keys, empty results, malformed envelopes, and per-item parse failures
  are handled (bad items skipped, safe partial results).
- External provider text is treated as untrusted data — it is never interpreted
  as instructions. Unknown price/age/availability stay UNKNOWN; the ranker/
  constraints never assert them.
- Determinism: identical (request, pool, config, engine version) → identical
  `ranking_fingerprint` (replayable; aligns with §16.1).

## Privacy (§17)

- Feedback (`/discover/feedback`) requires **no account** and collects only
  `request_id` (opaque, non-identifying), a coarse helpfulness enum, an optional
  boolean, and free text (capped). No children's names or precise addresses.
- Current pilot **logs feedback only — it is not persisted.** Before collecting
  real pilot data, add storage that enforces `DISCOVER_FEEDBACK_RETENTION_DAYS`.

## Evaluation gate (§16.2)

Pre-register the go/no-go thresholds **before** recruiting testers. The engine is
scored via `discover/evaluation` (`compute_arm_report` + `decide`) against
human `GroundTruthLabel`s across the three arms (relevance, llm_only,
intent_engine). Primary endpoints are trust, not taste:
`verified_constraint_satisfaction_rate ≥ 0.95`, `critical_factual_error_count = 0`,
`ranking_reproducibility = 1.00`.

## Before a live pilot (out of code scope)

- [ ] Provision `TICKETMASTER_API_KEY` and `GOOGLE_PLACES_API_KEY` (not needed
      for demos — use `DISCOVER_DEMO_MODE=1`).
- [ ] Review Google Places **display/attribution/storage** terms before any UI or
      evaluation persistence (Places data has restrictions); migrate from the
      legacy Text Search / deprecated Ticketmaster `latlong` as needed.
- [ ] Implement feedback persistence + a retention job enforcing the window.
- [ ] Wire a real `LLMClient` behind `DISCOVER_LLM_GATEWAY_URL` (evaluation arm B).
- [ ] Build the Discover frontend (Phase 6) and deploy a reachable Python backend.
- [ ] Pre-register §16.2 thresholds and the session set.
