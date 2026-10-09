1. Product vision
Product name
Intent Engine Discover
Tagline
Find what fits your life, not what gets the most clicks.
Product thesis
Traditional discovery systems largely organize results around keyword relevance, popularity, engagement, advertising, or historical behavior.
Intent Engine Discover introduces another approach:
Retrieve information from existing platforms, understand what the user wants to accomplish, and deterministically rank available options against that intent.
The product does not attempt to replace Google, Ticketmaster, Yelp, or existing marketplaces.
It operates as an intelligent discovery layer over permitted external data sources.
Example
A user enters:
Find something educational and fun for my four kids this Saturday. We're near Seattle, have about three hours, and want to spend less than $100.

The system should:
1. Interpret the user's goal.
2. Extract constraints and preferences.
3. Retrieve relevant activities from external providers.
4. Normalize results into a common candidate schema.
5. Apply verified hard constraints.
6. Rank eligible options against the user's intent.
7. Explain the recommendations.
8. Link users directly to the original providers.
9. Collect feedback on recommendation usefulness.
The system must not fabricate availability, pricing, operating hours, or suitability.
2. Business hypothesis
The initial experiment tests three hypotheses.
H1: Discovery quality
Users prefer intent-based recommendations over conventional relevance ranking.
H2: Decision efficiency
Users identify a suitable activity faster when recommendations account for their goals and constraints.
H3: Reusability
The same intent-planning and ranking infrastructure can support additional discovery domains without rewriting the core engine.
Success criteria
Metric	Pilot target
Real users	10
Completed discovery sessions	20
Users preferring intent-based results	70%
Sessions producing an actionable option	80%
Median time to useful option	Under 2 minutes
Critical factual errors	0
Users willing to return	70%
Working external data integrations	2


These are directional pilot thresholds, not statistically conclusive evidence of product-market fit.
3. Scope
In scope
- Natural-language discovery requests
- Location-aware retrieval using user-provided location
- Ticketmaster Discovery API integration
- Google Places API integration
- Common candidate schema
- Data provenance and freshness metadata
- V4 intent interpretation and validation
- Deterministic candidate ranking
- Hard-constraint handling
- Recommendation explanations
- Source links
- Basic feedback collection
- Baseline comparison
- Lightweight responsive web UI
- Integration tests and evaluation fixtures
Out of scope
- User accounts
- Payments
- Booking transactions
- Social networking
- Reviews and user-generated content
- Long-term personalization
- Automated web scraping
- Browser automation
- Autonomous purchasing
- Mobile applications
- Subscription billing
- Multi-agent frameworks
- New recommendation ML models
Do not expand scope without explicit approval.
4. System architecture
                 USER
                   |
                   v
         DISCOVERY REQUEST
                   |
                   v
          V4 INTENT LAYER
          ----------------
          Context Interpreter
          Intent Planner
          Plan Validator
                   |
                   v
          DISCOVERY CONTEXT
                   |
                   v
          RETRIEVAL SERVICE
          ----------------
          Ticketmaster Adapter
          Google Places Adapter
                   |
                   v
          NORMALIZATION LAYER
          -------------------
          Unified Candidate
          Provenance Metadata
          Attribute Validation
          Deduplication
                   |
                   v
          POLICY / CONSTRAINTS
          --------------------
          Hard Constraint Gates
          Unknown-Value Handling
                   |
                   v
          INTENT RANKING ENGINE
          ---------------------
          Deterministic Scoring
          Stable Tie Breaking
          Score Breakdown
                   |
                   v
          RECOMMENDATION API
                   |
                   v
          DISCOVER FRONTEND
          -----------------
          Ranked Results
          Why This Fits
          Source Links
          Compare Rankings
                   |
                   v
          FEEDBACK / EVALUATION

