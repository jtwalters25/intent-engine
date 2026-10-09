# Optional V4 model assistance

Phase 7 is disabled by default and independent of the legacy `LLM_ENABLED`
adapter. Rules-resolvable requests retain identical plans and make no network
call. Model assistance currently supports streaming only and the same five
objectives as the deterministic planner; it does not invent executable actions,
temporal templates, candidates, scores, or policy.

## Enable on the backend

Set these server environment variables before starting the application:

- `V4_LLM_ENABLED=true`
- `V4_LLM_ENDPOINT=https://your-controlled-gateway.example/interpret`
- `V4_LLM_API_KEY` — a secret bearer token
- `V4_LLM_MODEL` — gateway-specific model identifier

Enabling without complete valid configuration fails application startup.
Never use frontend `VITE_*` variables for credentials. Restart to apply changes.
No commercial provider or gateway is provisioned by this repository. An
operator must supply a trusted HTTPS interpretation gateway implementing the
following contract, or inject an `InterpretationProvider` in Python. There is
no live-model integration claim in the mocked test results.

## Gateway contract

POST JSON contains `task`, `model`, `instructions`, `objectives`, `context_keys`,
`input`, and `response_schema`. `input` contains only goal text, domain and
explicit context. It excludes server identities, profile authority, clock,
candidate catalog and credentials. The key is sent only as a bearer header.
Assess user-text privacy, consent, provider retention and data processing terms
before enabling an external gateway.

Return a raw JSON `ContextInterpretation` object (not a chat/completion envelope
or Markdown). All contract fields are required. Canonical objective values are
`wind_down`, `focus`, `family_time`, `quick_session`, and `high_energy`.
`entities` and `inferred_context` may contain only `energy` (0–1), `viewer`
(`kids`, `teen`, `family`, `adult`), and `horizon_minutes` (objective-specific
minimum through 240). Confidence must be at least 0.7. Constraints remain soft
USER/INFERRED input, never hard or SYSTEM/DOMAIN authority. Server profile and
hard constraints remain authoritative regardless of model or user assertions.

Only unsupported/ambiguous objective resolution invokes the gateway; malformed
context, excessive text, unsupported domains and other rules errors remain
rejections. Model responses are capped at 32 KiB, reject duplicate keys,
nonfinite numbers, extra fields, unknown signals and invalid semantic values.
Valid explicit context takes precedence over validated model inference.

Gateway requests use a five-second socket timeout, no redirects and no retries.
This is not a total wall-clock deadline against a slow-trickling server; a
production gateway should enforce its own total deadline, concurrency/rate
limits and budget. The synchronous plan route runs in FastAPI's worker pool so
model I/O does not block its async event loop. Public rate limiting, provider
quotas and deployment monitoring remain production prerequisites.

## Failure behavior

Transport failures (including timeout/429/5xx), malformed or uncertain model
output produce a validated `safe_fallback` plan, not a guessed objective.
Only canonical explicit context and domain defaults influence its single step;
the trusted maturity gate remains present. Confidence is zero, and assumptions
and transition reason explain fallback without exposing raw provider errors.
The same deterministic normalizer, validator, orchestrator and ranker execute
both assisted and fallback plans. Ranking is never delegated to a model.

Fallback defaults to a 30-minute lifetime, or a valid explicit horizon.
With no explicit energy it uses existing adapter defaults; no scoring formula
or safety behavior was changed. Execution revalidates all plans at current
server time and policy, as before.

Arbitrary model-authored temporal plans and direct vendor SDK adapters are
intentionally deferred. Phase 8 outcome ingestion is not implemented here.
