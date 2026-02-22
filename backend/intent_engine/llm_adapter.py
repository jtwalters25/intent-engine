"""LLM adapter for optional intent enhancement.

OFF by default. Enable via the LLM_ENABLED environment variable.

Design:
- Returns Optional[Intent]; None means "use rules fallback".
- Strict JSON parsing + Pydantic validation on LLM output.
- Structured logging (no raw user text in logs).
- Any exception → returns None (never crashes the pipeline).
"""

import json
import logging
import os
from typing import Optional

from .schemas import Intent, IntentType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_ENABLED: bool = os.environ.get("LLM_ENABLED", "").lower() in ("1", "true", "yes")


class LLMAdapter:
    """Adapter that calls an external LLM for intent classification.

    When ``enabled=True`` *and* the global ``LLM_ENABLED`` env-var is set,
    ``enhance()`` will attempt to parse LLM output into an ``Intent``.
    Otherwise it short-circuits and returns ``None`` (rules take over).
    """

    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled and LLM_ENABLED

    def enhance(self, intent_text: str) -> Optional[Intent]:
        """Attempt to classify *intent_text* via an LLM.

        Returns:
            An ``Intent`` if the LLM responds with valid JSON, else ``None``.
        """
        if not self.enabled:
            return None

        if not intent_text or not intent_text.strip():
            return None

        try:
            raw_response = self._call_llm(intent_text)
            return self._parse_response(raw_response)
        except Exception:
            logger.warning("LLM adapter failed; falling back to rules", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(self, intent_text: str) -> str:
        """Call the external LLM service.

        This is the integration point. Replace the body of this method
        with your actual HTTP/SDK call. The method MUST return a JSON
        string or raise on failure.

        Currently a no-op stub that returns empty JSON so the adapter
        gracefully falls back to rules when enabled.
        """
        logger.debug("LLM call requested (stub — returning empty)")
        return "{}"

    def _parse_response(self, raw: str) -> Optional[Intent]:
        """Parse and validate raw LLM JSON into an Intent.

        Accepts a JSON object with optional keys matching Intent fields.
        Unknown keys are silently ignored. Invalid JSON or validation
        failures return None (never raises).
        """
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned non-JSON response")
            return None

        if not isinstance(data, dict):
            logger.warning("LLM returned non-object JSON")
            return None

        # Must have at least intent_type to be useful
        if "intent_type" not in data:
            return None

        try:
            return Intent(
                intent_type=data["intent_type"],
                keywords=data.get("keywords", []),
                preferences=data.get("preferences", {}),
                priority=float(data.get("priority", 0.7)),
                intent_text=data.get("intent_text"),
                extracted_filters=data.get("extracted_filters", {}),
                confidence=float(data.get("confidence", 0.8)),
                use_llm=True,
            )
        except (ValueError, TypeError) as exc:
            logger.warning("LLM response failed Pydantic validation: %s", type(exc).__name__)
            return None