Architectural rule
Discover is an application built on Intent Engine, not a replacement for Intent Engine.
Keep retrieval, normalization, planning, ranking, and presentation independently testable.
5. Repository structure
Codex should inspect the actual repository before deciding exact paths.
Suggested additions:
backend/
  intent_engine/
    discover/
      __init__.py
      schemas.py
      service.py
      normalization.py
      constraints.py
      ranking_bridge.py
      provenance.py

      providers/
        __init__.py
        base.py
        ticketmaster.py
        google_places.py

      evaluation/
        baselines.py
        metrics.py

  tests/
    discover/
      test_schemas.py
      test_normalization.py
      test_constraints.py
      test_ranking.py
      test_providers.py
      test_service.py
      test_evaluation.py

frontend/
  src/
    pages/
      Discover.tsx

    components/
      discover/
        DiscoveryInput.tsx
        RecommendationCard.tsx
        RecommendationList.tsx
        ExplanationPanel.tsx
        ComparisonView.tsx
        FeedbackPanel.tsx

docs/
  IntentEngine_Discover_Pilot_Spec.md
  discover_implementation_status.md

These paths are proposals, not mandates. Reuse existing code where appropriate.
6. Discovery request contract
Introduce a typed DiscoveryRequest.
class DiscoveryRequest(BaseModel):    query: str    location: str | None = None    latitude: float | None = None    longitude: float | None = None    start_date: date | None = None    end_date: date | None = None    budget_total: Decimal | None = None    party_size: int | None = None    children_ages: list[int] = Field(default_factory=list)    duration_minutes: int | None = None    request_id: str | None = None


All numerical inputs require sensible validation limits.
The system should not silently infer precise location.
Example
{
  "query": "Find something educational and fun for my kids this Saturday",
  "location": "Seattle, WA",
  "budget_total": "100.00",
  "party_size": 5,
  "children_ages": [7, 9, 10, 12],
  "duration_minutes": 180
}

The request should be translated into validated V4 intent.
7. Unified candidate contract
External providers return different data structures.
Discover must normalize them into a common representation.
class DiscoveryCandidate(BaseModel):    candidate_id: str    provider: str    provider_id: str    title: str    description: str | None = None    category: str | None = None    location_name: str | None = None    latitude: float | None = None    longitude: float | None = None    start_time: datetime | None = None    end_time: datetime | None = None    price_min: Decimal | None = None    price_max: Decimal | None = None    currency: str | None = None    age_min: int | None = None    age_max: int | None = None    source_url: str    retrieved_at: datetime    attributes: dict[str, Any] = Field(default_factory=dict)


Critical requirement
Missing information must remain missing.
For example:
{
  "title": "Family Science Experience",
  "price_min": null,
  "price_max": null,
  "age_min": null,
  "age_max": null
}

The system must not interpret unknown price as free.
It must not interpret unknown age suitability as appropriate for all ages.
7.1 Attribute provenance (evidence contract)
The top-level candidate fields are a convenience view. The authoritative record for evidence is per-attribute provenance: every ranking-relevant attribute carries where it came from and how trustworthy it is. Ranking, constraints, and explanations may rely only on an attribute's provenance, never on a bare value.

class AttributeProvenance(BaseModel):
    value: Any | None
    status: Literal["VERIFIED", "EXTRACTED", "UNKNOWN"]
    # VERIFIED  — copied from a structured provider field (e.g. Ticketmaster priceRanges)
    # EXTRACTED — inferred from unstructured text / classifier / LLM; NOT a fact
    # UNKNOWN   — absent; no value may be asserted
    source: str                    # provider id
    source_field: str | None       # the structured field, when VERIFIED
    source_url: str
    retrieved_at: datetime
    extractor: str | None = None   # model/classifier id + version, when EXTRACTED

Rules:
- A hard constraint may FAIL only on a VERIFIED attribute. An EXTRACTED or UNKNOWN attribute routes to constraint-state UNKNOWN (see Section 11) — never to a confirmed violation and never to a silent pass.
- An explanation may present an attribute as fact only if status == VERIFIED. EXTRACTED values must be hedged ("appears to be ..."); UNKNOWN must surface as "needs verification".
- No attribute is upgraded from EXTRACTED to VERIFIED without a structured source.
This is the pilot's most important evidence contract: it is what lets the system prove it did not fabricate price, hours, age suitability, or availability. Attribute-extraction accuracy is the quality ceiling of the whole product, so EXTRACTED attributes must be labeled, measured, and never silently treated as VERIFIED.
8. Provider integrations
Provider A: Ticketmaster
Use the official Ticketmaster Discovery API.
Documentation:
https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
Retrieve relevant event information such as:
- Event name
- Event category
- Date and time
- Venue
- Location
- Price range when available
- Official event URL
Implement:
class TicketmasterProvider:    async def search(        self,        request: DiscoveryRequest    ) -> list[DiscoveryCandidate]:        ...


