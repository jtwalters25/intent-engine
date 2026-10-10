"""Fixture provider for demos and offline runs (no API keys, no network).

Returns a varied, realistic candidate pool with the same provenance discipline as
the real adapters — structured facts are VERIFIED, honest unknowns stay UNKNOWN,
descriptions are EXTRACTED — so the full pipeline (constraints, ranking,
explanations) behaves exactly as it would on live data. Selected via
``DISCOVER_DEMO_MODE`` (see ``config.py``); never a silent default in production.

The pool is intentionally diverse so a demo shows the engine's range:
- categories: science, museum, zoo, aquarium, park, music, theatre, comedy, food;
- price states: verified range w/ unknown basis (→ budget needs verification),
  verified per-ticket/per-person basis (→ budget can PASS **or** FAIL), and no
  price at all (→ unknown);
- age gates: all-ages, 4+, 16+, 18+ (→ hard exclusions for younger parties);
- timing: dated events vs undated places (→ date-window PASS vs UNKNOWN).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _verified(value, field: str, url: str, now: datetime) -> AttributeProvenance:
    return AttributeProvenance(value=value, status=EvidenceStatus.VERIFIED, source="fixture",
                               source_url=url, retrieved_at=now, source_field=field)


def _extracted(value, url: str, now: datetime) -> AttributeProvenance:
    return AttributeProvenance(value=value, status=EvidenceStatus.EXTRACTED, source="fixture",
                               source_url=url, retrieved_at=now, extractor="fixture-text-v1")


def _unknown(url: str, now: datetime) -> AttributeProvenance:
    return AttributeProvenance(value=None, status=EvidenceStatus.UNKNOWN, source="fixture",
                               source_url=url, retrieved_at=now)


def _candidate(
    now: datetime,
    *,
    cid: str,
    provider: str,
    title: str,
    url: str,
    category: str,
    lat: float,
    lng: float,
    location_name: str,
    description: str,
    start_offset_days: Optional[int] = None,
    price_min: Optional[Decimal] = None,
    price_max: Optional[Decimal] = None,
    price_basis: Optional[str] = None,
    age_min: Optional[int] = None,
) -> DiscoveryCandidate:
    start = now + timedelta(days=start_offset_days) if start_offset_days is not None else None
    cand = DiscoveryCandidate(
        candidate_id=cid, provider=provider, provider_id=cid.split(":")[-1], title=title,
        source_url=url, retrieved_at=now, category=category, location_name=location_name,
        latitude=lat, longitude=lng, start_time=start, description=description,
        price_min=price_min, price_max=price_max,
        currency="USD" if price_min is not None else None,
        age_min=age_min,
        attributes={"demo": True},
    )
    prov: Dict[str, AttributeProvenance] = {
        "title": _verified(title, "name", url, now),
        "category": _verified(category, "classification", url, now),
        "location_name": _verified(location_name, "venue.name", url, now),
        "latitude": _verified(lat, "venue.location.latitude", url, now),
        "longitude": _verified(lng, "venue.location.longitude", url, now),
        "description": _extracted(description, url, now),
        # Honest unknowns — mirror real provider output.
        "availability": _unknown(url, now),
        "duration_minutes": _unknown(url, now),
        "end_time": _unknown(url, now),
    }
    prov["start_time"] = _verified(start, "dates.start.dateTime", url, now) if start is not None else _unknown(url, now)
    if price_min is not None:
        prov["price_min"] = _verified(price_min, "priceRanges[].min", url, now)
        prov["price_max"] = _verified(price_max if price_max is not None else price_min, "priceRanges[].max", url, now)
        prov["currency"] = _verified("USD", "priceRanges[].currency", url, now)
    else:
        prov["price_min"] = _unknown(url, now)
        prov["price_max"] = _unknown(url, now)
        prov["currency"] = _unknown(url, now)
    # Price basis is usually UNKNOWN (providers rarely say per-ticket vs total),
    # which keeps budget at "needs verification". A few fixtures carry a VERIFIED
    # basis so the budget constraint can actually PASS or FAIL in the demo.
    prov["price_basis"] = _verified(price_basis, "priceRanges[].type", url, now) if price_basis else _unknown(url, now)
    prov["age_min"] = _verified(age_min, "ageRestrictions.minimumAge", url, now) if age_min is not None else _unknown(url, now)
    prov["age_max"] = _unknown(url, now)
    cand.provenance = prov
    return cand


def demo_candidates(now: Optional[datetime] = None) -> List[DiscoveryCandidate]:
    now = now or _utcnow()
    return [
        _candidate(now, cid="ticketmaster:TM-SCI", provider="ticketmaster",
                   title="Family Science Night", url="https://example.com/tm/TM-SCI",
                   category="Science", lat=47.6190, lng=-122.3500,
                   location_name="Pacific Science Center",
                   description="Hands-on experiments and a planetarium show for all ages.",
                   start_offset_days=2, price_min=Decimal("20.00"), price_max=Decimal("45.00")),
        _candidate(now, cid="google_places:GP-SAM", provider="google_places",
                   title="Seattle Art Museum", url="https://example.com/gp/GP-SAM",
                   category="Museum", lat=47.6070, lng=-122.3380,
                   location_name="1300 1st Ave, Seattle",
                   description="Downtown art museum with rotating family-friendly exhibits."),
        _candidate(now, cid="google_places:GP-ZOO", provider="google_places",
                   title="Woodland Park Zoo", url="https://example.com/gp/GP-ZOO",
                   category="Zoo", lat=47.6685, lng=-122.3540,
                   location_name="5500 Phinney Ave N, Seattle",
                   description="Outdoor zoo with educational keeper talks.", age_min=0),
        _candidate(now, cid="google_places:GP-AQUA", provider="google_places",
                   title="Seattle Aquarium", url="https://example.com/gp/GP-AQUA",
                   category="Aquarium", lat=47.6073, lng=-122.3430,
                   location_name="1483 Alaskan Way, Seattle",
                   description="Touch pools and a window on the Salish Sea; educational and kid-friendly.",
                   age_min=0),
        _candidate(now, cid="google_places:GP-PARK", provider="google_places",
                   title="Discovery Park Trails", url="https://example.com/gp/GP-PARK",
                   category="Park", lat=47.6580, lng=-122.4170,
                   location_name="3801 Discovery Park Blvd, Seattle",
                   description="Miles of free coastal trails, beach, and nature walks."),
        _candidate(now, cid="ticketmaster:TM-SYM", provider="ticketmaster",
                   title="Family Symphony Matinee", url="https://example.com/tm/TM-SYM",
                   category="Music", lat=47.6075, lng=-122.3390,
                   location_name="Benaroya Hall",
                   description="A one-hour orchestral program designed for families.",
                   start_offset_days=5, price_min=Decimal("15.00"), price_max=Decimal("60.00"),
                   price_basis="per_ticket"),
        _candidate(now, cid="ticketmaster:TM-THEATER", provider="ticketmaster",
                   title="Children's Theater: Dragon Tales", url="https://example.com/tm/TM-THEATER",
                   category="Theatre", lat=47.6240, lng=-122.3560,
                   location_name="Seattle Children's Theatre",
                   description="A playful stage adventure recommended for ages four and up.",
                   start_offset_days=6, price_min=Decimal("18.00"), price_max=Decimal("30.00"),
                   price_basis="per_ticket", age_min=4),
        _candidate(now, cid="ticketmaster:TM-COM", provider="ticketmaster",
                   title="Late Night Comedy (18+)", url="https://example.com/tm/TM-COM",
                   category="Comedy", lat=47.6130, lng=-122.3470,
                   location_name="The Underground Club",
                   description="After-hours stand-up. Adults only.",
                   start_offset_days=3, price_min=Decimal("30.00"), price_max=Decimal("30.00"),
                   age_min=18),
        _candidate(now, cid="ticketmaster:TM-VIP", provider="ticketmaster",
                   title="VIP Chef's Table Experience", url="https://example.com/tm/TM-VIP",
                   category="Food", lat=47.6100, lng=-122.3400,
                   location_name="Harbor Steps",
                   description="A premium multi-course tasting with the head chef.",
                   start_offset_days=7, price_min=Decimal("150.00"), price_max=Decimal("150.00"),
                   price_basis="per_person", age_min=16),
    ]


class FixtureProvider:
    """Offline provider returning a curated demo pool (no network, no keys)."""

    name = "fixture"

    def __init__(self, *, clock=None) -> None:
        self._clock = clock or _utcnow

    async def search(self, request: DiscoveryRequest) -> List[DiscoveryCandidate]:
        return demo_candidates(self._clock())
