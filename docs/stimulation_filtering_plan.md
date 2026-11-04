# Filtering over-stimulation — design & plan

_How Intent Engine detects, measures, and blocks/down-ranks over-stimulating
content — the attribute parents care about most and the one no provider verifies._

## Why this matters

Age ratings answer "is this appropriate?" They do **not** answer "is this
over-stimulating?" A `TV-Y` show can be hyper-paced (rapid cuts, loud, saturated,
high-motion); a `PG` film can be calm. Over-stimulation is:

- **Consequential** — Lillard & Peterson (2011, *Pediatrics*) found 9 minutes of a
  fast-paced cartoon (SpongeBob, ~5.5 scene cuts/min) measurably impaired
  4-year-olds' executive function vs. a slow-paced show (Caillou, ~1.8 cuts/min)
  or drawing.
- **Unverified** — it appears in **zero** provider "verified" fields. Ask an LLM "is
  this calming?" and you get an *estimate* — sometimes reasonable, but ungrounded,
  unreproducible, and stated with the same confidence whether the model is recalling
  a fact or inventing one. We **measure** it from the video and show every input.
  That's the moat, and the clearest demonstration of the "trust, not taste" thesis.

## Three distinct axes (do not conflate)

| Axis | What it is | Evidence basis | Enforcement |
|---|---|---|---|
| **Maturity** | Age-inappropriate (adult) | Ratings — structured, VERIFIED | Hard block (shipped) |
| **Photosensitivity / flash** | Seizure-risk flashing | Standardized + measurable: ITU-R BT.1702 (≤3 flashes/s, ≥20 cd/m²); Harding FPA | Hard **safety** gate |
| **Stimulation / pacing** | Over-arousal: fast cuts, loud, high motion, saturated color | **Not published — must be computed** | Soft down-rank; hard block in low-stim / wind-down mode |

## What data exists

- **Ratings:** structured, licensable. Common Sense Media has a partner Reviews API
  (per-title content grid: violence, scariness, recommended age) — adjacent proxies,
  not a stimulation score, and partner-gated.
- **Flash rate:** a real, standardized **safety** metric (ITU-R BT.1702 / Harding),
  measurable per title but not open data; compute it or buy QC results.
- **Stimulation/pacing:** **no published per-title dataset.** Computable, and the
  operationalization is research-backed (the SpongeBob-vs-Caillou cuts/min anchor).

So: **ratings you license; flash and stimulation you compute.**

## The Stimulation Index (how we measure it)

A transparent weighted composite — same ethos as the existing multiplier formula —
each component measurable with open tooling and **provenance-tagged** (MEASURED /
ESTIMATED / UNKNOWN), never asserted as a provider-verified fact.

| Component | Signal | Measured by |
|---|---|---|
| **Pacing** (primary) | cuts/min, avg shot length | PySceneDetect (`ContentDetector`) |
| **Loudness/dynamics** | integrated LUFS + range | ffmpeg `ebur128` (ITU-R BS.1770 / EBU R128) |
| **Motion** | mean optical-flow magnitude | OpenCV optical flow |
| **Color intensity** | HSV saturation mean/variance | per-frame stats |
| **Flash events** | flashes/s vs ITU-R BT.1702 | Harding-style detector (doubles as the safety gate) |

Composite (published weights, sum 1.0): `stim = 0.4·pacing + 0.2·loudness +
0.2·motion + 0.1·color + 0.1·flash`, each component normalized 0–1 against a
published reference scale. Deterministic → same clip, same index + fingerprint.
Unmeasured → UNKNOWN → "needs verification," exactly like Discover.

## How the demo shows it (implemented — step 1)

Prototype shipped in the `/demo` streaming vertical (client-side, fixture data):

- A `StimulationProfile` on every streaming item (cuts/min, LUFS, motion,
  saturation, flashes/s + provenance), plus a new kid-rated but hyper-paced show
  ("Sensory Rush Rhymes", 22 cuts/min) — the whole point: it passes the maturity
  gate but is **over-stimulating**. In this prototype these values are hand-set
  anchors tagged `ESTIMATED`, not measured from clips; the production pipeline
  below produces `MEASURED` values.
- A **wind-down stim gate**: when energy intent is low (bedtime), items with a
  Stimulation Index above the cap (0.5) are **hard-blocked** — mirroring the
  maturity gate. At bedtime, Dark S3 blocks on *maturity*; Sensory Rush Rhymes
  blocks on *stimulation*; calm picks (Bluey, Planet Earth) rise.
- A per-item **⚡ stim badge** (red above cap) and a **measurement breakdown** in
  the scoring panel: the composite, every component value, its provenance, the cap,
  and a flash ⚠ when flashes/s exceed the ITU-R limit.

Files: `frontend/src/data/demoPlatforms.ts` (`StimulationProfile`,
`computeStimIndex`, `STIM_CAP`, gate in `rankWithSignals`),
`components/demo/ContentCard.tsx`, `components/demo/ScoringFormula.tsx`.

## How we prove it (rigor)

- **Reproduce known ordering:** the index ranks well-known shows the way the
  research/parents expect (SpongeBob/Cocomelon high; Mister Rogers/Bluey low).
- **Validate against an external label:** correlate the composite with CSM
  recommended-age/intensity (licensed) or a small human-labeled "feels
  over-stimulating" set → report correlation/AUC. Same pre-registered discipline as
  the Discover trust scoreboard.
- **Determinism:** same clip → same index + fingerprint, auditable.
- **Honesty:** present as a derived estimate with components shown; unmeasured →
  "needs verification."

## Data/rights reality

You can't mass-measure copyrighted catalogs without the content. Demo: measure
trailers/clips or ship precomputed fixtures (done). Product: partner with a platform
(they have the content) or license adjacent structured data (CSM). Flash-safety
scoring is independently valuable and defensible as its own feature.

## Roadmap

1. **Demo prototype (done)** — Stimulation Index + wind-down stim-gate + measurement
   panel on fixtures.
2. **Real measurement module (backend):** `stimulation.py` computing the components
   from a video (PySceneDetect + ffmpeg ebur128 + optical flow + flash detector) →
   index + components + provenance + fingerprint; unit-tested on short clips.
3. **Wire as an engine signal:** a hard `stim_gate` constraint (bedtime) alongside
   `maturity_gate`, plus the soft stim multiplier; honest provenance throughout.
4. **Validation harness:** correlate index vs CSM/human labels; reproduce known
   ordering; pre-register thresholds.
5. **Productize:** CSM licensing + platform partnership for content access.

## Honest limitations

- The construct is partly subjective; we define it operationally and validate against
  a label.
- Flash ≠ stimulation (it's one safety component).
- No open per-title dataset; rights constrain measuring at scale.
- The index is a derived estimate, provenance-tagged — never a provider-verified fact.

## Sources

- Lillard & Peterson 2011, *Pediatrics* — fast-paced TV and executive function.
- ITU-R BT.1702 (2023); Harding Flash & Pattern Analyser — photosensitivity.
- Common Sense Media Reviews API (partner program) — structured per-title ratings.
- PySceneDetect — shot/scene detection; EBU R128 / ITU-R BS.1770 — loudness.
