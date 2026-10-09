"""Discover ranking signals — the intent→signal normalization boundary (spec §10).

Each signal translates a domain concept into a deterministic 0.0–1.0 "fit" score
computed only from candidate evidence and the request. Per spec §10 every signal
documents its meaning, range, calculation, and missing-value handling, and is
unit-tested. Signals never invent facts: a signal is only ``known`` when it rests
on actual evidence; otherwise it returns the neutral value and reports its basis
as UNKNOWN so the explanation layer (spec §13.1) can caveat it.

Scores are 0.0–1.0 (``NEUTRAL`` = 0.5, higher = better fit). The ranking adapter
(next slice) maps these onto the engine's multiplier chain (spec §12); strict
budget/distance limits stay in the constraint layer (`constraints.py`) and are
never overridden by a soft signal.

Evidence basis per signal:
- VERIFIED  — derived from a VERIFIED structured attribute.
- EXTRACTED — derived from unstructured text or an approximation (e.g. title
  keywords, straight-line distance as a stand-in for travel time).
- UNKNOWN   — no evidence; the neutral score is returned and `known` is False.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from intent_engine.discover.constraints import verified_total_range
from intent_engine.discover.schemas import (
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)

NEUTRAL = 0.5
MAX_DISTANCE_KM = 50.0

SIGNAL_NAMES: Tuple[str, ...] = (
    "family_friendly",
    "educational_value",
    "budget_fit",
    "distance_fit",
    "schedule_fit",
    "duration_fit",
)

_FAMILY_POSITIVE = frozenset({
    "family", "children", "child", "kid", "kids", "zoo", "aquarium", "museum",
    "park", "playground", "nature", "science", "animation", "circus", "puppet",
    "fair", "petting", "cartoon",
})
_FAMILY_NEGATIVE = frozenset({
    "nightlife", "nightclub", "club", "bar", "casino", "adult", "mature",
    "explicit", "18+", "21+", "burlesque",
})
_EDUCATIONAL_POSITIVE = frozenset({
    "museum", "science", "history", "historical", "educational", "planetarium",
    "aquarium", "zoo", "library", "art", "cultural", "nature", "botanical",
    "exhibit", "exhibition", "observatory", "heritage",
})
_EDUCATIONAL_NEGATIVE: frozenset = frozenset()


@dataclass(frozen=True)
class SignalResult:
    """One signal's deterministic outcome for a candidate."""

    name: str
    value: float  # 0.0–1.0 fit (NEUTRAL when not known)
    known: bool  # grounded in actual evidence?
    evidence_status: EvidenceStatus
    detail: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _category_or_title(candidate: DiscoveryCandidate) -> Tuple[Optional[str], EvidenceStatus]:
    """Prefer a VERIFIED category; fall back to title text (unstructured)."""
    category = candidate.evidence("category")
    if (
        category is not None
        and category.status is EvidenceStatus.VERIFIED
        and isinstance(category.value, str)
        and category.value.strip()
    ):
        return category.value, EvidenceStatus.VERIFIED
    if isinstance(candidate.title, str) and candidate.title.strip():
        return candidate.title, EvidenceStatus.EXTRACTED
    return None, EvidenceStatus.UNKNOWN


def _keyword_signal(
    name: str,
    candidate: DiscoveryCandidate,
    positives: frozenset,
    negatives: frozenset,
) -> SignalResult:
    text, status = _category_or_title(candidate)
    if text is None:
        return SignalResult(name, NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "no category or title to assess")
    lowered = text.lower()
    tokens = set(lowered.replace("/", " ").replace("-", " ").split())
    if any(word in tokens or word in lowered for word in negatives):
        return SignalResult(name, 0.15, True, status, f"unsuitable keyword in '{text}'")
    if any(word in tokens or word in lowered for word in positives):
        return SignalResult(name, 0.9, True, status, f"relevant keyword in '{text}'")
    # Had text but nothing to go on — absence of a keyword is not evidence.
    return SignalResult(name, NEUTRAL, False, EvidenceStatus.UNKNOWN,
                        f"no relevant keyword in '{text}'")


