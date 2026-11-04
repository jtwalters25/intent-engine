# Design decisions

The story of the system design — the questions I had to answer and the constraints
I imposed before using AI to execute them fast. It's a lightweight
[ADR](https://adr.github.io/) log, but the useful part isn't the answers; it's the
**questions** and the **guardrails**. AI wrote much of the code, the tests, and the
first drafts of these docs. It did not choose the trust model, the safety
invariants, the kill-criteria, or the product framing — those were decisions, and
each one became a constraint the AI had to execute within.

The through-line: **I set the intent and the constraints; AI accelerated the
execution.** The way I built it mirrors what it does — human intent and policy in
front, deterministic and auditable execution behind.

Format per decision: the **question** I had to answer, the **tension** that made it
non-obvious, the **decision**, the **guardrail** I gave the AI, and the **result**.

---

### 1. Should an LLM ever choose the recommendation?

- **Tension:** LLMs read messy human goals well, but they're unreliable on
  reproducibility, policy enforcement, and not fabricating. I wanted the
  natural-language understanding without surrendering control of the actual decision.
- **Decision:** A hard trust boundary — the agent may *propose* intent; deterministic
  code validates it, enforces safety, ranks, and explains. The model never picks the
  winner. (`IntentEngine_v4_Spec.md`)
- **Guardrail:** LLM output is untrusted input — schema-validated, range-checked,
  fail-closed to deterministic ranking. Invalid output degrades to a safe default,
  never a 500 or an unsafe pick.
- **Result:** The V4 contracts and ~1,200 tests encode these invariants. AI wrote most
  of the plumbing; every boundary was my decision and a test I required.

### 2. A learned ranking model, or a deterministic one?

- **Tension:** ML could learn preferences, but it's a black box — you can't explain or
  reproduce a given order, and you can't audit a safety decision.
- **Decision:** A deterministic multiplier chain
  (`base × time × viewer × energy × device × prophecy + diversity`) with reproducible
  fingerprints; every score decomposes into named signals.
- **Guardrail:** No randomness, no personalization, same input → same output; the LLM
  may never mutate the formula.
- **Result:** Any ranking anomaly traces to the signal that caused it. And I kept the
  honest limitation in the README: deterministic scoring can't measure *causal lift*
  (no randomized holdouts). I didn't paper over the weakness.

### 3. How do you stay honest when the data is missing?

- **Tension:** Real-world data is full of holes, and the tempting move — the LLM
  default — is to fill them with a confident value.
- **Decision:** A provenance ledger — every attribute is `VERIFIED` / `EXTRACTED` /
  `UNKNOWN`. A hard constraint fails only on `VERIFIED` evidence; unknowns surface as
  "needs verification," never a fabricated fact.
- **Guardrail:** `UNKNOWN` attributes may not carry a value (enforced in the schema);
  the LLM may rephrase an explanation but cannot add, drop, or upgrade a claim.
- **Result:** The product can prove it never asserted something it couldn't verify —
  the "trust, not taste" wedge.

### 4. Is "over-stimulating" the same as "adult"?

- **Tension:** Age ratings are the only per-title signal most people know, but a `TV-Y`
  show can be hyper-stimulating and a `PG` film calm. Conflating them is wrong.
- **Decision:** Split three axes — maturity (verified rating → hard block),
  photosensitivity (ITU-R BT.1702 → safety gate), and stimulation (computed → soft
  down-rank + a wind-down block). (`stimulation_filtering_plan.md`)
- **Guardrail:** Stimulation is a *derived measurement*, provenance-tagged — never
  asserted as a provider-verified fact; unmeasured → needs verification.
- **Result:** The demo blocks a kid-rated but hyper-paced show on *measured*
  stimulation, with the component breakdown shown. The exact question I handed to AI
  to execute — under the constraints above.

### 5. How do you prove it's better than just asking an LLM?

- **Tension:** "It's more trustworthy" is a claim, not evidence — and asking an LLM is
  the obvious baseline to beat.
- **Decision:** A pre-registered trust eval — the engine vs. an LLM-only arm, scored on
  verified-constraint satisfaction, critical factual errors (target 0), and
  reproducibility (1.0) — with explicit go/no-go kill-criteria written *before* the
  result.
- **Guardrail:** The eval PIVOTs (fails) if the engine ever asserts one false fact, or
  if the LLM matches it on both primary endpoints. I didn't give myself an escape hatch.
- **Result:** The comparison is honest and falsifiable, not a rigged demo.

### 6. When does the LLM get to touch the output at all?

- **Tension:** I wanted natural-language explanations without letting the model invent
  claims.
- **Decision:** The LLM may only *rephrase* explanations the deterministic engine
  already produced — it can't add, drop, or upgrade a claim.
- **Guardrail:** Enforced with structured outputs (a strict schema keyed to existing
  claim IDs), so faithfulness doesn't depend on the model behaving.
- **Result:** "LLM-optional" is real — turn the model off and the system still works and
  still can't lie.

### 7. A Netflix feature, or something standalone?

- **Tension:** It started as a parent-intent streaming re-ranker, so the obvious framing
  was "a feature for Netflix." But that's the weakest commercial position and buries the
  real IP.
- **Decision:** Reframe to a *trust layer for AI-driven decisions*; lead with real-world
  discovery as the proof; treat streaming as one embeddable customer, not the product.
- **Guardrail:** Keep the engine domain-agnostic (a pluggable adapter protocol) so no
  single vertical is load-bearing.
- **Result:** The README now leads with the engine thesis rather than a churn fantasy.

### 8. How do you keep an AI accelerator from over-building or drifting?

- **Tension:** AI will happily add files, abstractions, and scope you didn't ask for —
  and silently change things you depend on.
- **Decision:** Hard constraints on every AI change — isolate the agentic code from the
  ranking core, never modify the scoring formulas or hard safety gates, keep the full
  test suite green, ship features off-by-default behind flags, one branch + PR per
  change.
- **Guardrail:** A change that touched ranking behavior or weakened a test was rejected.
- **Result:** ~1,200 tests stayed green across the build; the deterministic core never
  regressed while the agentic layer grew around it.

---

### The word I rejected: "guess"

I almost described the LLM as *guessing* an unverified attribute (e.g. "is this show
over-stimulating?"). I cut it. It's imprecise and it overclaims: for well-known titles
the model's answer is often a reasonable estimate, not a coin flip. The accurate — and
sharper — point is on a different axis entirely: the estimate is **unverifiable and
unreproducible**, and stated with the same confidence whether the model is recalling a
fact or inventing one. You can't tell a good inference from a fabrication, and neither
can the model. We don't try to out-guess it; we remove the guessing by **measuring**,
and we show every input. Getting that word right *is* the brand.

---

### AI as an accelerator — honestly

What AI did: wrote most of the code, the ~1,200 tests, and first drafts of the docs;
explored options quickly; caught bugs; handled the deploy plumbing. What it did **not**
do: choose the trust boundary, the determinism contract, the faithfulness model, the
eval kill-criteria, or the product framing. Those were judgment calls. The speed came
from AI; the architecture came from the decisions above. That's the point of writing
them down.
