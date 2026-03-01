"""Ride matching domain adapter (Uber-style ride ranking)."""

from typing import Any, Dict

from intent_engine.schemas import Domain, Item, MultiplierSet, RideIntent


_KEYWORD_MAP: Dict[str, RideIntent] = {
    "cheap": RideIntent.BUDGET,
    "affordable": RideIntent.BUDGET,
    "budget": RideIntent.BUDGET,
    "pool": RideIntent.BUDGET,
    "shared": RideIntent.BUDGET,
    "comfort": RideIntent.COMFORT,
    "comfortable": RideIntent.COMFORT,
    "premium": RideIntent.PREMIUM,
    "luxury": RideIntent.PREMIUM,
    "black": RideIntent.PREMIUM,
    "suv": RideIntent.PREMIUM,
    "fast": RideIntent.URGENT,
    "urgent": RideIntent.URGENT,
    "hurry": RideIntent.URGENT,
    "asap": RideIntent.URGENT,
    "now": RideIntent.URGENT,
    "usual": RideIntent.HABITUAL,
    "commute": RideIntent.HABITUAL,
    "regular": RideIntent.HABITUAL,
}


def _resolve_time_bucket(hour: int) -> str:
    if 5 <= hour < 9:
        return "morning_commute"
    elif 9 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 20:
        return "evening_commute"
    elif 20 <= hour < 23:
        return "evening"
    else:
        return "late_night"


class RideMatchingAdapter:
    """Domain adapter for ride matching (Uber-style)."""

    @property
    def domain(self) -> Domain:
        return Domain.RIDE_MATCHING

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        intent_type = RideIntent.COMFORT  # safe default
        urgency = float(raw_input.get("urgency", 0.5))
        surge_sensitivity = float(raw_input.get("surge_sensitivity", 0.5))
        time_bucket = raw_input.get("time_bucket", "afternoon")

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

        # Infer from time
        if intent_type == RideIntent.COMFORT:
            if time_bucket in ("morning_commute", "evening_commute"):
                intent_type = RideIntent.HABITUAL

        # High urgency override
        if urgency > 0.8 and intent_type not in (RideIntent.PREMIUM, RideIntent.BUDGET):
            intent_type = RideIntent.URGENT

        return {
            "intent_type": intent_type.value,
            "urgency": urgency,
            "surge_sensitivity": surge_sensitivity,
            "time_bucket": time_bucket,
            "comfort_preference": float(raw_input.get("comfort_preference", 0.5)),
        }

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        attrs = item.attributes
        comfort_score = float(attrs.get("comfort_score", 0.5))
        eta_minutes = float(attrs.get("eta_minutes", 10))
        price_multiplier = float(attrs.get("price_multiplier", 1.0))

        intent_type = intent.get("intent_type", "comfort")
        urgency = float(intent.get("urgency", 0.5))
        surge_sensitivity = float(intent.get("surge_sensitivity", 0.5))
        comfort_pref = float(intent.get("comfort_preference", 0.5))

        # Context: commute times favor low ETA
        context = 1.0
        time_bucket = intent.get("time_bucket", "afternoon")
        if time_bucket in ("morning_commute", "evening_commute"):
            # Lower ETA → higher multiplier (normalize: 3min=1.3, 15min=0.7)
            context = max(0.5, 1.5 - eta_minutes / 20)

        # Profile: comfort/budget tier preference
        profile = 1.0
        if intent_type == "budget":
            # Favor low price, penalize premium
            profile = max(0.3, 1.4 - price_multiplier * 0.4)
        elif intent_type == "premium":
            # Favor high comfort
            profile = 0.6 + 0.8 * comfort_score
        elif intent_type == "comfort":
            profile = 0.8 + 0.4 * comfort_score

        # Urgency: fastest ETA wins
        urgency_mult = 1.0
        if intent_type == "urgent" or urgency > 0.7:
            # Strong ETA preference: 3min=1.4, 15min=0.6
            urgency_mult = max(0.4, 1.6 - eta_minutes / 15)
        elif intent_type == "habitual":
            # Mild ETA preference
            urgency_mult = max(0.7, 1.2 - eta_minutes / 30)

        # Cost: surge sensitivity
        cost = 1.0
        if surge_sensitivity > 0.5:
            # High sensitivity → penalize surging rides
            cost = max(0.3, 1.3 - price_multiplier * surge_sensitivity * 0.5)

        # Prophecy: habitual pattern boost
        prophecy = 1.0
        if intent_type == "habitual":
            prophecy = 1.2

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
        """Block rides above surge cap."""
        surge_cap = constraints.get("surge_cap")
        if surge_cap is not None:
            price_mult = float(item.attributes.get("price_multiplier", 1.0))
            if price_mult > float(surge_cap):
                return True
        return False

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        parts = []
        if multipliers.profile == 0.0:
            return f"'{item.title}' blocked by constraint"
        if multipliers.context > 1.1:
            parts.append("fast ETA for commute")
        if multipliers.urgency > 1.1:
            parts.append("quick pickup")
        elif multipliers.urgency < 0.8:
            parts.append("slower ETA")
        if multipliers.cost < 0.8:
            parts.append("surge-penalized")
        if multipliers.profile > 1.1:
            parts.append("matches ride preference")
        if multipliers.prophecy > 1.0:
            parts.append("matches commute pattern")

        if not parts:
            return f"'{item.title}' ranked by base score"
        return f"'{item.title}': {', '.join(parts)}"

    def diversity_key(self, item: Item) -> str:
        return item.attributes.get("ride_type", item.category or "standard")
