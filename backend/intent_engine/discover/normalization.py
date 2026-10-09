"""Candidate normalization and deduplication (spec section 9).

Providers already emit validated ``DiscoveryCandidate`` objects, so normalization
here means collapsing overlapping results — the same real-world activity returned
by more than one provider, or twice by one provider — into a single candidate
without losing evidence or attribution.

Dedup rules:
- Exact ``candidate_id`` repeats collapse to the first occurrence.
- Cross-provider matches are detected by a conservative fingerprint: normalized
  title AND at least one strong discriminator (event date or coarse coordinates).
  Title-only collisions are NOT merged, to avoid fusing distinct activities.
- The surviving "primary" is the member with the most VERIFIED attributes (ties
  broken deterministically). Merging only ever *adds* a VERIFIED attribute from
  another member where the primary had none — it never overwrites a verified
  value or fabricates one. Each merged attribute keeps its own provenance, so
  cross-provider evidence stays attributable.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from intent_engine.discover.schemas import DiscoveryCandidate, EvidenceStatus

# Candidate scalar fields whose value can be lifted from a merged attribute.
_SCALAR_FIELDS = frozenset(
    {
        "category",
        "location_name",
        "latitude",
        "longitude",
        "start_time",
        "end_time",
        "price_min",
        "price_max",
        "currency",
        "age_min",
        "age_max",
        "description",
    }
)

_WHITESPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for matching."""
    lowered = _NON_WORD.sub(" ", title.lower())
    return _WHITESPACE.sub(" ", lowered).strip()


def _verified_count(candidate: DiscoveryCandidate) -> int:
    return sum(
        1
        for prov in candidate.provenance.values()
        if prov.status is EvidenceStatus.VERIFIED
    )


Fingerprint = Tuple[str, Optional[str], Optional[Tuple[float, float]]]


def candidate_fingerprint(candidate: DiscoveryCandidate) -> Optional[Fingerprint]:
    """A conservative cross-provider identity, or None if not safely mergeable.

    Requires a normalized title plus at least one strong discriminator (verified
    event date or coarse coordinates). Without a discriminator we return None so
    the candidate is treated as unique.
    """
    title = normalize_title(candidate.title)
    if not title:
        return None

    date_key: Optional[str] = None
    start = candidate.evidence("start_time")
    if (
        start is not None
        and start.status is EvidenceStatus.VERIFIED
        and isinstance(start.value, datetime)
    ):
        date_key = start.value.date().isoformat()

    geo_key: Optional[Tuple[float, float]] = None
    if candidate.latitude is not None and candidate.longitude is not None:
        geo_key = (round(candidate.latitude, 3), round(candidate.longitude, 3))

    if date_key is None and geo_key is None:
        return None
    return (title, date_key, geo_key)


def _merge_into(primary: DiscoveryCandidate, other: DiscoveryCandidate) -> None:
    """Add VERIFIED evidence from ``other`` for attributes the primary lacks."""
    for attribute, prov in other.provenance.items():
        if prov.status is not EvidenceStatus.VERIFIED:
            continue
        existing = primary.provenance.get(attribute)
        if existing is not None and existing.status is EvidenceStatus.VERIFIED:
            continue  # never overwrite an already-verified attribute
        primary.provenance[attribute] = prov
        if attribute in _SCALAR_FIELDS:
            setattr(primary, attribute, prov.value)

    merged_from = primary.attributes.get("merged_from", [])
    if other.candidate_id not in merged_from:
        merged_from = [*merged_from, other.candidate_id]
    primary.attributes["merged_from"] = sorted(merged_from)


def deduplicate_candidates(
    candidates: List[DiscoveryCandidate],
) -> List[DiscoveryCandidate]:
    """Collapse exact and cross-provider duplicates, preserving first-seen order."""
    # 1) Drop exact candidate_id repeats.
    by_id: Dict[str, DiscoveryCandidate] = {}
    ordered: List[DiscoveryCandidate] = []
    for candidate in candidates:
        if candidate.candidate_id in by_id:
            continue
        by_id[candidate.candidate_id] = candidate
        ordered.append(candidate)

    # 2) Group the mergeable ones by fingerprint (insertion order = first seen).
    groups: Dict[Fingerprint, List[DiscoveryCandidate]] = {}
    result: List[DiscoveryCandidate] = []
    for candidate in ordered:
        fingerprint = candidate_fingerprint(candidate)
        if fingerprint is None:
            result.append(candidate)  # not safely mergeable -> unique
            continue
        groups.setdefault(fingerprint, []).append(candidate)

    # 3) Collapse each group onto a deterministic primary.
    for members in groups.values():
        primary = min(
            members,
            key=lambda c: (-_verified_count(c), c.provider, c.candidate_id),
        )
        for member in members:
            if member is primary:
                continue
            _merge_into(primary, member)
        result.append(primary)

    # 4) Restore first-seen order across the whole result set.
    order = {candidate.candidate_id: i for i, candidate in enumerate(ordered)}
    result.sort(key=lambda c: order[c.candidate_id])
    return result
