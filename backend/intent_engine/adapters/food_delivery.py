"""Food delivery domain adapter (Uber Eats-style restaurant/dish ranking)."""

from typing import Any, Dict

from intent_engine.schemas import Domain, Item, MultiplierSet, FoodIntent


_KEYWORD_MAP: Dict[str, FoodIntent] = {
    "comfort": FoodIntent.COMFORT,
    "cozy": FoodIntent.COMFORT,
    "warm": FoodIntent.COMFORT,
    "soul food": FoodIntent.COMFORT,
    "indulgent": FoodIntent.COMFORT,
    "healthy": FoodIntent.HEALTHY,
    "salad": FoodIntent.HEALTHY,
    "light": FoodIntent.HEALTHY,
    "clean": FoodIntent.HEALTHY,
    "low cal": FoodIntent.HEALTHY,
    "fast": FoodIntent.FAST,
    "quick": FoodIntent.FAST,
    "hungry": FoodIntent.FAST,
    "starving": FoodIntent.FAST,
    "asap": FoodIntent.FAST,
    "new": FoodIntent.DISCOVERY,
    "discover": FoodIntent.DISCOVERY,
    "try": FoodIntent.DISCOVERY,
    "surprise": FoodIntent.DISCOVERY,
    "explore": FoodIntent.DISCOVERY,
    "usual": FoodIntent.HABITUAL,
    "regular": FoodIntent.HABITUAL,
    "again": FoodIntent.HABITUAL,
    "reorder": FoodIntent.HABITUAL,
}


class FoodDeliveryAdapter:
    """Domain adapter for food delivery (Uber Eats-style)."""

    @property
    def domain(self) -> Domain:
        return Domain.FOOD_DELIVERY

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        intent_type = FoodIntent.UNKNOWN
        hunger_urgency = float(raw_input.get("hunger_urgency", 0.5))
        price_sensitivity = float(raw_input.get("price_sensitivity", 0.5))
        health_priority = float(raw_input.get("health_priority", 0.5))
        time_bucket = raw_input.get("time_bucket", "evening")

        # Check keywords
        keywords = raw_input.get("keywords", [])
        intent_text = raw_input.get("intent_text", "")
        search_text = " ".join(keywords).lower()
        if intent_text:
            search_text += " " + intent_text.lower()

        for keyword, mapped_intent in _KEYWORD_MAP.items():
            if keyword in search_text:
                intent_type = mapped_intent
                break

        # Infer from signals
        if intent_type == FoodIntent.UNKNOWN:
            if hunger_urgency > 0.8:
                intent_type = FoodIntent.FAST
            elif health_priority > 0.7:
                intent_type = FoodIntent.HEALTHY
            elif time_bucket == "late_night":
                intent_type = FoodIntent.COMFORT

        return {
            "intent_type": intent_type.value,
            "hunger_urgency": hunger_urgency,
            "price_sensitivity": price_sensitivity,
            "health_priority": health_priority,
            "time_bucket": time_bucket,
            "comfort_preference": float(raw_input.get("comfort_preference", 0.5)),
        }

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        attrs = item.attributes
        prep_time = float(attrs.get("prep_time_minutes", 20))
        health_score = float(attrs.get("health_score", 0.5))
        price_tier = int(attrs.get("price_tier", 2))
        reorder_rate = float(attrs.get("reorder_rate", 0.3))

        intent_type = intent.get("intent_type", "unknown")
        hunger_urgency = float(intent.get("hunger_urgency", 0.5))
        price_sensitivity = float(intent.get("price_sensitivity", 0.5))
        health_priority = float(intent.get("health_priority", 0.5))
        comfort_pref = float(intent.get("comfort_preference", 0.5))

        # Context: meal time alignment
        context = 1.0
        time_bucket = intent.get("time_bucket", "evening")
        if time_bucket == "late_night":
            # Late night → comfort food (inverse health)
            context = 0.7 + 0.6 * (1.0 - health_score)
        elif time_bucket in ("morning", "early_morning"):
            # Morning → lighter/healthier
            context = 0.7 + 0.6 * health_score

        # Profile: dietary/health alignment
        profile = 1.0
        if intent_type == "healthy":
            profile = 0.5 + health_score  # strongly favor healthy
        elif intent_type == "comfort":
            profile = 0.5 + (1.0 - health_score) * 0.8  # favor comfort (inverse health)

        # Urgency: hunger → fast prep time
        urgency_mult = 1.0
        if intent_type == "fast" or hunger_urgency > 0.7:
            # Low prep time → high multiplier: 10min=1.3, 40min=0.6
            urgency_mult = max(0.4, 1.5 - prep_time / 30)

        # Cost: price sensitivity
        cost = 1.0
        if price_sensitivity > 0.5:
            # Penalize expensive tiers proportionally
            cost = max(0.4, 1.3 - (price_tier - 1) * 0.2 * price_sensitivity)

        # Prophecy: habitual reorder boost
        prophecy = 1.0
        if intent_type == "habitual":
            prophecy = 1.0 + 0.5 * reorder_rate
        elif intent_type == "discovery":
            # Penalize high reorder (familiar) items for discovery
            prophecy = max(0.6, 1.2 - reorder_rate)

        return MultiplierSet(
            context=round(context, 3),
            profile=round(profile, 3),
            urgency=round(urgency_mult, 3),
            cost=round(cost, 3),
            prophecy=round(prophecy, 3),
        )

    def apply_hard_constraints(
        self, item: Item, constraints: Dict[str, Any]
    ) -> bool:
        """Block items containing flagged allergens."""
        allergens = constraints.get("allergens")
        if allergens:
            item_allergens = item.attributes.get("allergens", [])
            if isinstance(allergens, list) and isinstance(item_allergens, list):
                for allergen in allergens:
                    if allergen.lower() in [a.lower() for a in item_allergens]:
                        return True
        return False

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        parts = []
        if multipliers.urgency > 1.1:
            parts.append("quick prep time")
        elif multipliers.urgency < 0.8:
            parts.append("longer wait")
        if multipliers.profile > 1.1:
            parts.append("matches dietary preference")
        if multipliers.cost < 0.8:
            parts.append("above price preference")
        if multipliers.prophecy > 1.1:
            parts.append("frequently reordered")
        elif multipliers.prophecy < 0.8:
            parts.append("new discovery option")
        if multipliers.context > 1.1:
            parts.append("good meal-time fit")

        if not parts:
            return f"'{item.title}' ranked by base score"
        return f"'{item.title}': {', '.join(parts)}"

    def diversity_key(self, item: Item) -> str:
        return item.attributes.get("cuisine_type", item.category or "other")
