# Intent Engine Discover — the pitch

_A trustworthy way to discover real-world things to do._

## The problem

Planning real life still means 15 browser tabs. "Something educational and fun
for the kids this Saturday under $100" turns into an hour of cross-checking
prices, ages, hours, and travel across Google, Ticketmaster, and a dozen venue
sites.

AI assistants promise to fix this — but they **make things up**. Ask one for
weekend plans and it will confidently tell you an event is "free and great for
all ages"… and be wrong about the price, the age limit, or whether it's even
happening. When a plan involves **money, your kids, and a schedule**, a
confident wrong answer is worse than no answer at all.

## The wedge: faithfulness, not taste

LLMs are strong at *taste* and structurally weak at *truth*. So we don't compete
on taste. **Intent Engine Discover is built to prove it never made anything up.**

Every attribute it uses carries provenance — `VERIFIED` (from a structured
provider field), `EXTRACTED` (inferred from text), or `UNKNOWN`:

- A hard constraint can **fail only on VERIFIED evidence**. Unknown is never a
  silent "yes."
- It **never asserts an unknown as fact**. A price it can't establish is shown as
  "needs verification," not as "$0 / free."
- Every recommendation's explanation is a set of **grounded claims** — verified
  facts are stated plainly, inferred ones are hedged, and every unknown that
  affects eligibility gets a caveat.
- Ranking is **deterministic and reproducible** — same inputs, same order, same
  fingerprint. You can replay and audit any result.

That's the moat: in a world of plausible-sounding AI, the product a parent can
*trust* wins.

## See it in 30 seconds

Ask: _"Something educational and fun for my kids this Saturday."_

The engine:
1. Pulls real activities, normalizes them into one shape with provenance.
2. **Excludes** an 18+ event the moment a child is in the party — on verified age
   evidence, not a guess.
3. Ranks the rest against the intent (family-fit, educational value, schedule,
   distance, budget).
4. Flags items whose price basis it couldn't verify as **"needs verification"**
   instead of pretending they fit the budget.
5. Explains each pick with evidence-tagged claims and a link to the source.

**Live demo API:** `https://intent-engine-backend.vercel.app` (runs on realistic
fixture data, no keys). The `/discover` page drives the whole flow.

## Why it's defensible

- **Trust is the product.** The hard part isn't ranking — it's *faithful*
  ranking under missing data. That's engineered in, not prompted.
- **Deterministic + auditable.** Reproducible fingerprints and a per-attribute
  evidence ledger mean every recommendation can be explained to a skeptic.
- **Composable.** Discover is an application built on the existing Intent Engine
  (deterministic ranking + grounded explanations), not a throwaway.
- **LLM-optional.** The model may only *rephrase* explanations — it can't add,
  drop, or upgrade a claim. Faithfulness doesn't depend on the model behaving.

## How we'll know it worked (pre-registered)

The pilot is judged on **trust, not taste**:

| Endpoint | Target |
|---|---|
| Verified constraint satisfaction (top-5) | ≥ 0.95 **and** beats LLM-only |
| Critical factual errors | **0** |
| Ranking reproducibility | 1.00 |
| "Needs verification" honesty | ≥ 0.98 |

Preference/relevance are secondary — the engine can lose on taste and still win
by being the only arm a parent can trust.

## Where it goes

Start with family activities (events + places). The same evidence-faithful
engine extends to any high-stakes, real-world discovery where getting price,
timing, eligibility, and availability *right* matters more than sounding good —
travel, local services, accessibility-aware planning, and beyond.

---

_Deep dives: `discover_implementation_status.md` (what's built),
`discover_pilot_readiness.md` (how to run/deploy),
`discover_live_data_todo.md` (path to live provider data)._