def family_friendly(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """Suitability for a family/children, from category (else title keywords)."""
    return _keyword_signal("family_friendly", candidate, _FAMILY_POSITIVE, _FAMILY_NEGATIVE)


def educational_value(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """Educational character, from category (else title keywords)."""
    return _keyword_signal("educational_value", candidate, _EDUCATIONAL_POSITIVE, _EDUCATIONAL_NEGATIVE)


def budget_fit(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """How comfortably a VERIFIED total fits the stated budget (soft preference).

    Neutral/unknown when no budget is stated or no total can be established; the
    hard budget constraint (constraints.py) owns strict exclusion.
    """
    if request.budget_total is None:
        return SignalResult("budget_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "no budget stated")
    min_total, _ = verified_total_range(candidate, request)
    if min_total is None:
        return SignalResult("budget_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "total cost not verified")
    budget = request.budget_total
    headroom = float((budget - min_total) / budget)  # 1.0 free, 0.0 at budget, <0 over
    value = _clamp(0.5 + 0.5 * headroom)
    return SignalResult("budget_fit", value, True, EvidenceStatus.VERIFIED,
                        f"verified total from {min_total} against budget {budget}")


def distance_fit(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """Proximity to a requested coordinate (straight-line approximation).

    Marked EXTRACTED: straight-line distance stands in for travel time, which is
    not verified. Neutral/unknown without both request and candidate coordinates.
    """
    if (
        not request.has_precise_location
        or candidate.latitude is None
        or candidate.longitude is None
    ):
        return SignalResult("distance_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "request or candidate location unavailable")
    distance = _haversine_km(
        request.latitude, request.longitude, candidate.latitude, candidate.longitude
    )
    value = _clamp(1.0 - distance / MAX_DISTANCE_KM)
    return SignalResult("distance_fit", value, True, EvidenceStatus.EXTRACTED,
                        f"~{distance:.1f} km straight-line")


def schedule_fit(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """How well a VERIFIED event time matches the requested date window."""
    if request.start_date is None and request.end_date is None:
        return SignalResult("schedule_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "no date window stated")
    start = candidate.evidence("start_time")
    if start is None or start.status is not EvidenceStatus.VERIFIED or not isinstance(start.value, datetime):
        return SignalResult("schedule_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "event time not verified")
    day = start.value.date()
    within = (
        (request.start_date is None or day >= request.start_date)
        and (request.end_date is None or day <= request.end_date)
    )
    return SignalResult("schedule_fit", 1.0 if within else 0.0, True, EvidenceStatus.VERIFIED,
                        f"event {day.isoformat()} {'within' if within else 'outside'} window")


def duration_fit(candidate: DiscoveryCandidate, request: DiscoveryRequest) -> SignalResult:
    """Closeness of a VERIFIED activity duration to the requested duration.

    Typically UNKNOWN in the pilot — providers do not return a verified duration.
    """
    if request.duration_minutes is None:
        return SignalResult("duration_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "no duration preference stated")
    duration = candidate.evidence("duration_minutes")
    if (
        duration is None
        or duration.status is not EvidenceStatus.VERIFIED
        or isinstance(duration.value, bool)
        or not isinstance(duration.value, (int, float))
    ):
        return SignalResult("duration_fit", NEUTRAL, False, EvidenceStatus.UNKNOWN,
                            "activity duration not verified")
    requested = request.duration_minutes
    value = _clamp(1.0 - abs(float(duration.value) - requested) / requested)
    return SignalResult("duration_fit", value, True, EvidenceStatus.VERIFIED,
                        f"{duration.value} min vs requested {requested} min")


def compute_signals(
    candidate: DiscoveryCandidate, request: DiscoveryRequest
) -> Dict[str, SignalResult]:
    """All six Discover ranking signals for one candidate (deterministic)."""
    return {
        "family_friendly": family_friendly(candidate, request),
        "educational_value": educational_value(candidate, request),
        "budget_fit": budget_fit(candidate, request),
        "distance_fit": distance_fit(candidate, request),
        "schedule_fit": schedule_fit(candidate, request),
        "duration_fit": duration_fit(candidate, request),
    }