Provider B: Google Places
Use the official Google Places API.
Documentation:
https://developers.google.com/maps/documentation/places/web-service/overview
Retrieve permitted information about:
- Museums
- Parks
- Attractions
- Family entertainment venues
- Educational destinations
- Other relevant places
Implement:
class GooglePlacesProvider:    async def search(        self,        request: DiscoveryRequest    ) -> list[DiscoveryCandidate]:        ...


Provider requirements
Both providers must support:
- Timeouts
- Error handling
- Rate-limit handling
- Configurable request limits
- Environment-based API keys
- Structured logging
- Provider-specific validation
- Safe partial results
Do not expose API keys in the frontend.
Respect each provider's current terms governing caching, storage, attribution, and display. In particular, Google Maps Platform data has restrictions that must be reviewed before combining, storing, or displaying Places data in an independent experience.
If the intended UI violates a provider's terms, document the conflict and use an authorized alternative rather than implementing a workaround.
9. Retrieval strategy
Do not initially use autonomous agents to browse the internet.
Use deterministic provider adapters.
async def retrieve_candidates(request):    results = await gather_provider_results(request)    normalized = normalize_candidates(results)    deduplicated = deduplicate_candidates(normalized)    return deduplicated


Retrieval rules
- Limit the number of external calls.
- Use explicit timeouts.
- Deduplicate overlapping results.
- Preserve provider attribution.
- Preserve original source URLs.
- Track retrieval failures.
- Do not fabricate results when a provider fails.
- Respect provider-specific retention restrictions.
Partial failure
If Ticketmaster fails but Google Places succeeds, return available permitted results with a warning.
If all providers fail, return a clear retrieval error.
Do not silently substitute invented candidates.
10. Intent Engine integration
This is the most important technical section.
Discover must reuse the existing V4 architecture where possible.
Expected conceptual flow:
DiscoveryRequest
      |
      v
ContextInterpretation
      |
      v
IntentPlan
      |
      v
PlanValidator
      |
      v
DiscoveryIntent
      |
      v
Deterministic Ranker

Codex must inspect the actual Phase 1 and Phase 2 implementation before creating integration code.
Do not duplicate the planner
If RuleBasedIntentPlanner already exists, use it.
If V4 does not yet support the Discover domain, introduce a narrowly scoped adapter or translation boundary.
Do not create an entirely separate intent-planning framework.
Normalization boundary
The Discover adapter must translate domain-specific concepts into supported ranking signals.
Examples:
family_friendly
educational_value
budget_fit
distance_fit
schedule_fit
duration_fit

Every signal requires:
- A documented meaning
- A defined range
- A deterministic calculation
- Explicit handling of missing values
- Unit tests
Do not invent unsupported signals inside the ranker.
11. Hard constraints
Hard constraints execute before ranking.
Examples include:
- Event occurs outside the requested date window.
- Known total price exceeds a strict budget.
- Known minimum age exceeds a child's age when the activity requires every participant to meet that minimum.
- Destination exceeds a strict distance limit.
- Activity is explicitly unavailable.
Unknown values
Unknown does not equal compliant.
Unknown also does not automatically equal a violation.
Use three states:
PASS
FAIL
UNKNOWN

For hard constraints:
- FAIL: exclude.
- PASS: eligible.
- UNKNOWN: handle according to explicit policy.
For the pilot, unknown eligibility should be shown separately as Needs verification, not mixed into fully verified recommendations.
Budget handling
A price range is not necessarily the total family cost.
The system must distinguish:
price_per_person
price_per_ticket
price_per_group
total_price
unknown_price_basis

