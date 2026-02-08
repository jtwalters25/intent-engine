"""Deterministic re-ranking module for the Intent Engine."""

from typing import List, Dict, Any
from intent_engine.schemas import UserContext, CandidateItem, RankedItem


class IntentRanker:
    """A deterministic ranker that scores items based on user intent as a soft constraint."""
    
    def __init__(self, intent_weight: float = 0.5):
        """Initialize the ranker.
        
        Args:
            intent_weight: Weight for intent score vs base score (0.0-1.0).
                          0.0 = use only base_score, 1.0 = use only intent_score
        """
        if not 0.0 <= intent_weight <= 1.0:
            raise ValueError("intent_weight must be between 0.0 and 1.0")
        self.intent_weight = intent_weight
    
    def _calculate_keyword_match_score(self, item: CandidateItem, keywords: List[str]) -> float:
        """Calculate how well an item matches the intent keywords.
        
        Args:
            item: The candidate item
            keywords: List of intent keywords
            
        Returns:
            A score between 0.0 and 1.0
        """
        if not keywords:
            return 0.5  # Neutral score if no keywords
        
        # Extract searchable text from item
        searchable_fields = [
            item.title.lower(),
            str(item.attributes.get("tags", [])).lower(),
            str(item.attributes.get("category", "")).lower(),
            str(item.attributes.get("description", "")).lower(),
        ]
        searchable_text = " ".join(searchable_fields)
        
        # Calculate match ratio
        matches = sum(1 for keyword in keywords if keyword.lower() in searchable_text)
        return matches / len(keywords)
    
    def _calculate_preference_match_score(
        self, item: CandidateItem, preferences: Dict[str, Any]
    ) -> float:
        """Calculate how well an item matches the intent preferences.
        
        Args:
            item: The candidate item
            preferences: Dictionary of preferences
            
        Returns:
            A score between 0.0 and 1.0
        """
        if not preferences:
            return 0.5  # Neutral score if no preferences
        
        matches = 0
        total = len(preferences)
        
        for key, value in preferences.items():
            item_value = item.attributes.get(key)
            if item_value is not None:
                # Exact match for strings, equality for numbers
                if isinstance(value, str) and isinstance(item_value, str):
                    if value.lower() == item_value.lower():
                        matches += 1
                elif value == item_value:
                    matches += 1
        
        return matches / total if total > 0 else 0.5
    
    def _calculate_intent_score(self, item: CandidateItem, context: UserContext) -> float:
        """Calculate the intent-based score for an item.
        
        Args:
            item: The candidate item
            context: The user context with intent
            
        Returns:
            A combined intent score between 0.0 and 1.0
        """
        intent = context.intent
        
        # Calculate component scores
        keyword_score = self._calculate_keyword_match_score(item, intent.keywords)
        preference_score = self._calculate_preference_match_score(item, intent.preferences)
        
        # Combine scores with intent priority
        combined_score = (keyword_score + preference_score) / 2
        weighted_score = combined_score * intent.priority
        
        return weighted_score
    
    def _generate_explanation(
        self, item: CandidateItem, context: UserContext, intent_score: float
    ) -> str:
        """Generate a human-readable explanation for the ranking.
        
        Args:
            item: The candidate item
            context: The user context
            intent_score: The calculated intent score
            
        Returns:
            An explanation string
        """
        intent = context.intent
        explanations = []
        
        # Keyword matching explanation
        if intent.keywords:
            matched_keywords = [
                kw for kw in intent.keywords
                if kw.lower() in item.title.lower() or 
                   kw.lower() in str(item.attributes).lower()
            ]
            if matched_keywords:
                explanations.append(
                    f"Matches intent keywords: {', '.join(matched_keywords)}"
                )
        
        # Preference matching explanation
        if intent.preferences:
            matched_prefs = []
            for key, value in intent.preferences.items():
                item_value = item.attributes.get(key)
                if item_value is not None and str(value).lower() == str(item_value).lower():
                    matched_prefs.append(f"{key}={value}")
            if matched_prefs:
                explanations.append(
                    f"Matches preferences: {', '.join(matched_prefs)}"
                )
        
        # Score-based explanation
        if intent_score >= 0.7:
            explanations.append("Strong intent match")
        elif intent_score >= 0.4:
            explanations.append("Moderate intent match")
        else:
            explanations.append("Weak intent match")
        
        return "; ".join(explanations) if explanations else "No specific intent match"
    
    def rank(self, candidates: List[CandidateItem], context: UserContext) -> List[RankedItem]:
        """Rank candidate items based on user context and intent.
        
        Args:
            candidates: List of candidate items to rank
            context: User context with intent
            
        Returns:
            List of ranked items sorted by final score (highest first)
        """
        ranked_items = []
        
        for item in candidates:
            # Calculate intent score
            intent_score = self._calculate_intent_score(item, context)
            
            # Combine base score and intent score
            final_score = (
                (1 - self.intent_weight) * item.base_score +
                self.intent_weight * intent_score
            )
            
            # Generate explanation
            explanation = self._generate_explanation(item, context, intent_score)
            
            # Create ranked item
            ranked_item = RankedItem(
                item=item,
                final_score=final_score,
                intent_score=intent_score,
                explanation=explanation
            )
            ranked_items.append(ranked_item)
        
        # Sort by final score (descending)
        ranked_items.sort(key=lambda x: x.final_score, reverse=True)
        
        return ranked_items
