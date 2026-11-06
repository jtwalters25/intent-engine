# Demo redesign plan: film-style `/demo`

Reference: `docs/design/bedtime-film.html` (concept animation).

## Goal
A visitor understands the product in about 10 seconds: pick a moment, watch the titles re-rank, see why. Detail (formula, sliders) stays one click away.

## Scope
- Presentation only. `rankWithSignals` and all scoring data in `src/data/demoPlatforms.ts` are untouched.
- Signal Mode of `/demo` is redesigned. Agentic Mode, the activity finder, the homepage, and the backend are unchanged.
- No new dependencies. Motion is CSS transitions plus a small FLIP hook.

## Structure
1. **Header**: wordmark, Signal/Agentic mode, Calm toggle (kept).
2. **Platform pills**: the five verticals.
3. **Moment hero**: big time (from the context subtitle), context label, one-line description, signal chips.
4. **Moment picker**: one pill per context.
5. **Order toggle**: `For this moment` (default) / `Engagement`. The same tiles animate between the engine order and the catalog's engagement order. Replaces the two columns.
6. **Poster grid**: large tiles with rank, title, rating/runtime, "was #N" marker, held-back state (grayscale, shrink, reason pill).
7. **Focus panel**: the selected tile (default #1). Plain reason from the item's own tags, its strongest multipliers, and stimulation meters when the item has stimulation data (red when over the cap, labeled "estimated").
8. **Why this order?**: expands inline to the existing `SignalSliders` and `ScoringFormula` components.

## Steps
1. Tokens and fonts (Geist, Geist Mono) scoped to the demo; Calm mode keeps working through the existing CSS variables.
2. Poster grid with spring reorder (FLIP).
3. Held-back state.
4. Focus panel with meters and reason.
5. Why panel with existing formula and sliders.
6. Engagement / moment toggle.
7. Mobile and reduced-motion pass.
8. Tests: on-screen order equals `rankWithSignals` for every platform and context, and equals catalog order in Engagement view.

## Success criteria
- Frontend tests pass with the same or more tests; no new TypeScript errors (one pre-existing error in `CuratedHomeScreen.tsx`).
- On-screen order matches the engine for every platform and context.
- Screenshots at 1440x900 and 390x844 show no clipped or overlapping text.
- Reduced motion: reorder is instant, nothing hidden.
- Every number on screen comes from demo data. No em dashes in new copy.

## Decisions I made
- **Toggle instead of two columns**, with a "was #N" marker on each tile so the before/after contrast survives.
- **Why panel is inline and collapsible**, not a modal drawer: simpler, keeps it visible for technical visitors, no focus trap needed.
- **Poster colors are derived from each item's existing thumbnail gradient** (brightened), so every vertical gets tiles without new data fields.
- **Reason headline uses the item's own tags** ("Soothing. Short. Familiar.") and the subline names its two strongest multipliers, so the copy is traceable to data rather than written per title.
- **The big time and description come from splitting the existing context subtitle**, so no data copy changed. Contexts without a time show the label only.
- **Selecting a tile dims the others** (the film's focus moment); selecting it again or pressing Escape clears it.