If the total cost cannot be established, do not claim that the option fits the budget.
12. Deterministic ranking
Use the existing ranking engine or its supported extension points.
Do not introduce LLM-generated scores.
A possible domain-specific model is:
final_score =
    base_relevance
    × goal_fit
    × schedule_fit
    × budget_preference_fit
    × distance_preference_fit
    × family_fit

This formula is illustrative.
Codex must inspect the existing ranking contracts before implementing the actual model.
Important distinction
Strict budget and distance limits belong in the constraint layer.
Soft preferences can influence ranking.
Do not let a high relevance score override a failed hard constraint.
Determinism
Given identical:
- Validated intent
- Candidate snapshot
- Ranking configuration
- Evaluation timestamp
- Engine version
the system must produce identical ranking results.
13. Explainability
Every recommendation should answer:
Why does this fit my request?
Example:
Recommended because it matches your educational preference, occurs within your requested time window, and is approximately 20 minutes from your selected location. Admission cost requires verification.

Explanations must derive from actual candidate attributes and ranking decisions.
The system must not claim evidence that is absent.
Developer explanation
Expose:
{
  "candidate_id": "ticketmaster_123",
  "rank": 1,
  "score": 0.84,
  "signals": {
    "goal_fit": 0.95,
    "schedule_fit": 1.0,
    "distance_fit": 0.82
  },
  "constraints": {
    "date": "PASS",
    "budget": "UNKNOWN"
  }
}

Values above are illustrative.
13.1 Explanation grounding (evidence contract)
An explanation is a set of atomic claims. Every claim cites the candidate attribute and provenance it rests on. A claim whose supporting attribute is not VERIFIED may not be stated as fact.

class ExplanationClaim(BaseModel):
    text: str
    kind: Literal["match", "tradeoff", "caveat"]
    attribute: str                 # e.g. "schedule", "distance", "price", "age"
    evidence_status: Literal["VERIFIED", "EXTRACTED", "UNKNOWN"]
    signal: str | None = None      # the ranking signal this claim derives from, if any

Rules:
- Claims are generated from ranking signals and constraint results, not written freely. Each match/tradeoff claim maps to one signal or one PASS/FAIL constraint; each caveat maps to an UNKNOWN constraint or an EXTRACTED value.
- An explanation MUST include a caveat for every UNKNOWN that affected eligibility (price, age, availability). Silence on a relevant unknown is a defect, not a cleaner UI.
- The rendered sentence is a deterministic template over these claims. The optional LLM may only rephrase; it may not add, drop, or upgrade a claim. The pre-LLM claim set is retained as evidence and is what explanation_accuracy is scored against (Section 16).
14. API endpoints
Suggested endpoints:
POST /discover/search

POST /discover/feedback

POST /discover/evaluate

GET /discover/health

Search response
{
  "request_id": "req_123",
  "intent": {
    "objective": "family_educational_activity"
  },
  "recommendations": [],
  "needs_verification": [],
  "excluded_count": 4,
  "provider_status": {
    "ticketmaster": "success",
    "google_places": "success"
  },
  "trace_id": "trace_123"
}

The response must distinguish verified recommendations from uncertain options.
15. Frontend
Add a dedicated Discover route.
Suggested:
/discover

Do not replace the existing /demo.
Screen 1: Discovery input
Main heading:
What are you trying to do?
Subheading:
Tell us your goal. We'll find options that fit.
Input example:
Something educational for my kids this weekend, under $100.

Include an optional location field.
A user must be able to submit without creating an account.
Screen 2: Recommendations
Show five results initially.
Each card includes:
- Name
- Category
- Location
- Date/time where applicable
- Verified or unknown price
- Why it fits
- Verification warnings
- Source attribution
- Original listing link
Screen 3: Comparison
Allow users to compare:
Standard relevance ranking
versus
Intent Engine ranking
Do not imply that the standard ranking represents Google's proprietary algorithm.
The baseline should be explicitly identified as a simple relevance-based ranking of the same retrieved candidates.
Screen 4: Feedback
Ask:
Did these recommendations help you find something you would actually do?

