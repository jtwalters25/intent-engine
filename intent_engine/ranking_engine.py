"""Deterministic ranking engine with soft intent constraints and diversity."""

from typing import List, Dict, Any
import time
from .schemas import (
    Item, RankedItem, UserContext, Intent, IntentType,
    LatencyBreakdown, RankingRequest, RankingResponse
)
from .intent_parser import IntentParser


class RankingEngine:
    """Deterministic ranking engine with diversity guardrails."""
    
    # Scoring weights and thresholds
    BUDGET_PRICE_THRESHOLD_LOW = 100.0
    BUDGET_PRICE_THRESHOLD_MID = 200.0
    
    def __init__(self):
        self.intent_parser = IntentParser()
        
    def rank(self, request: RankingRequest) -> RankingResponse:
        """
        Rank items based on user context and intent.
        
        Args:
            request: RankingRequest with items, context, and optional intent
            
        Returns:
            RankingResponse with ranked items, explanations, and latency
        """
        start_time = time.time()
        
        # Step 1: Parse intent
        intent_start = time.time()
        intent = self.intent_parser.parse(request.intent_text, request.use_llm)
        intent_time = (time.time() - intent_start) * 1000
        
        # Step 2: Calculate scores for each item
        ranking_start = time.time()
        scored_items = []
        for item in request.items:
            score, explanation = self._calculate_score(
                item, request.user_context, intent
            )
            scored_items.append((item, score, explanation))
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)
        ranking_time = (time.time() - ranking_start) * 1000
        
        # Step 3: Apply diversity guardrails
        diversity_start = time.time()
        diverse_items = self._apply_diversity(scored_items, request.user_context)
        diversity_time = (time.time() - diversity_start) * 1000
        
        # Step 4: Create ranked items with explanations
        ranked_items = [
            RankedItem(
                item=item,
                rank=idx + 1,
                score=score,
                explanation=explanation
            )
            for idx, (item, score, explanation) in enumerate(diverse_items)
        ]
        
        total_time = (time.time() - start_time) * 1000
        
        return RankingResponse(
            ranked_items=ranked_items,
            latency=LatencyBreakdown(
                total_ms=total_time,
                intent_parsing_ms=intent_time,
                ranking_ms=ranking_time,
                diversity_check_ms=diversity_time
            ),
            intent=intent
        )
    
    def _calculate_score(
        self, 
        item: Item, 
        user_context: UserContext, 
        intent: Intent
    ) -> tuple[float, str]:
        """
        Calculate score for an item using deterministic rules.
        
        Returns:
            Tuple of (score, explanation)
        """
        score = 0.0
        factors = []
        
        # Base score from quality and popularity
        base_score = (item.quality_score * 0.4) + (item.popularity_score * 0.3)
        score += base_score
        factors.append(f"base={base_score:.2f}")
        
        # Intent-based adjustments (soft constraints)
        intent_boost = self._apply_intent_boost(item, intent)
        score += intent_boost
        if intent_boost > 0:
            factors.append(f"intent={intent_boost:.2f}")
        
        # User context preferences
        preference_boost = self._apply_preference_boost(item, user_context)
        score += preference_boost
        if preference_boost > 0:
            factors.append(f"preference={preference_boost:.2f}")
        
        # Budget constraints
        budget_penalty = self._apply_budget_constraint(item, user_context)
        score += budget_penalty
        if budget_penalty < 0:
            factors.append(f"budget={budget_penalty:.2f}")
        
        # History boost (repeat engagement)
        history_boost = self._apply_history_boost(item, user_context)
        score += history_boost
        if history_boost > 0:
            factors.append(f"history={history_boost:.2f}")
        
        explanation = " + ".join(factors) if factors else "default scoring"
        
        return max(0.0, min(1.0, score)), explanation
    
    def _apply_intent_boost(self, item: Item, intent: Intent) -> float:
        """Apply soft constraint boost based on intent type."""
        boost = 0.0
        
        if intent.intent_type == IntentType.POPULAR:
            boost = item.popularity_score * 0.2
        elif intent.intent_type == IntentType.PREMIUM:
            # Boost high-quality items
            boost = item.quality_score * 0.2
        elif intent.intent_type == IntentType.BUDGET:
            # Boost lower-priced items
            if item.price < self.BUDGET_PRICE_THRESHOLD_LOW:
                boost = 0.15
            elif item.price < self.BUDGET_PRICE_THRESHOLD_MID:
                boost = 0.1
        elif intent.intent_type == IntentType.DISCOVERY:
            # Boost less popular items for discovery
            boost = (1.0 - item.popularity_score) * 0.15
        
        # Apply extracted filters
        if intent.extracted_filters:
            if "price_max" in intent.extracted_filters:
                if item.price <= intent.extracted_filters["price_max"]:
                    boost += 0.1
            if "category" in intent.extracted_filters:
                if item.category.lower() == intent.extracted_filters["category"].lower():
                    boost += 0.15
            if "brand" in intent.extracted_filters:
                brand = item.attributes.get("brand", "").lower()
                if brand == intent.extracted_filters["brand"].lower():
                    boost += 0.15
        
        return boost
    
    def _apply_preference_boost(self, item: Item, user_context: UserContext) -> float:
        """Apply boost based on user preferences."""
        boost = 0.0
        
        if not user_context.preferences:
            return boost
        
        # Match category preference
        if "category" in user_context.preferences:
            if item.category == user_context.preferences["category"]:
                boost += 0.1
        
        # Match brand preference
        if "brand" in user_context.preferences:
            item_brand = item.attributes.get("brand", "")
            if item_brand == user_context.preferences["brand"]:
                boost += 0.1
        
        return boost
    
    def _apply_budget_constraint(self, item: Item, user_context: UserContext) -> float:
        """Apply penalty if item is outside budget range."""
        if not user_context.budget_range:
            return 0.0
        
        min_budget, max_budget = user_context.budget_range
        
        if item.price < min_budget:
            # Slightly penalize too cheap items
            return -0.05
        elif item.price > max_budget:
            # Heavily penalize items over budget
            return -0.3
        
        return 0.0
    
    def _apply_history_boost(self, item: Item, user_context: UserContext) -> float:
        """Apply boost if user has interacted with similar items."""
        if item.item_id in user_context.history:
            # Small boost for previously viewed items
            return 0.05
        return 0.0
    
    def _apply_diversity(
        self, 
        scored_items: List[tuple[Item, float, str]], 
        user_context: UserContext
    ) -> List[tuple[Item, float, str]]:
        """
        Apply diversity guardrails to prevent category clustering.
        
        Args:
            scored_items: List of (item, score, explanation) tuples sorted by score
            user_context: User context for personalization
            
        Returns:
            Reordered list with diversity applied
        """
        if len(scored_items) <= 3:
            # No diversity needed for small lists
            return scored_items
        
        diverse_list = []
        remaining = list(scored_items)
        
        while remaining:
            # Try to find an item that doesn't violate diversity constraint
            added = False
            for i, (item, score, explanation) in enumerate(remaining):
                category = item.category
                
                # Check diversity rule: No more than 2 consecutive items from same category
                if len(diverse_list) >= 2:
                    last_two_categories = [diverse_list[-1][0].category, diverse_list[-2][0].category]
                    if last_two_categories[0] == category and last_two_categories[1] == category:
                        # This would create 3 in a row, skip for now
                        continue
                
                # Add this item
                diverse_list.append((item, score, explanation))
                remaining.pop(i)
                added = True
                break
            
            # If we couldn't add any item without violating diversity
            # Find item with different category than the last one
            if not added and remaining:
                if len(diverse_list) >= 1:
                    last_category = diverse_list[-1][0].category
                    # Try to find an item with different category
                    found_different = False
                    for i, (item, score, explanation) in enumerate(remaining):
                        if item.category != last_category:
                            diverse_list.append((item, score, explanation))
                            remaining.pop(i)
                            found_different = True
                            break
                    
                    # If all remaining are same category, just add next one
                    if not found_different:
                        diverse_list.append(remaining.pop(0))
                else:
                    # First item, just add it
                    diverse_list.append(remaining.pop(0))
        
        return diverse_list
