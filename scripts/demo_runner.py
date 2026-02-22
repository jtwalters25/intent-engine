"""Demo runner: 3 scenarios through the full Intent Engine pipeline.

Loads a synthetic children's content catalog and runs:
  1. Bedtime Calm   — evening wind-down content
  2. Afterschool STEM — educational science/math after school
  3. Weekend Fun    — energetic family adventure on a Saturday

Each scenario shows:
  - Translated intent (keywords, preferences, priority)
  - Ranked results with 2-3 human-readable explanations per item
  - How non-matching items are demoted but NOT filtered (soft constraint)
"""

from intent_engine.schemas import Intent, UserContext, CandidateItem
from intent_engine.rules_translator import IntentTranslator
from intent_engine.simple_ranker import IntentRanker


# ---------------------------------------------------------------------------
# Synthetic catalog — 12 children's content items
# ---------------------------------------------------------------------------

CATALOG = [
    CandidateItem(
        item_id="c01",
        title="Goodnight Moon Lullaby",
        attributes={
            "category": "stories", "mood": "calm", "energy": "low",
            "tags": ["sleep", "lullaby", "gentle", "bedtime"],
            "age_range": "3-6",
        },
        base_score=0.80,
    ),
    CandidateItem(
        item_id="c02",
        title="Calm Ocean Sounds for Kids",
        attributes={
            "category": "music", "mood": "calm", "energy": "low",
            "tags": ["relaxing", "soothing", "quiet", "nature", "ocean"],
            "age_range": "2-8",
        },
        base_score=0.72,
    ),
    CandidateItem(
        item_id="c03",
        title="Rocket Science Experiments",
        attributes={
            "category": "stem", "mood": "energetic", "energy": "high",
            "tags": ["science", "experiment", "space", "rocket", "coding"],
            "age_range": "6-10",
        },
        base_score=0.85,
    ),
    CandidateItem(
        item_id="c04",
        title="Math Puzzle Challenge",
        attributes={
            "category": "stem", "mood": "fun", "energy": "medium",
            "tags": ["math", "puzzle", "logic", "numbers", "educational"],
            "age_range": "5-9",
        },
        base_score=0.78,
    ),
    CandidateItem(
        item_id="c05",
        title="Dinosaur Adventure Quest",
        attributes={
            "category": "stories", "mood": "energetic", "energy": "high",
            "tags": ["adventure", "dinosaur", "exciting", "outdoor"],
            "age_range": "4-8",
        },
        base_score=0.88,
    ),
    CandidateItem(
        item_id="c06",
        title="Silly Dance Party",
        attributes={
            "category": "music", "mood": "fun", "energy": "high",
            "tags": ["games", "funny", "playful", "dance", "active"],
            "age_range": "3-7",
        },
        base_score=0.75,
    ),
    CandidateItem(
        item_id="c07",
        title="Build a Robot Workshop",
        attributes={
            "category": "stem", "mood": "creative", "energy": "medium",
            "tags": ["robot", "engineering", "building", "technology", "coding"],
            "age_range": "7-12",
        },
        base_score=0.82,
    ),
    CandidateItem(
        item_id="c08",
        title="Stargazing Night Guide",
        attributes={
            "category": "nature", "mood": "calm", "energy": "low",
            "tags": ["nature", "space", "quiet", "gentle", "stars"],
            "age_range": "5-10",
        },
        base_score=0.70,
    ),
    CandidateItem(
        item_id="c09",
        title="Family Treasure Hunt",
        attributes={
            "category": "games", "mood": "fun", "energy": "high",
            "tags": ["adventure", "family", "outdoor", "games", "exciting"],
            "age_range": "4-10",
        },
        base_score=0.83,
    ),
    CandidateItem(
        item_id="c10",
        title="Painting with Watercolors",
        attributes={
            "category": "art", "mood": "creative", "energy": "low",
            "tags": ["art", "drawing", "painting", "craft", "quiet"],
            "age_range": "4-9",
        },
        base_score=0.68,
    ),
    CandidateItem(
        item_id="c11",
        title="Coding for Kids: First Steps",
        attributes={
            "category": "stem", "mood": "educational", "energy": "medium",
            "tags": ["coding", "technology", "educational", "interactive", "logic"],
            "age_range": "6-11",
        },
        base_score=0.76,
    ),
    CandidateItem(
        item_id="c12",
        title="Pirate Ship Sing-Along",
        attributes={
            "category": "music", "mood": "fun", "energy": "high",
            "tags": ["songs", "adventure", "playful", "funny", "pirate"],
            "age_range": "3-7",
        },
        base_score=0.71,
    ),
]


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "Bedtime Calm",
        "description": "A parent looking for calm, wind-down content at 8 PM.",
        "text": "bedtime calm",
        "hour": 20,
        "day_of_week": "tuesday",
        "user_id": "parent_001",
    },
    {
        "name": "Afterschool STEM",
        "description": "A kid home from school at 4 PM wanting science activities.",
        "text": "afterschool stem educational",
        "hour": 16,
        "day_of_week": "wednesday",
        "user_id": "kid_002",
    },
    {
        "name": "Weekend Fun",
        "description": "Saturday morning family looking for energetic, fun content.",
        "text": "fun energetic weekend",
        "hour": 10,
        "day_of_week": "saturday",
        "user_id": "family_003",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def divider(char: str = "=", width: int = 78) -> None:
    print(char * width)


def run_scenario(scenario: dict, translator: IntentTranslator, ranker: IntentRanker) -> None:
    """Run a single scenario through the full pipeline."""
    divider()
    print(f"  SCENARIO: {scenario['name']}")
    print(f"  {scenario['description']}")
    divider()

    # --- Step 1: Translate intent ---
    intent = translator.translate(
        scenario["text"],
        hour=scenario.get("hour"),
        day_of_week=scenario.get("day_of_week"),
    )

    print(f"\n  Translated Intent:")
    print(f"    type       = {intent.intent_type}")
    print(f"    keywords   = {intent.keywords}")
    print(f"    preferences= {intent.preferences}")
    print(f"    priority   = {intent.priority:.2f}")

    # --- Step 2: Build UserContext ---
    context = UserContext(
        user_id=scenario["user_id"],
        intent=intent,
    )

    # --- Step 3: Rank ---
    ranked = ranker.rank(list(CATALOG), context)

    # --- Step 4: Display results ---
    print(f"\n  Ranked Results ({len(ranked)} items — all items present, soft constraint):\n")
    for i, r in enumerate(ranked, 1):
        marker = ">>" if i <= 3 else "  "
        print(f"  {marker} {i:>2}. {r.item.title}")
        print(f"       final={r.final_score:.3f}  intent={r.intent_score:.3f}  base={r.item.base_score:.2f}")
        # Show structured explanations for top 5
        if i <= 5:
            for line in r.explanations:
                print(f"         - {line}")
        print()

    # Soft-constraint proof: count items in output vs catalog
    print(f"  Items in catalog: {len(CATALOG)}  |  Items in output: {len(ranked)}")
    print(f"  (All items present — intent is a soft re-ranking signal, not a filter)\n")


def main() -> None:
    print()
    print("  Intent Engine — Demo Runner")
    print("  Pipeline: IntentTranslator -> IntentRanker -> Explanations")
    print()

    translator = IntentTranslator()
    # 60% intent weight, 40% base score — intent matters but doesn't dominate
    ranker = IntentRanker(intent_weight=0.6)

    for scenario in SCENARIOS:
        run_scenario(scenario, translator, ranker)

    divider()
    print("  Done. All 3 scenarios completed.")
    divider()


if __name__ == "__main__":
    main()