Capture:
YES
SOMEWHAT
NO

Also capture optional feedback on the selected recommendation.
16. Evaluation framework
The pilot runs TWO separate experiments. Conflating them is the most common way to misread the result, so they are defined, measured, and reported separately.

Experiment R — Ranking quality (isolates the engine)
A fixed, identical candidate pool with identical VERIFIED metadata is given to all three ranking arms. This measures ranking and constraint handling ONLY; retrieval and UI are held constant. Experiment R is what proves or disproves H1's technical core: that deterministic, constraint-faithful ranking beats the alternatives given the SAME information.

Experiment E — End-to-end discovery (measures the product)
The full pipeline (retrieval -> normalization -> constraints -> ranking -> explanation -> UI) versus a human doing the same research across conventional tools (timed, manual; no SERP scraping). This measures the product, including retrieval and effort. A good E result driven by UI polish, or a weak E result driven by thin provider data, must NOT be read as a ranking result — that is what Experiment R isolates.

Primary endpoints (trust, not taste)
The defensible wedge is faithfulness, not aesthetic ranking quality, and an LLM is structurally strong at taste. Primary endpoints are therefore:
1. verified_constraint_satisfaction_rate (top-5)
2. critical_factual_error_count
Preference and relevance are SECONDARY. The engine can win on taste and still fail if it misstates facts; it can lose on taste and still win if it is the only arm a parent can trust.

Arms (every session gives all arms the same candidate pool)
A. Relevance baseline — keyword/popularity ranking of the pooled candidates. Labeled in-product as "simple relevance baseline", never as Google's algorithm.
B. LLM-only — same pool, same VERIFIED/EXTRACTED/UNKNOWN provenance, explicitly instructed not to assert unknowns. Giving it the same provenance means the comparison tests behavior (does it stay faithful?), not an information handicap. Evaluation-only; not the default experience.
C. Intent Engine — validated intent, three-state constraints, deterministic ranking, grounded explanations (Section 13.1).

Blinding and order
Experiment R is run blind: arm branding stripped, ranked lists of the SAME items, order randomized per session and recorded in the evidence ledger. Testers do not learn which list is the engine until after scoring (Section 23). No arm may access information another arm lacks unless running Experiment E.

Ground truth (how endpoints are scored objectively)
Before a session is scored, a human verifier resolves each top-5 candidate's price, schedule, age policy, and travel time against the source URL and records a GroundTruthLabel. Endpoints are computed against these labels, not against an arm's own claims. Labeling is done once per candidate pool and shared across arms, so all arms are judged on identical truth.
Evaluation metrics (operational definitions — these ARE the definitions, fixed before any data is collected)
All rates are numerator/denominator over the pre-registered session set. Report per-arm with n and the exact session ids.

| Metric | Definition | Computed from | Pre-registered target |
|---|---|---|---|
| verified_constraint_satisfaction_rate | share of top-5 whose VERIFIED attributes satisfy every stated hard constraint under ground truth | GroundTruthLabel | Engine >= 0.95 AND strictly > LLM-only |
| critical_factual_error_count | count of claims an arm presents as fact that ground truth contradicts (wrong price/hours/open/"kid-friendly") | claims x labels | Engine = 0 |
| constraint_violation_rate | share of top-5 that are a confirmed hard-constraint FAIL under ground truth | GroundTruthLabel | Engine = 0 (FAILs are excluded by design) |
| needs_verification_honesty | share of UNKNOWN-eligibility items correctly shown as "needs verification" rather than asserted | claims x labels | Engine >= 0.98 |
| explanation_accuracy | share of ExplanationClaims whose evidence_status matches ground truth and whose VERIFIED claims are confirmed | claims x labels | Engine >= 0.95 |
| ranking_reproducibility | share of identical (intent, snapshot, config, version) inputs that reproduce an identical ranking_fingerprint | replay | 1.00 |
| top_5_relevance | mean blind rater relevance (1-5) of top-5 to the stated goal | human rater | SECONDARY — report, do not gate |
| user_preference_rate | share of blind sessions where the tester prefers the engine's list | Section 23 | SECONDARY — target 0.70 |
| time_to_first_useful_result | median seconds from submit to the tester marking an option they would act on | session timing | < 120s (Experiment E) |
| provider_error_rate | provider calls returning error/timeout ÷ total provider calls | logs | report |
| cost_per_search | (provider + LLM spend) ÷ searches | logs | within Section 21 budget |
| search_latency_ms | p50 / p95 end-to-end latency | logs | report |

