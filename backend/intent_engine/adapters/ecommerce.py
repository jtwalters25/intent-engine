"""E-commerce domain adapter (Amazon-style product ranking)."""

from typing import Any, Dict

from intent_engine.schemas import Domain, Item, MultiplierSet, EcommerceIntent


# Keyword → intent mapping
_KEYWORD_MAP: Dict[str, EcommerceIntent] = {
    "gift": EcommerceIntent.GIFT,
    "present": EcommerceIntent.GIFT,
    "shower": EcommerceIntent.GIFT,
    "holiday": EcommerceIntent.GIFT,
    "birthday": EcommerceIntent.GIFT,
    "budget": EcommerceIntent.BUDGET,
    "cheap": EcommerceIntent.BUDGET,
    "affordable": EcommerceIntent.BUDGET,
    "deal": EcommerceIntent.BUDGET,
    "save": EcommerceIntent.BUDGET,
    "premium": EcommerceIntent.PREMIUM,
    "luxury": EcommerceIntent.PREMIUM,
    "best": EcommerceIntent.PREMIUM,
    "high-end": EcommerceIntent.PREMIUM,
    "pro": EcommerceIntent.PREMIUM,
    "practical": EcommerceIntent.PRACTICAL,
    "everyday": EcommerceIntent.PRACTICAL,
    "essential": EcommerceIntent.PRACTICAL,
    "useful": EcommerceIntent.PRACTICAL,
    "new": EcommerceIntent.DISCOVERY,
    "discover": EcommerceIntent.DISCOVERY,
    "explore": EcommerceIntent.DISCOVERY,
    "trending": EcommerceIntent.DISCOVERY,
}


class EcommerceAdapter:
    """Domain adapter for e-commerce (Amazon-style product listings)."""

    @property
    def domain(self) -> Domain:
        return Domain.ECOMMERCE

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve raw intent signals into canonical e-commerce intent."""
        intent_type = EcommerceIntent.UNKNOWN
        price_sensitivity = float(raw_input.get("price_sensitivity", 0.5))
        quality_priority = float(raw_input.get("quality_priority", 0.5))

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

        # Infer from signals when still unknown
        if intent_type == EcommerceIntent.UNKNOWN:
            if price_sensitivity > 0.7:
                intent_type = EcommerceIntent.BUDGET
            elif quality_priority > 0.7:
                intent_type = EcommerceIntent.PREMIUM

        return {
            "intent_type": intent_type.value,
            "price_sensitivity": price_sensitivity,
            "quality_priority": quality_priority,
            "shopper_profile": raw_input.get("shopper_profile", "adult"),
        }

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        """Compute multipliers based on e-commerce-specific signals."""
        attrs = item.attributes
        maturity = attrs.get("maturity", "family")
        price_tier = int(attrs.get("price_tier", 2))
        quality_score = float(attrs.get("quality_score", 0.5))
        gift_score = float(attrs.get("gift_score", 0.5))
        popularity = float(attrs.get("popularity", quality_score))

        intent_type = intent.get("intent_type", "unknown")
        price_sensitivity = float(intent.get("price_sensitivity", 0.5))
        quality_priority = float(intent.get("quality_priority", 0.5))
        shopper_profile = intent.get("shopper_profile", "adult")

        # Context multiplier: occasion / gift-suitability alignment
        context = 1.0
        if intent_type == "gift":
            context = 0.8 + 0.4 * gift_score

        # Profile multiplier: audience gating (buying for kids)
        profile = 1.0
        if shopper_profile == "kids":
            if maturity == "adult":
                profile = 0.0  # hard gate via multiplier
            elif maturity == "teen":
                profile = 0.4
            elif maturity == "kids":
                profile = 1.2

        # Urgency multiplier: quality vs. practicality alignment
        urgency = 1.0
        if intent_type == "premium":
            urgency = 0.6 + 0.8 * quality_score
        elif intent_type == "practical":
            urgency = 0.8 + 0.4 * (1.0 - float(price_tier - 1) / 3.0)
        if quality_priority > 0.7:
            urgency *= (0.7 + 0.6 * quality_score)

        # Cost multiplier: price sensitivity penalizes expensive tiers
        cost = 1.0
        effective_sensitivity = price_sensitivity
        if intent_type == "budget":
            effective_sensitivity = max(price_sensitivity, 0.8)
        if effective_sensitivity > 0.5:
            cost = max(0.4, 1.3 - (price_tier - 1) * 0.2 * effective_sensitivity)

        # Prophecy: occasion boost / discovery novelty
        prophecy = 1.0
        if intent_type == "gift":
            prophecy = 1.0 + 0.3 * gift_score
        elif intent_type == "discovery":
            prophecy = max(0.6, 1.2 - popularity)

        return MultiplierSet(
            context=round(context, 3),
            profile=round(profile, 3),
            urgency=round(urgency, 3),
            cost=round(cost, 3),
            prophecy=round(prophecy, 3),
        )

    def apply_hard_constraints(
        self, item: Item, constraints: Dict[str, Any]
    ) -> bool:
        """Block adult-only products when a kids audience gate is set."""
        maturity_gate = constraints.get("maturity_gate")
        if maturity_gate == "kids":
            if item.attributes.get("maturity", "family") == "adult":
                return True
        return False

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        """Generate human-readable explanation."""
        if multipliers.profile == 0.0:
            return f"'{item.title}' blocked: adult product not suitable for a kids audience"
        parts = []
        if multipliers.context > 1.1:
            parts.append("strong gift fit")
        if multipliers.urgency > 1.1:
            parts.append("high quality match")
        elif multipliers.urgency < 0.8:
            parts.append("below quality preference")
        if multipliers.cost < 0.8:
            parts.append("above price preference")
        if multipliers.prophecy > 1.1:
            parts.append("occasion-boosted")
        elif multipliers.prophecy < 0.8:
            parts.append("new discovery option")
        if multipliers.profile > 1.0:
            parts.append("age-appropriate boost")

        if not parts:
            return f"'{item.title}' ranked by base score"
        return f"'{item.title}': {', '.join(parts)}"

    def diversity_key(self, item: Item) -> str:
        """Group by product category for diversity."""
        return item.attributes.get("category_type", item.category or "other")
