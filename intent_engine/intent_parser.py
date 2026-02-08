"""Intent parsing with rules-first approach (LLM optional)."""

import re
from typing import Dict, Any
from .schemas import Intent, IntentType


class IntentParser:
    """Rules-based intent parser with optional LLM fallback."""
    
    # Keywords for intent classification (ordered by specificity)
    INTENT_KEYWORDS = {
        IntentType.POPULAR: ["popular", "trending", "bestseller", "top-rated", "favorite"],
        IntentType.BUDGET: ["cheap", "affordable", "budget", "save", "discount"],
        IntentType.PREMIUM: ["premium", "luxury", "high-end"],
        IntentType.COMPARISON: ["compare", "versus", "vs", "difference", "better than"],
        IntentType.TARGETED: ["looking for", "searching for", "find", "search", "need", "want", "specific"],
        IntentType.DISCOVERY: ["explore", "discover", "new", "browse", "surprise"],
    }
    
    # Filter extraction patterns
    FILTER_PATTERNS = {
        "price_max": r"(?:under|below|less than|<)\s*\$?(\d+(?:\.\d+)?)",
        "price_min": r"(?:over|above|more than|>)\s*\$?(\d+(?:\.\d+)?)",
        "category": r"(?:in|from|category)\s+([a-zA-Z]+)",
        "brand": r"(?:brand|from|by)\s+([a-zA-Z]+)",
    }
    
    def parse(self, intent_text: str = None, use_llm: bool = False) -> Intent:
        """
        Parse intent from text using rules-first approach.
        
        Args:
            intent_text: Optional text describing user intent
            use_llm: Whether to use LLM for parsing (off by default)
            
        Returns:
            Intent object with classification and extracted filters
        """
        # Default to UNKNOWN if no text provided
        if not intent_text:
            return Intent(
                intent_type=IntentType.UNKNOWN,
                intent_text=None,
                extracted_filters={},
                confidence=0.0,
                use_llm=False
            )
        
        # Normalize text
        normalized_text = intent_text.lower().strip()
        
        # Rules-first classification
        intent_type, confidence = self._classify_intent_rules(normalized_text)
        
        # Extract filters using regex patterns
        extracted_filters = self._extract_filters_rules(normalized_text)
        
        # If LLM is enabled and confidence is low, could enhance here
        # For now, LLM is optional and off by default
        if use_llm and confidence < 0.5:
            # Placeholder for LLM enhancement
            # In production, would call LLM service here
            pass
        
        return Intent(
            intent_type=intent_type,
            intent_text=intent_text,
            extracted_filters=extracted_filters,
            confidence=confidence,
            use_llm=use_llm
        )
    
    def _classify_intent_rules(self, text: str) -> tuple[IntentType, float]:
        """
        Classify intent using keyword matching.
        
        Args:
            text: Normalized intent text
            
        Returns:
            Tuple of (intent_type, confidence)
        """
        best_match = IntentType.UNKNOWN
        best_score = 0
        
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > best_score:
                best_score = score
                best_match = intent_type
        
        # Calculate confidence based on match count
        if best_score == 0:
            return IntentType.UNKNOWN, 0.0
        elif best_score == 1:
            return best_match, 0.6
        elif best_score == 2:
            return best_match, 0.8
        else:
            return best_match, 0.95
    
    def _extract_filters_rules(self, text: str) -> Dict[str, Any]:
        """
        Extract filters from text using regex patterns.
        
        Args:
            text: Normalized intent text
            
        Returns:
            Dictionary of extracted filters
        """
        filters = {}
        
        for filter_name, pattern in self.FILTER_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                # Convert numeric values
                if filter_name.startswith("price"):
                    filters[filter_name] = float(value)
                else:
                    filters[filter_name] = value
        
        return filters
