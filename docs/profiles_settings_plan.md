# Settings & Profiles — workflow plan

_Splitting "Adjust Preferences" (session intent) from "Settings" (account profiles),
and making profiles drive real engine policy._

## Problem

Today the parent flow has two entry points — the gear ("Parent Controls") and
"Adjust Preferences" — that effectively land on the same preferences surface.
There's no account-level view of *who* uses the app. The data model already has a
`ChildProfile` (`{id, name, age, avatar}`) and a single `selectedChild`, but no
multi-profile picker or management screen.

## The split (the core idea)

Two genuinely different surfaces, mirroring the engine's own hard-vs-soft boundary:

| Surface | Scope | Who | Maps to |
|---|---|---|---|
| **Adjust Preferences** | *Session intent* — transient, soft | Anyone | energy/mood, time, "end on a calm note" (soft signals) |
| **Settings** | *Account policy* — persistent, hard, PIN-gated | Parent | the profile roster + each profile's maturity gate and stimulation cap |

This is the product thesis one level up: **parent-set hard policy vs session-set
soft intent** — the same "hard gates vs soft re-ranking" split that's already in the
ranker.

## Data model

Extend the existing `ChildProfile` into a richer `Profile`:

```ts
interface Profile {
  id: string;
  name: string;
  kind: 'adult' | 'kid';
  ageMin: number;
  ageMax: number;        // adult: open-ended
  avatar: string;
  maturityGate: boolean; // kid → block adult-maturity content (HARD)
  stimCap: number | null; // over-stimulation ceiling (HARD); null = none
}
```

Three seeded sample profiles — the key payoff is that **age range drives the
stimulation cap we already built**:

| Profile | Age range | Maturity gate | Stim cap | Lean |
|---|---|---|---|---|
| **Parent** | 18+ | none | none | unrestricted |
| **Toddler** | 2–4 | kids (hard) | **0.3** (strict) | calm + educational |
| **Big Kid** | 5–9 | kids (hard) | **0.5** (current default) | balanced |

A toddler's profile enforces a *lower* over-stimulation ceiling than an
8-year-old's. Profiles aren't cosmetic avatars; they set policy the engine enforces.

## Workflow

1. **Profile picker** ("Who's watching?") → pick a profile → sets the active viewer +
   policy context.
2. Home re-ranks for that profile (viewer signal + maturity gate + stim cap all
   derive from it).
3. **Adjust Preferences** → tweak *this session's* intent, but it **cannot loosen**
   the profile's hard gates (a kid session can't unblock adult content or raise the
   stim cap).
4. **Settings** (PIN-gated) → see all profiles, edit age range + policy, add/remove.

## Engine tie-in

The active profile resolves to the engine's existing signals:
- `kind`/`ageMax` → `viewer` signal + `maturity_gate` (kids profiles block adult
  maturity, the gate that already exists).
- `stimCap` → the bedtime stimulation gate's cap (per-profile instead of a global
  `STIM_CAP`).
This makes the profile the single source of a viewer's policy.

## Phased build (each shippable)

1. **Profiles in context + picker + account list (Settings).** Seed the 3 profiles,
   add `activeProfileId`, a "Who's watching?" picker, and a read-only Settings screen
   listing all profiles with their age range + policy badges, PIN-gated. Splits
   Settings from Adjust Preferences. **(This PR.)**
2. **Edit** a profile's age range + policy (maturity, stim cap), PIN-gated behind the
   existing `PinGateModal`.
3. **Add/remove** profiles; persist the roster to `localStorage`.
4. **Wire profile policy → engine signals end-to-end**: age range → stim cap → the
   bedtime gate; `kind` → viewer/maturity.

## Open decision

Where the picker lives: a dedicated step/screen entered first, vs. a route. Leaning
toward a first-run "Who's watching?" step so it matches the familiar streaming mental
model, with the active profile switchable later from Settings.

## Honest notes

- The parent/home flow is a UI prototype with mock content; Phase 1 profiles are
  UI-level and wire into the mock. Phase 4 connects them to the real ranker signals.
- `selectedChild` is preserved for back-compat (the active profile maps onto it).