16.1 Evaluation evidence ledger (evidence contract)
Every evaluation session emits one immutable record sufficient to reproduce and audit the comparison. This is the artifact a skeptic reviews.

class EvaluationSession(BaseModel):
    session_id: str
    request: DiscoveryRequest
    validated_intent: dict                      # canonical IntentPlan used by arm C
    candidate_pool: list[DiscoveryCandidate]    # the shared snapshot, with provenance
    pool_fingerprint: str                       # stable hash of the normalized pool
    arms: dict[str, ArmResult]                  # "relevance" | "llm_only" | "intent_engine"
    ground_truth: list[GroundTruthLabel]
    presentation_order: list[str]               # randomized arm order shown to the tester
    engine_version: str
    config_version: str
    created_at: datetime

class ArmResult(BaseModel):
    ranking: list[str]                          # candidate_ids, in order
    explanations: dict[str, list[ExplanationClaim]]
    ranking_fingerprint: str | None             # engine arm only; see below
    metrics: dict[str, float]

class GroundTruthLabel(BaseModel):
    candidate_id: str
    verified_price_basis: Literal["per_person","per_ticket","per_group","total","unknown"]
    verified_total_cost: Decimal | None
    verified_within_date_window: bool | None
    verified_min_age: int | None
    verified_distance_minutes: float | None
    verified_at: datetime
    verifier: str

Reproducibility fingerprint
ranking_fingerprint = stable hash over (canonical validated_intent, pool_fingerprint, config_version, engine_version). It EXCLUDES latency, trace_id, wall-clock timestamps, and presentation order. ranking_reproducibility asserts that two runs with the same fingerprint inputs produce byte-identical (ranking, scores, pre-LLM explanation claims). This mirrors the V4 determinism contract and the V4 security plan's replay-equality set.

16.2 Pre-registered go / no-go
Register these thresholds BEFORE recruiting testers; they map directly to Section 23. Do not move them after seeing results.
- CONTINUE: Engine meets all PRIMARY targets (satisfaction >= 0.95, factual errors = 0, reproducibility = 1.00) AND preference >= 0.70 AND strictly beats LLM-only on at least one primary endpoint.
- IMPROVE: Primary endpoints met, but preference < 0.70 or time_to_first_useful_result >= 120s (idea works; data/UI weak).
- PIVOT: LLM-only matches or beats the engine on BOTH primary endpoints with less complexity, OR the engine cannot reach factual errors = 0.

Define metric calculations before collecting pilot results.
17. Feedback telemetry
Introduce:
class DiscoveryFeedback(BaseModel):    request_id: str    selected_candidate_id: str | None = None    helpfulness: str    would_use_again: bool | None = None    feedback_text: str | None = None


Track only the information necessary for the experiment.
Do not require accounts.
Avoid collecting children's names, precise home addresses, or unnecessary personal information.
Use request identifiers that do not expose identity.
Set a documented retention period for pilot feedback.
18. Reliability and safety
The pilot must handle:
- Missing API keys
- Provider timeouts
- Rate limits
- Empty search results
- Duplicate candidates
- Missing prices
- Missing age restrictions
- Invalid location inputs
- Malformed provider responses
- Invalid agent output
- Unavailable LLM service
- Expired event dates
- Prompt injection embedded in external descriptions
Treat external descriptions as untrusted data.
Never interpret a provider's description as instructions to the application.
Fallback behavior
If intent planning fails, return a clearly labeled deterministic relevance-based result when safe.
If candidate retrieval fails entirely, return an error rather than fabricated recommendations.
19. Testing requirements
Implement unit tests for:
- Discovery request validation
- Provider response normalization
- Candidate deduplication
- Provenance preservation
- Hard constraints
- Unknown-value handling
- Budget calculations
- Deterministic ranking
- Explanation accuracy
- Provider failures
- Prompt-injection resistance
- API contracts
- Feedback validation
Use recorded, legally retainable test fixtures or synthetic data.
Do not require live external API calls in the standard test suite.
Integration tests
Use mocked provider clients to verify the complete pipeline:
Request
→ Intent
→ Retrieval
→ Normalization
→ Constraints
→ Ranking
→ Explanation
→ Response

