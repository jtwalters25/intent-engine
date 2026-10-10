# Discover — TODO to go live with real provider data

How to move from the offline demo (`DISCOVER_DEMO_MODE=1`) to real results from
Google Places, Ticketmaster, and Eventbrite. Ordered by dependency.

## Status today
- ✅ `TicketmasterProvider` and `GooglePlacesProvider` adapters are built and
  tested against recorded JSON fixtures (parse → provenance → normalize →
  constraints → rank → explain), but have **never run against live APIs**.
- ✅ Demo mode serves a fixture pool so the product is fully demoable with no keys.
- ❌ No live keys, no Eventbrite adapter, no caching/quotas, no feedback storage.

## 1. Credentials & accounts
- [ ] **Ticketmaster** — register for a Discovery API key
  (`developer.ticketmaster.com`); note the default **5 req/s, 5k/day** quota.
- [ ] **Google Places** — create a Google Cloud project, enable **Places API**,
  create an API key, **restrict** it (HTTP referrer/IP + API restriction), and
  set up billing. Decide: legacy **Text Search** (current adapter) vs **Places
  API (New)** — confirm eligibility before launch.
- [ ] **Eventbrite** — create an app, get an OAuth private token
  (`www.eventbrite.com/platform/api`). Note: Eventbrite deprecated public search
  (`/events/search`) — confirm current access tier (org-scoped vs public) before
  committing; if public search is unavailable, treat Eventbrite as
  organizer/venue-scoped or drop it.
- [ ] Store all keys as env vars / secrets — never in the repo or frontend.

## 2. Terms of use / legal (do before any public launch)
- [ ] **Google Places**: review display/attribution/caching/storage limits.
  Places content generally may **not** be stored beyond caching limits or
  combined into an independent dataset — verify before persisting candidates or
  evaluation snapshots. Show required attributions. Keep `html_attributions`.
- [ ] **Ticketmaster**: confirm attribution/branding rules and that linking back
  to the official event URL satisfies terms. Migrate the deprecated `latlong`
  param to `geoPoint`.
- [ ] **Eventbrite**: confirm attribution + allowed use of event data.
- [ ] Document a retention policy consistent with the strictest provider.

## 3. Build the Eventbrite adapter (new)
- [ ] `providers/eventbrite.py` — `EventbriteProvider(BaseProvider)` with
  `_build_request` + `_parse`, mapping structured fields → **VERIFIED**
  provenance (name, start/end, venue lat/long, ticket price when structured),
  text → EXTRACTED, absent → UNKNOWN. **Do not** turn "free-ish" copy into a
  verified $0.
- [ ] Record fixtures (`tests/discover/fixtures/eventbrite_*.json`) and add
  parse/provenance tests mirroring `test_providers.py`.
- [ ] Register it in `config.build_providers` behind `EVENTBRITE_API_TOKEN`.

## 4. Wire live providers into config
- [ ] Extend `DiscoverConfig` with the Eventbrite token (Ticketmaster/Google
  already supported) and per-provider enable flags.
- [ ] `build_providers`: construct each provider only when its key is present
  (already the pattern); keep `DISCOVER_DEMO_MODE` as the offline override.
- [ ] Confirm `retrieve_candidates` partial-failure behavior with 3 providers
  (one down → warn + serve the rest; all down → 502).

## 5. Retrieval hardening (cost, latency, safety — spec §9/§18/§21)
- [ ] **Caching**: add a short-TTL cache keyed by (provider, normalized query,
  location, date window) to cut duplicate calls and cost. Respect provider cache
  limits.
- [ ] **Quotas/limits**: cap results per provider (`DISCOVER_MAX_RESULTS`),
  enforce timeouts (done), add simple rate-limit backoff for 429s.
- [ ] **Geocoding**: the request takes a free-text location but never infers a
  precise coordinate. Add an explicit geocode step (Google Geocoding) only if a
  provider needs lat/long, and treat the result as its own evidence.
- [ ] **Dedup across 3 providers**: validate the cross-provider fingerprint on
  real data (same event from Ticketmaster + Eventbrite) and tune.
- [ ] Keep treating all provider text as untrusted (prompt-injection test
  already covers this).

## 6. Flip from demo to live
- [ ] Set provider keys in the backend Vercel project; set
  `DISCOVER_DEMO_MODE=0` (or unset).
- [ ] Smoke-test `/discover/search` against each provider individually, then
  combined; verify provenance (TM price VERIFIED, Google price_level NOT money,
  unknowns stay UNKNOWN).
- [ ] Add a lightweight integration test tier that can optionally hit live APIs
  (off by default; recorded fixtures remain the standard suite — spec §19).

## 7. Feedback persistence & privacy (spec §17)
- [ ] Replace the log-only `/discover/feedback` with a store (e.g. a Vercel
  Marketplace Postgres) and a retention job honoring
  `DISCOVER_FEEDBACK_RETENTION_DAYS`.
- [ ] Keep it account-free and PII-light (opaque `request_id` only).

## 8. Evaluation on real data (spec §16)
- [ ] Wire the three arms (`relevance`, `llm_only`, `intent_engine`) to live
  candidate pools; have a human create `GroundTruthLabel`s per session.
- [ ] Implement a real `LLMClient` behind `DISCOVER_LLM_GATEWAY_URL` for arm B.
- [ ] Pre-register §16.2 go/no-go thresholds before recruiting testers.

## 9. Frontend for production
- [ ] Set `VITE_API_BASE_URL` to the backend URL in the frontend Vercel project
  (prod + preview) and redeploy the frontend with the Discover code on `main`.
- [ ] Add required provider attributions to the results UI.

## Quick reference — env vars
| Var | Purpose |
|---|---|
| `TICKETMASTER_API_KEY` | Ticketmaster Discovery |
| `GOOGLE_PLACES_API_KEY` | Google Places |
| `EVENTBRITE_API_TOKEN` | Eventbrite (new adapter) |
| `DISCOVER_DEMO_MODE` | `1` = offline fixtures; `0`/unset = live |
| `DISCOVER_MAX_RESULTS` | per-provider cap (cost control) |
| `DISCOVER_PROVIDER_TIMEOUT` | per-provider timeout seconds |
| `DISCOVER_LLM_GATEWAY_URL` | enables the LLM-only evaluation arm |
| `DISCOVER_FEEDBACK_RETENTION_DAYS` | feedback retention window |
