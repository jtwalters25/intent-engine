

# Fix Dynamic CTA and Clarify Time Override UX

## Issues Identified

### Issue 1: Static CTA Button Text
The button always says "Start calm viewing" regardless of the actual energy level selected. When a user sets energy to "Energetic" or "High energy," the button text becomes misleading.

**Current behavior:** Static text "Start calm viewing"  
**Expected behavior:** Dynamic text that matches the selected energy mode

### Issue 2: Confusing Time Override Intent
The time selector is ambiguous. Users cannot tell if selecting "Afternoon" means:
- "Pretend it's afternoon right now" (session override)
- "Save my preferences for afternoons" (future scheduling)

The current label "Override the auto-detected time" is unclear.

---

## Solution

### Fix 1: Dynamic CTA Based on Energy Level

Create a helper function that generates appropriate CTA text based on energy level:

| Energy Level | CTA Text |
|--------------|----------|
| 0-25 (Very calm) | "Start calm viewing" |
| 26-40 (Calm) | "Start relaxed viewing" |
| 41-60 (Balanced) | "Start balanced viewing" |
| 61-80 (Energetic) | "Start active viewing" |
| 81-100 (High energy) | "Start energetic viewing" |

Also update the "Optimized for" line below the context card to dynamically reflect the current energy setting.

### Fix 2: Clarify Time Override with Better Copy

Replace the ambiguous copy with clearer language that emphasizes this is a **session override**:

**Current:**
- Header: "Time of Day"
- Subtext: "Override the auto-detected time"

**Proposed:**
- Header: "Session Mode"  
- Subtext: "Choose the viewing mode for this session"
- Add a small inline note: "This only affects tonight's recommendations"

Additionally, show a subtle "(auto-detected)" indicator next to the time in the summary card when it matches the system time, and "(overridden)" when manually changed.

---

## Technical Changes

### File: `src/components/screens/IntentSetupScreen.tsx`

1. **Add CTA helper function:**
```typescript
const getCtaText = (level: number): string => {
  if (level <= 25) return 'Start calm viewing';
  if (level <= 40) return 'Start relaxed viewing';
  if (level <= 60) return 'Start balanced viewing';
  if (level <= 80) return 'Start active viewing';
  return 'Start energetic viewing';
};
```

2. **Add dynamic "Optimized for" helper:**
```typescript
const getOptimizedForText = (level: number, time: TimeOfDay): string => {
  if (level <= 40) {
    return 'Optimized for winding down - Designed to support healthy routines';
  }
  if (level <= 60) {
    return 'Optimized for balanced engagement - A mix of calm and active content';
  }
  return 'Optimized for active play - Energetic content for playtime';
};
```

3. **Track auto-detected vs manual override:**
```typescript
const [isTimeOverridden, setIsTimeOverridden] = useState(false);
const autoDetectedTime = getAutoTimeOfDay();

// Update time override handler
onClick={() => {
  setTimeOfDay(time);
  setEnergyLevel(getDefaultEnergyLevel(time));
  setIsTimeOverridden(time !== autoDetectedTime);
}}
```

4. **Update UI elements:**
   - CTA button uses `getCtaText(state.energyLevel)`
   - Summary card shows "(auto)" or "(session override)" badge
   - Time override section renamed to "Session Mode" with clarifying copy
   - "Optimized for" text updates dynamically

---

## Visual Preview of Changes

**Summary Card - Time indicator:**
```
Time: Evening (auto)
```
or after override:
```
Time: Morning (session)
```

**Time Override Section:**
```
Session Mode
Choose the viewing mode for this session

[Morning] [Afternoon] [Evening] [Bedtime]

This only affects tonight's recommendations
```

**Dynamic CTA examples:**
- Energy 20% -> "Start calm viewing"
- Energy 70% -> "Start active viewing"
- Energy 90% -> "Start energetic viewing"