Existing V3 and V4 tests must remain green.
20. Implementation phases
Codex must implement one phase at a time.
Phase	Deliverable	Exit criteria
0	Repository assessment	V4 integration points identified
1	Discover schemas	Contracts and validation tests pass
2	Provider integrations	Two providers work with mocked tests
3	Normalization and constraints	Validated candidates and correct filtering
4	Intent Engine integration	Deterministic ranked results
5	Discover API	End-to-end backend test passes
6	Frontend	User can search and inspect results
7	Feedback and evaluation	Baselines and metrics work
8	Pilot readiness	Deployment, privacy, cost, and reliability checks pass


Do not implement later phases automatically.
Phase 0 is mandatory
Before writing code, Codex must:
1. Inspect the repository.
2. Determine current V4 implementation status.
3. Identify existing reusable components.
4. Identify integration gaps.
5. Review provider requirements.
6. Identify any blockers.
7. Produce a concrete implementation plan.
If V4 orchestration is incomplete, the pilot should integrate only with stable V4 capabilities and explicitly document deferred functionality.
21. Cost controls
This is a bootstrapped pilot.
Implement:
- Configurable provider request limits
- API usage logging
- Server-side secrets
- Query throttling
- Daily usage limits
- LLM calls disabled by default
- Development fixtures for offline testing
Target
Aim for an initial infrastructure budget of $25–$50 per month, subject to actual provider pricing and usage.
Do not assume the provider APIs are free.
Do not purchase paid infrastructure without approval.
22. Pilot readiness
The application is ready for external testers when:
- A user can enter a natural-language goal.
- Real permitted provider data is retrieved.
- Candidate data is normalized.
- Hard constraints execute correctly.
- Unknown values are visibly identified.
- Intent Engine produces deterministic rankings.
- Every recommendation has a traceable explanation.
- Original source links work.
- Feedback can be collected.
- API keys remain server-side.
- Provider terms have been reviewed.
- Existing tests pass.
- The application can be deployed without exposing internal development functionality.
23. Business validation
After deployment, recruit 10 testers.
Ask them to complete real discovery tasks.
Do not explain which ranking method is yours before they evaluate the results.
Capture:
- Preferred ranking
- Selected activity
- Time to selection
- Perceived usefulness
- Incorrect or misleading information
- Willingness to use again
Go/no-go decision
Continue: Strong user preference, reliable recommendations, and evidence of repeat demand.
Improve: Users find the idea useful but data quality or ranking performance is insufficient.
Pivot: LLM-only or conventional search consistently matches or exceeds Intent Engine with less complexity.
Do not expand into additional verticals until this decision is made.
24. Future expansion
Only after validating the pilot, consider additional domains:
- Product discovery
- Restaurants
- Travel
- Educational resources
- Entertainment
- Local services
Each should reuse the same core discovery contracts and deterministic ranking infrastructure.
The long-term architecture should support an SDK and API, but the pilot must not prematurely implement a generalized platform.
25. Definition of done
Intent Engine Discover MVP is complete when a user can enter:
Find an affordable educational activity for my kids this weekend.

And the system:
1. Interprets the goal.
2. Retrieves real external candidates.
3. Normalizes and validates candidate information.
4. Applies hard constraints.
5. Handles unknown information explicitly.
6. Produces deterministic intent-based rankings.
7. Explains each recommendation.
8. Links to the original source.
9. Collects feedback.
10. Supports a fair baseline comparison.
11. Records sufficient information to reproduce ranking decisions, within provider data-retention permissions.
The primary deliverable is a validated discovery experience, not another abstract agent framework.