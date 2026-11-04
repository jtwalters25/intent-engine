"""Anthropic-backed ``LLMClient`` for the Discover eval's ``llm_only`` arm (spec §16, arm B).

This is the real client the harness previously deferred. It is **evaluation-only
and off by default**: nothing in the `/discover/search` request or ranking path
uses it, and it is constructed only when an ``ANTHROPIC_API_KEY`` (or an injected
client) is available.

Design
------
- The model is shown the same ``VERIFIED`` / ``EXTRACTED`` / ``UNKNOWN`` provenance
  the engine sees, plus the stated hard constraints, and asked for a ranking with
  per-candidate claims. This is the *fair* LLM baseline (§16): a faithful model
  scores well, and a reckless one that asserts an ``UNKNOWN`` as fact is caught by
  ``critical_factual_error_count``. We deliberately do **not** sanitize the model's
  output into faithfulness — doing so would rig the comparison the pilot exists to run.
- Output is constrained with **structured outputs** (a strict response schema via
  ``messages.parse``), so the response maps deterministically into ``LLMArmOutput``
  without brittle free-text parsing. The schema forces the model to commit an
  evidence status to every claim; mislabelling an unknown as ``VERIFIED`` then
  shows up in the metrics rather than being silently dropped.
- The ``anthropic`` SDK is imported **lazily** and the underlying client is
  **injectable**, so this module imports — and its tests run — with no SDK
  installed and no network access (spec §19: the standard suite never hits a live API).

Default model is Claude Opus 4.8 (``claude-opus-4-8``) with adaptive thinking.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from intent_engine.discover.evaluation.baselines import LLMArmOutput
from intent_engine.discover.evaluation.contracts import (
    AssertedFact,
    CandidateSnapshot,
    StatedConstraints,
)
from intent_engine.discover.schemas import ClaimKind, EvidenceStatus, ExplanationClaim

_DEFAULT_MODEL = "claude-opus-4-8"
_DEFAULT_MAX_TOKENS = 4096

_SYSTEM = (
    "You rank real-world family activities against a parent's request and explain "
    "each pick. Every attribute carries a provenance tag: VERIFIED (from a structured "
    "source — safe to state as fact), EXTRACTED (inferred from text — hedge it), or "
    "UNKNOWN (absent — never assert it; flag it as needs-verification). For each "
    "candidate, emit atomic claims whose evidence_status matches the attribute's "
    "provenance. Use kind='caveat' only for UNKNOWN or EXTRACTED attributes, never for "
    "a VERIFIED one. Set asserted_value only when you are stating a concrete value for "
    "that attribute. Rank the most suitable candidates first."
)


# --- structured-output response schema (kept plain for the API; not the eval types) ---


class _LLMClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    attribute: str
    text: str
    evidence_status: EvidenceStatus
    kind: ClaimKind
    asserted_value: Optional[str] = None


class _LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranking: List[str]
    claims: List[_LLMClaim]


# --- helpers ---


def _coerce_value(raw: Optional[str]) -> Any:
    """Best-effort typing so an asserted value compares fairly to ground truth.

    Ground-truth values are numbers / booleans; the model returns strings. We
    coerce int, then float, then bool, else keep the string. We never fabricate a
    value from nothing — ``None`` stays ``None``.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    low = text.lower()
    if low in {"true", "yes"}:
        return True
    if low in {"false", "no"}:
        return False
    return text


def _to_claim(claim: _LLMClaim) -> Optional[ExplanationClaim]:
    """Build an ExplanationClaim, coercing the one incoherent combo instead of dropping it.

    A caveat may not rest on a VERIFIED attribute. If the model emits that combo we
    keep the claim (and its VERIFIED status, so the assertion still counts against the
    arm) but relabel the kind to MATCH rather than discarding the evidence.
    """
    text = claim.text.strip()
    attribute = claim.attribute.strip()
    if not text or not attribute:
        return None
    kind = claim.kind
    if kind is ClaimKind.CAVEAT and claim.evidence_status is EvidenceStatus.VERIFIED:
        kind = ClaimKind.MATCH
    return ExplanationClaim(
        text=text,
        kind=kind,
        attribute=attribute,
        evidence_status=claim.evidence_status,
    )


def _to_arm_output(parsed: _LLMResponse, pool: List[CandidateSnapshot]) -> LLMArmOutput:
    """Map the model's structured output onto the eval contract, faithfully.

    Candidate ids not in the shared pool (hallucinated) are dropped; everything else
    is preserved as the model produced it — including unfaithful assertions, which
    the metrics are designed to catch.
    """
    valid = {s.candidate_id for s in pool}

    ranking: List[str] = []
    seen: set = set()
    for cid in parsed.ranking:
        if cid in valid and cid not in seen:
            ranking.append(cid)
            seen.add(cid)

    explanations: Dict[str, List[ExplanationClaim]] = {}
    facts: List[AssertedFact] = []
    for raw in parsed.claims:
        if raw.candidate_id not in valid:
            continue
        claim = _to_claim(raw)
        if claim is None:
            continue
        explanations.setdefault(raw.candidate_id, []).append(claim)
        value = _coerce_value(raw.asserted_value)
        if value is not None and raw.evidence_status is not EvidenceStatus.UNKNOWN:
            facts.append(
                AssertedFact(
                    candidate_id=raw.candidate_id,
                    attribute=claim.attribute,
                    asserted_value=value,
                    asserted_as=raw.evidence_status,
                )
            )

    return LLMArmOutput(ranking=ranking, explanations=explanations, asserted_facts=facts)


def _render_pool(pool: List[CandidateSnapshot]) -> List[dict]:
    rendered = []
    for snapshot in pool:
        attrs = {
            name: {"value": prov.value, "provenance": prov.status.value}
            for name, prov in snapshot.attributes.items()
        }
        rendered.append({"candidate_id": snapshot.candidate_id, "attributes": attrs})
    return rendered


def _build_prompt(pool: List[CandidateSnapshot], stated: StatedConstraints) -> str:
    payload = {
        "stated_constraints": stated.model_dump(mode="json", exclude_none=True),
        "candidates": _render_pool(pool),
    }
    return (
        "Rank these candidates for the request and explain each with grounded claims.\n\n"
        + json.dumps(payload, sort_keys=True, default=str)
    )


class AnthropicLLMClient:
    """Concrete ``LLMClient`` (spec §16 arm B) backed by the Anthropic Messages API.

    ``client`` is injectable for tests; when omitted, an ``anthropic.Anthropic()``
    is built lazily on first use and reads ``ANTHROPIC_API_KEY`` from the environment.
    """

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        client: Any = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self._model = model
        self._client = client
        self._max_tokens = max_tokens

    def _ensure_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy: module imports without the SDK installed

            self._client = anthropic.Anthropic()
        return self._client

    def rank(self, pool: List[CandidateSnapshot], stated: StatedConstraints) -> LLMArmOutput:
        client = self._ensure_client()
        message = client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(pool, stated)}],
            output_format=_LLMResponse,
        )
        return _to_arm_output(message.parsed_output, pool)


def default_llm_client(*, model: str = _DEFAULT_MODEL) -> Optional[AnthropicLLMClient]:
    """Return an Anthropic arm-B client only when an API key is configured; else None.

    Off by default: with no ``ANTHROPIC_API_KEY`` the eval harness keeps using its
    injected/mocked client and no live calls are possible.
    """
    import os

    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return None
    return AnthropicLLMClient(model=model)
