"""Grounded explanations for ranked Discover candidates (spec section 13.1).

An explanation is a set of atomic ``ExplanationClaim``s generated deterministically
from ranking signals and constraint results — never written freely:

- Each match/tradeoff claim maps to one *known* signal, or to a PASS hard
  constraint. A claim is stated as fact only when its evidence is VERIFIED;
  EXTRACTED evidence is hedged ("appears to …").
- Every UNKNOWN hard constraint that affected eligibility (price, age, …) yields
  a mandatory caveat. Silence on a relevant unknown is a defect (§13.1).

``render`` is a deterministic template over the claims. An optional LLM may only
rephrase the rendered text; it may not add, drop, or upgrade a claim. The claim
list is the retained evidence that ``explanation_accuracy`` scores (§16).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from intent_engine.discover.ranking import RankedCandidate
from intent_engine.discover.schemas import ClaimKind, EvidenceStatus, ExplanationClaim
from intent_engine.discover.signals import SIGNAL_NAMES

# Strong-fit / weak-fit thresholds on the 0–1 signal scale.
_STRONG = 0.66
_WEAK = 0.34

# Human-readable attribute label per signal.
_SIGNAL_ATTR = {
    "family_friendly": "family suitability",
    "educational_value": "educational value",
    "budget_fit": "price",
    "distance_fit": "distance",
    "schedule_fit": "schedule",
    "duration_fit": "duration",
}


@dataclass(frozen=True)
class Explanation:
    claims: List[ExplanationClaim]
    text: str


def _match_text(attr: str, verified: bool) -> str:
    return f"matches your {attr}" if verified else f"appears to match your {attr}"


def _tradeoff_text(attr: str, verified: bool) -> str:
    return f"is a weaker fit on {attr}" if verified else f"may be a weaker fit on {attr}"


def build_claims(ranked: RankedCandidate) -> List[ExplanationClaim]:
    """Deterministic claim set for one ranked candidate (spec §13.1)."""
    claims: List[ExplanationClaim] = []

    # 1) Signal-derived match / tradeoff claims (only for signals with evidence).
    for name in SIGNAL_NAMES:
        detail = ranked.signal_details[name]
        if not detail.known:
            continue
        attr = _SIGNAL_ATTR[name]
        verified = detail.evidence_status is EvidenceStatus.VERIFIED
        if detail.value >= _STRONG:
            claims.append(ExplanationClaim(
                text=_match_text(attr, verified), kind=ClaimKind.MATCH,
                attribute=attr, evidence_status=detail.evidence_status, signal=name,
            ))
        elif detail.value <= _WEAK:
            claims.append(ExplanationClaim(
                text=_tradeoff_text(attr, verified), kind=ClaimKind.TRADEOFF,
                attribute=attr, evidence_status=detail.evidence_status, signal=name,
            ))
        # a known-but-neutral signal asserts nothing

    # 2) Constraint-derived claims: PASS -> match (fact); UNKNOWN -> mandatory caveat.
    for name, state in sorted(ranked.constraint_states.items()):
        label = name.replace("_", " ")
        if state == "PASS":
            claims.append(ExplanationClaim(
                text=f"{label} is satisfied", kind=ClaimKind.MATCH,
                attribute=name, evidence_status=EvidenceStatus.VERIFIED, signal=None,
            ))
        elif state == "UNKNOWN":
            claims.append(ExplanationClaim(
                text=f"{label} needs verification", kind=ClaimKind.CAVEAT,
                attribute=name, evidence_status=EvidenceStatus.UNKNOWN, signal=None,
            ))

    return claims


def _oxford(parts: List[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def render(claims: List[ExplanationClaim]) -> str:
    """Deterministic sentence template over the claims."""
    matches = [c.text for c in claims if c.kind is ClaimKind.MATCH]
    tradeoffs = [c.text for c in claims if c.kind is ClaimKind.TRADEOFF]
    caveats = [c.text for c in claims if c.kind is ClaimKind.CAVEAT]

    segments: List[str] = []
    if matches:
        segments.append("Recommended because it " + _oxford(matches) + ".")
    if tradeoffs:
        segments.append("Trade-off: it " + _oxford(tradeoffs) + ".")
    if caveats:
        caveat = _oxford(caveats)
        segments.append(caveat[0].upper() + caveat[1:] + ".")
    if not segments:
        return "No distinguishing evidence available for this option."
    return " ".join(segments)


def explain(ranked: RankedCandidate) -> Explanation:
    """Build the grounded claim set and its deterministic rendered sentence."""
    claims = build_claims(ranked)
    return Explanation(claims=claims, text=render(claims))
