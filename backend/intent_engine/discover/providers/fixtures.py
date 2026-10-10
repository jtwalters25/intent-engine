"""Fixture provider for demos and offline runs (no API keys, no network).

Returns a large, varied candidate pool (~63 activities across many scenarios)
with the same provenance discipline as the real adapters — structured facts are
VERIFIED, honest unknowns stay UNKNOWN, descriptions are EXTRACTED — so the full
pipeline (constraints, ranking, explanations) behaves exactly as on live data.
Selected via ``DISCOVER_DEMO_MODE`` (see ``config.py``); never a silent default
in production.

``FixtureProvider.search`` is query-aware: it keyword-matches the request against
each candidate's title/category/description/tags (mimicking a real provider
search), so different goals surface different, relevant results. The pool spans:
- categories: science, museum, zoo, aquarium, park, hike, music, theatre, dance,
  comedy, sports, food, class, market, nightlife, attraction, film, …;
- price states: no price (unknown), verified range with unknown basis
  (→ budget "needs verification"), and verified per-ticket/per-person basis
  (→ budget can PASS or FAIL);
- age gates: none, 0, 3+, 4+, 6+, 10+, 12+, 16+, 18+, 21+;
- timing: dated events vs undated places.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from intent_engine.discover.schemas import (
    AttributeProvenance,
    DiscoveryCandidate,
    DiscoveryRequest,
    EvidenceStatus,
)

_TOKEN = re.compile(r"[a-z0-9]+")
_DEFAULT_LIMIT = 20
_FALLBACK_LIMIT = 12


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
    tags: Optional[List[str]] = None,
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
        attributes={"demo": True, "tags": list(tags or [])},
    )
    prov: Dict[str, AttributeProvenance] = {
        "title": _verified(title, "name", url, now),
        "category": _verified(category, "classification", url, now),
        "location_name": _verified(location_name, "venue.name", url, now),
        "latitude": _verified(lat, "venue.location.latitude", url, now),
        "longitude": _verified(lng, "venue.location.longitude", url, now),
        "description": _extracted(description, url, now),
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
    prov["price_basis"] = _verified(price_basis, "priceRanges[].type", url, now) if price_basis else _unknown(url, now)
    prov["age_min"] = _verified(age_min, "ageRestrictions.minimumAge", url, now) if age_min is not None else _unknown(url, now)
    prov["age_max"] = _unknown(url, now)
    cand.provenance = prov
    return cand


def _d(value: str) -> Decimal:
    return Decimal(value)


# Compact pool spec. Keys: id, prov, title, cat, loc, lat, lng, desc, tags,
# and optional days / pmin / pmax / basis / age.
_POOL: List[dict] = [
    # --- Family / educational (indoor) ---
    {"id": "GP-SAM", "prov": "google_places", "title": "Seattle Art Museum", "cat": "Museum", "loc": "1300 1st Ave", "lat": 47.6070, "lng": -122.3380, "desc": "Downtown art museum with rotating family-friendly exhibits.", "tags": ["museum", "art", "family", "kids", "indoor", "educational"]},
    {"id": "GP-ZOO", "prov": "google_places", "title": "Woodland Park Zoo", "cat": "Zoo", "loc": "5500 Phinney Ave N", "lat": 47.6685, "lng": -122.3540, "desc": "Outdoor zoo with educational keeper talks.", "tags": ["zoo", "animals", "family", "kids", "educational", "outdoor"], "age": 0},
    {"id": "GP-AQUA", "prov": "google_places", "title": "Seattle Aquarium", "cat": "Aquarium", "loc": "1483 Alaskan Way", "lat": 47.6073, "lng": -122.3430, "desc": "Touch pools and a window on the Salish Sea; kid-friendly.", "tags": ["aquarium", "animals", "family", "kids", "educational", "indoor"], "age": 0},
    {"id": "GP-FLIGHT", "prov": "google_places", "title": "Museum of Flight", "cat": "Museum", "loc": "9404 E Marginal Way S", "lat": 47.5180, "lng": -122.2960, "desc": "Aircraft, a space gallery, and flight simulators.", "tags": ["museum", "aviation", "space", "family", "kids", "educational", "stem"]},
    {"id": "TM-SCI", "prov": "ticketmaster", "title": "Family Science Night", "cat": "Science", "loc": "Pacific Science Center", "lat": 47.6190, "lng": -122.3500, "desc": "Hands-on experiments and a planetarium show for all ages.", "tags": ["science", "stem", "family", "kids", "educational", "planetarium"], "days": 2, "pmin": _d("20.00"), "pmax": _d("45.00")},
    {"id": "EB-STORY", "prov": "eventbrite", "title": "Central Library Story Time", "cat": "Library", "loc": "1000 4th Ave", "lat": 47.6065, "lng": -122.3325, "desc": "Free early-reader story hour.", "tags": ["library", "books", "kids", "family", "free", "educational", "toddler"], "days": 1},
    {"id": "GP-CHILDMUS", "prov": "google_places", "title": "Seattle Children's Museum", "cat": "Museum", "loc": "305 Harrison St", "lat": 47.6200, "lng": -122.3530, "desc": "Play-based exhibits for little ones.", "tags": ["museum", "kids", "family", "toddler", "indoor", "play"]},
    {"id": "EB-STARPARTY", "prov": "eventbrite", "title": "Observatory Star Party", "cat": "Science", "loc": "Green Lake", "lat": 47.6800, "lng": -122.3270, "desc": "Free evening telescope viewing with astronomers.", "tags": ["science", "astronomy", "stars", "family", "free", "educational", "evening"], "days": 4},

    # --- Outdoor / active ---
    {"id": "GP-DISCPARK", "prov": "google_places", "title": "Discovery Park Trails", "cat": "Park", "loc": "3801 Discovery Park Blvd", "lat": 47.6580, "lng": -122.4170, "desc": "Miles of free coastal trails, beach, and nature walks.", "tags": ["park", "hike", "outdoor", "nature", "free", "family", "beach"]},
    {"id": "GP-ALKI", "prov": "google_places", "title": "Alki Beach", "cat": "Beach", "loc": "Alki Ave SW", "lat": 47.5760, "lng": -122.4090, "desc": "Sandy beach with skyline views.", "tags": ["beach", "outdoor", "free", "family", "walk", "nature"]},
    {"id": "EB-KAYAK", "prov": "eventbrite", "title": "Kayak Rental on Lake Union", "cat": "Outdoor", "loc": "2100 Westlake Ave N", "lat": 47.6370, "lng": -122.3380, "desc": "Guided paddle on the lake.", "tags": ["kayak", "outdoor", "water", "active", "adventure"], "days": 3, "pmin": _d("35.00"), "pmax": _d("35.00"), "basis": "per_person", "age": 8},
    {"id": "GP-GREENLAKE", "prov": "google_places", "title": "Green Lake Loop", "cat": "Park", "loc": "7201 E Green Lake Dr N", "lat": 47.6800, "lng": -122.3280, "desc": "Flat 3-mile loop for walking and biking.", "tags": ["park", "walk", "bike", "outdoor", "free", "family"]},
    {"id": "EB-HIKE", "prov": "eventbrite", "title": "Mount Si Guided Hike", "cat": "Outdoor", "loc": "North Bend", "lat": 47.4880, "lng": -121.7230, "desc": "Strenuous guided day hike.", "tags": ["hike", "outdoor", "nature", "active", "adventure"], "days": 6, "pmin": _d("15.00"), "pmax": _d("15.00"), "basis": "per_person", "age": 12},
    {"id": "GP-GARDEN", "prov": "google_places", "title": "Washington Park Arboretum", "cat": "Garden", "loc": "2300 Arboretum Dr E", "lat": 47.6390, "lng": -122.2940, "desc": "Botanical garden trails.", "tags": ["garden", "nature", "park", "outdoor", "walk", "family"]},
    {"id": "EB-CLIMB", "prov": "eventbrite", "title": "Rock Climbing Gym Day Pass", "cat": "Sports", "loc": "900 Poplar Pl S", "lat": 47.5920, "lng": -122.3160, "desc": "Indoor bouldering and top-rope.", "tags": ["climbing", "sports", "active", "indoor", "adventure"], "pmin": _d("25.00"), "pmax": _d("25.00"), "basis": "per_person", "age": 5},
    {"id": "EB-SUP", "prov": "eventbrite", "title": "Stand-Up Paddleboard Lesson", "cat": "Outdoor", "loc": "Lake Washington", "lat": 47.6100, "lng": -122.2600, "desc": "Beginner SUP lesson.", "tags": ["paddleboard", "water", "outdoor", "active", "adventure"], "days": 5, "pmin": _d("45.00"), "pmax": _d("45.00"), "basis": "per_person", "age": 10},

    # --- Live music / concerts ---
    {"id": "TM-SYM", "prov": "ticketmaster", "title": "Family Symphony Matinee", "cat": "Music", "loc": "Benaroya Hall", "lat": 47.6075, "lng": -122.3390, "desc": "A one-hour orchestral program for families.", "tags": ["music", "symphony", "orchestra", "family", "kids", "concert"], "days": 5, "pmin": _d("15.00"), "pmax": _d("60.00"), "basis": "per_ticket"},
    {"id": "TM-INDIE", "prov": "ticketmaster", "title": "Indie Rock Show", "cat": "Music", "loc": "The Showbox", "lat": 47.6085, "lng": -122.3400, "desc": "Touring indie headliner.", "tags": ["music", "rock", "concert", "nightlife", "live"], "days": 7, "pmin": _d("35.00"), "pmax": _d("75.00"), "basis": "per_ticket", "age": 21},
    {"id": "TM-JAZZ", "prov": "ticketmaster", "title": "Jazz Night", "cat": "Music", "loc": "Dimitriou's Jazz Alley", "lat": 47.6150, "lng": -122.3410, "desc": "Intimate live jazz.", "tags": ["music", "jazz", "concert", "live", "evening"], "days": 2, "pmin": _d("30.00"), "pmax": _d("55.00"), "basis": "per_ticket"},
    {"id": "TM-KIDSING", "prov": "ticketmaster", "title": "Kids' Sing-Along Concert", "cat": "Music", "loc": "Moore Theatre", "lat": 47.6130, "lng": -122.3410, "desc": "Interactive concert for little ones.", "tags": ["music", "kids", "family", "concert", "singalong", "toddler"], "days": 8, "pmin": _d("18.00"), "pmax": _d("30.00"), "basis": "per_ticket"},
    {"id": "EB-OUTCON", "prov": "eventbrite", "title": "Outdoor Summer Concert", "cat": "Music", "loc": "Gas Works Park", "lat": 47.6456, "lng": -122.3344, "desc": "Free lawn concert at sunset.", "tags": ["music", "concert", "outdoor", "free", "family", "festival"], "days": 10},
    {"id": "TM-OPERA", "prov": "ticketmaster", "title": "Opera Gala", "cat": "Music", "loc": "McCaw Hall", "lat": 47.6240, "lng": -122.3490, "desc": "A grand opera evening.", "tags": ["music", "opera", "concert", "formal", "evening"], "days": 9, "pmin": _d("60.00"), "pmax": _d("220.00"), "basis": "per_ticket"},
    {"id": "TM-HIPHOP", "prov": "ticketmaster", "title": "Hip-Hop Festival", "cat": "Music", "loc": "WaMu Theater", "lat": 47.5950, "lng": -122.3320, "desc": "Multi-artist hip-hop lineup.", "tags": ["music", "hiphop", "festival", "concert", "nightlife"], "days": 11, "pmin": _d("49.00"), "pmax": _d("120.00"), "basis": "per_ticket", "age": 18},
    {"id": "TM-COUNTRY", "prov": "ticketmaster", "title": "Country Music Concert", "cat": "Music", "loc": "Climate Pledge Arena", "lat": 47.6221, "lng": -122.3540, "desc": "An arena country tour.", "tags": ["music", "country", "concert", "arena", "live"], "days": 13, "pmin": _d("45.00"), "pmax": _d("150.00"), "basis": "per_ticket"},

    # --- Theatre / arts ---
    {"id": "TM-THEATER", "prov": "ticketmaster", "title": "Children's Theater: Dragon Tales", "cat": "Theatre", "loc": "Seattle Children's Theatre", "lat": 47.6240, "lng": -122.3560, "desc": "A playful stage adventure recommended for ages four and up.", "tags": ["theatre", "kids", "family", "play", "stage"], "days": 6, "pmin": _d("18.00"), "pmax": _d("30.00"), "basis": "per_ticket", "age": 4},
    {"id": "TM-BROADWAY", "prov": "ticketmaster", "title": "Broadway Touring Musical", "cat": "Theatre", "loc": "Paramount Theatre", "lat": 47.6130, "lng": -122.3320, "desc": "A hit musical on tour.", "tags": ["theatre", "musical", "broadway", "stage", "evening"], "days": 12, "pmin": _d("59.00"), "pmax": _d("180.00"), "basis": "per_ticket"},
    {"id": "EB-IMPROV", "prov": "eventbrite", "title": "Improv Comedy Night", "cat": "Comedy", "loc": "Unexpected Productions", "lat": 47.6090, "lng": -122.3420, "desc": "Audience-driven improv.", "tags": ["comedy", "improv", "theatre", "nightlife", "live"], "days": 3, "pmin": _d("20.00"), "pmax": _d("20.00"), "basis": "per_ticket"},
    {"id": "EB-SHAKES", "prov": "eventbrite", "title": "Shakespeare in the Park", "cat": "Theatre", "loc": "Volunteer Park", "lat": 47.6300, "lng": -122.3150, "desc": "Free outdoor Shakespeare.", "tags": ["theatre", "shakespeare", "outdoor", "free", "family", "classic"], "days": 9},
    {"id": "GP-GALLERY", "prov": "google_places", "title": "Pioneer Square Art Gallery", "cat": "Art", "loc": "110 S Washington St", "lat": 47.6010, "lng": -122.3330, "desc": "Rotating contemporary exhibits; free opening.", "tags": ["art", "gallery", "free", "culture", "indoor"]},
    {"id": "TM-NUT", "prov": "ticketmaster", "title": "Ballet: The Nutcracker", "cat": "Dance", "loc": "McCaw Hall", "lat": 47.6240, "lng": -122.3490, "desc": "The holiday ballet classic.", "tags": ["dance", "ballet", "theatre", "family", "holiday", "seasonal"], "days": 14, "pmin": _d("40.00"), "pmax": _d("160.00"), "basis": "per_ticket"},
    {"id": "EB-PUPPET", "prov": "eventbrite", "title": "Puppet Show", "cat": "Theatre", "loc": "Northwest Puppet Center", "lat": 47.7000, "lng": -122.3200, "desc": "A marionette fairy tale.", "tags": ["theatre", "puppet", "kids", "family", "toddler"], "days": 4, "pmin": _d("12.00"), "pmax": _d("18.00"), "basis": "per_ticket"},
    {"id": "TM-MAGIC", "prov": "ticketmaster", "title": "Magic Show", "cat": "Family", "loc": "The Triple Door", "lat": 47.6085, "lng": -122.3380, "desc": "Close-up magic and illusions.", "tags": ["magic", "family", "kids", "show", "entertainment"], "days": 7, "pmin": _d("25.00"), "pmax": _d("40.00"), "basis": "per_ticket"},

    # --- Sports ---
    {"id": "TM-MARINERS", "prov": "ticketmaster", "title": "Mariners Baseball Game", "cat": "Sports", "loc": "T-Mobile Park", "lat": 47.5914, "lng": -122.3325, "desc": "An MLB home game.", "tags": ["sports", "baseball", "family", "stadium", "outdoor"], "days": 5, "pmin": _d("18.00"), "pmax": _d("120.00"), "basis": "per_ticket"},
    {"id": "TM-SOUNDERS", "prov": "ticketmaster", "title": "Sounders Soccer Match", "cat": "Sports", "loc": "Lumen Field", "lat": 47.5952, "lng": -122.3316, "desc": "An MLS home match.", "tags": ["sports", "soccer", "family", "stadium", "outdoor"], "days": 8, "pmin": _d("29.00"), "pmax": _d("140.00"), "basis": "per_ticket"},
    {"id": "TM-STORM", "prov": "ticketmaster", "title": "Storm Basketball Game", "cat": "Sports", "loc": "Climate Pledge Arena", "lat": 47.6221, "lng": -122.3540, "desc": "A WNBA home game.", "tags": ["sports", "basketball", "family", "arena"], "days": 6, "pmin": _d("20.00"), "pmax": _d("110.00"), "basis": "per_ticket"},
    {"id": "TM-MINORS", "prov": "ticketmaster", "title": "Minor League Baseball", "cat": "Sports", "loc": "Cheney Stadium", "lat": 47.2370, "lng": -122.4950, "desc": "An affordable family ballgame.", "tags": ["sports", "baseball", "family", "cheap", "outdoor"], "days": 4, "pmin": _d("10.00"), "pmax": _d("28.00"), "basis": "per_ticket"},
    {"id": "GP-SKATE", "prov": "google_places", "title": "Public Ice Skating Session", "cat": "Sports", "loc": "Kraken Community Iceplex", "lat": 47.6960, "lng": -122.3380, "desc": "Open skate for all ages.", "tags": ["sports", "skating", "ice", "family", "kids", "indoor"]},
    {"id": "EB-MARATHON", "prov": "eventbrite", "title": "Marathon Spectator Fest", "cat": "Sports", "loc": "Downtown", "lat": 47.6080, "lng": -122.3350, "desc": "Free cheer stations along the route.", "tags": ["sports", "running", "marathon", "free", "outdoor", "family"], "days": 10},
    {"id": "TM-HOCKEY", "prov": "ticketmaster", "title": "Kraken Hockey Game", "cat": "Sports", "loc": "Climate Pledge Arena", "lat": 47.6221, "lng": -122.3540, "desc": "An NHL home game.", "tags": ["sports", "hockey", "arena", "family"], "days": 9, "pmin": _d("39.00"), "pmax": _d("200.00"), "basis": "per_ticket"},

    # --- Food / experiences ---
    {"id": "TM-VIP", "prov": "ticketmaster", "title": "VIP Chef's Table Experience", "cat": "Food", "loc": "Harbor Steps", "lat": 47.6100, "lng": -122.3400, "desc": "A premium multi-course tasting dinner with the head chef.", "tags": ["food", "dinner", "tasting", "fine", "premium", "experience"], "days": 7, "pmin": _d("150.00"), "pmax": _d("150.00"), "basis": "per_person", "age": 16},
    {"id": "EB-FOODTOUR", "prov": "eventbrite", "title": "Pike Place Food Tour", "cat": "Food", "loc": "85 Pike St", "lat": 47.6097, "lng": -122.3420, "desc": "A guided market tasting walk.", "tags": ["food", "tour", "market", "tasting", "walk", "family"], "days": 2, "pmin": _d("59.00"), "pmax": _d("59.00"), "basis": "per_person", "age": 6},
    {"id": "EB-COOKPASTA", "prov": "eventbrite", "title": "Cooking Class: Fresh Pasta", "cat": "Class", "loc": "1531 Melrose Ave", "lat": 47.6150, "lng": -122.3270, "desc": "A hands-on pasta-making class.", "tags": ["food", "cooking", "class", "workshop", "handson"], "days": 5, "pmin": _d("85.00"), "pmax": _d("85.00"), "basis": "per_person", "age": 12},
    {"id": "EB-BREW", "prov": "eventbrite", "title": "Brewery Tour & Tasting", "cat": "Food", "loc": "Fremont", "lat": 47.6510, "lng": -122.3500, "desc": "A behind-the-scenes brewery tour.", "tags": ["food", "beer", "brewery", "tasting", "tour", "nightlife"], "days": 3, "pmin": _d("30.00"), "pmax": _d("30.00"), "basis": "per_person", "age": 21},
    {"id": "GP-MARKET", "prov": "google_places", "title": "Ballard Farmers Market", "cat": "Market", "loc": "Ballard Ave NW", "lat": 47.6680, "lng": -122.3840, "desc": "A free open-air market.", "tags": ["food", "market", "free", "family", "outdoor", "local"]},
    {"id": "EB-WINE", "prov": "eventbrite", "title": "Wine Tasting Flight", "cat": "Food", "loc": "Woodinville", "lat": 47.7540, "lng": -122.1600, "desc": "A guided flight of local wines.", "tags": ["food", "wine", "tasting", "nightlife"], "days": 6, "pmin": _d("40.00"), "pmax": _d("40.00"), "basis": "per_person", "age": 21},
    {"id": "EB-DUMPLING", "prov": "eventbrite", "title": "Dumpling-Making Workshop", "cat": "Class", "loc": "Chinatown-ID", "lat": 47.5980, "lng": -122.3270, "desc": "A family-friendly dumpling class.", "tags": ["food", "cooking", "class", "family", "kids", "handson"], "days": 8, "pmin": _d("45.00"), "pmax": _d("45.00"), "basis": "per_person", "age": 6},
    {"id": "EB-CHOCO", "prov": "eventbrite", "title": "Chocolate Factory Tour", "cat": "Food", "loc": "Georgetown", "lat": 47.5460, "lng": -122.3200, "desc": "A bean-to-bar tour with samples.", "tags": ["food", "chocolate", "tour", "family", "kids"], "days": 4, "pmin": _d("22.00"), "pmax": _d("22.00"), "basis": "per_person"},
    {"id": "EB-RAMEN", "prov": "eventbrite", "title": "Ramen Pop-Up", "cat": "Food", "loc": "South Lake Union", "lat": 47.6250, "lng": -122.3370, "desc": "A limited-run ramen night.", "tags": ["food", "ramen", "popup", "dinner", "casual"], "days": 3, "pmin": _d("18.00"), "pmax": _d("18.00"), "basis": "per_person"},

    # --- Nightlife / adult / seasonal / misc ---
    {"id": "TM-COM", "prov": "ticketmaster", "title": "Late Night Comedy (18+)", "cat": "Comedy", "loc": "The Underground Club", "lat": 47.6130, "lng": -122.3470, "desc": "After-hours stand-up. Adults only.", "tags": ["comedy", "standup", "nightlife", "adults"], "days": 3, "pmin": _d("30.00"), "pmax": _d("30.00"), "age": 18},
    {"id": "TM-CLUB", "prov": "ticketmaster", "title": "Dance Club Night", "cat": "Nightlife", "loc": "Q Nightclub", "lat": 47.6190, "lng": -122.3210, "desc": "DJ sets till late.", "tags": ["nightlife", "dance", "club", "dj", "music"], "days": 7, "pmin": _d("25.00"), "pmax": _d("40.00"), "basis": "per_ticket", "age": 21},
    {"id": "GP-TRIVIA", "prov": "google_places", "title": "Trivia Night at the Pub", "cat": "Nightlife", "loc": "Capitol Hill", "lat": 47.6230, "lng": -122.3210, "desc": "A free weekly pub quiz.", "tags": ["nightlife", "trivia", "pub", "free", "social"], "days": 1, "age": 21},
    {"id": "EB-HOLIDAY", "prov": "eventbrite", "title": "Holiday Market", "cat": "Market", "loc": "Seattle Center", "lat": 47.6210, "lng": -122.3490, "desc": "Seasonal crafts and treats.", "tags": ["market", "holiday", "seasonal", "free", "family", "shopping"], "days": 11},
    {"id": "TM-NYE", "prov": "ticketmaster", "title": "New Year's Eve Gala", "cat": "Food", "loc": "Downtown Hotel", "lat": 47.6100, "lng": -122.3340, "desc": "A black-tie dinner and countdown.", "tags": ["food", "gala", "nightlife", "formal", "seasonal"], "days": 14, "pmin": _d("195.00"), "pmax": _d("195.00"), "basis": "per_person", "age": 21},
    {"id": "TM-HAUNT", "prov": "ticketmaster", "title": "Haunted House", "cat": "Attraction", "loc": "Georgetown", "lat": 47.5460, "lng": -122.3210, "desc": "A seasonal scare attraction.", "tags": ["attraction", "haunted", "seasonal", "thrill", "halloween"], "days": 9, "pmin": _d("28.00"), "pmax": _d("28.00"), "basis": "per_ticket", "age": 12},
    {"id": "EB-ESCAPE", "prov": "eventbrite", "title": "Escape Room Challenge", "cat": "Attraction", "loc": "Downtown", "lat": 47.6110, "lng": -122.3360, "desc": "A 60-minute puzzle room for groups.", "tags": ["attraction", "puzzle", "escape", "family", "group", "indoor"], "days": 2, "pmin": _d("32.00"), "pmax": _d("32.00"), "basis": "per_person", "age": 10},
    {"id": "EB-ROOFMOVIE", "prov": "eventbrite", "title": "Rooftop Movie Night", "cat": "Film", "loc": "Downtown Rooftop", "lat": 47.6120, "lng": -122.3380, "desc": "A classic film under the stars.", "tags": ["film", "movie", "outdoor", "evening", "date"], "days": 6, "pmin": _d("20.00"), "pmax": _d("20.00"), "basis": "per_ticket"},
    {"id": "TM-SILENT", "prov": "ticketmaster", "title": "Silent Disco", "cat": "Music", "loc": "Fremont", "lat": 47.6510, "lng": -122.3490, "desc": "A headphone dance party.", "tags": ["music", "dance", "nightlife", "silentdisco"], "days": 8, "pmin": _d("22.00"), "pmax": _d("22.00"), "basis": "per_ticket", "age": 18},
    {"id": "EB-OPENMIC", "prov": "eventbrite", "title": "Comedy Open Mic", "cat": "Comedy", "loc": "Ballard", "lat": 47.6680, "lng": -122.3830, "desc": "A free local comedy showcase.", "tags": ["comedy", "standup", "free", "nightlife", "local"], "days": 2},
    {"id": "GP-CONSERV", "prov": "google_places", "title": "Volunteer Park Conservatory", "cat": "Garden", "loc": "1400 E Galer St", "lat": 47.6300, "lng": -122.3150, "desc": "A Victorian glasshouse of exotic plants.", "tags": ["garden", "nature", "indoor", "family", "plants"]},
    {"id": "TM-CIRCUS", "prov": "ticketmaster", "title": "Family Circus", "cat": "Family", "loc": "Marymoor Park", "lat": 47.6580, "lng": -122.1180, "desc": "Big-top acrobatics and clowns.", "tags": ["circus", "family", "kids", "show", "outdoor"], "days": 10, "pmin": _d("25.00"), "pmax": _d("65.00"), "basis": "per_ticket"},
    {"id": "EB-CRAFT", "prov": "eventbrite", "title": "Kids' Craft Workshop", "cat": "Class", "loc": "Fremont", "lat": 47.6510, "lng": -122.3505, "desc": "A drop-in art and craft session.", "tags": ["class", "craft", "kids", "family", "art", "handson"], "days": 4, "pmin": _d("15.00"), "pmax": _d("15.00"), "basis": "per_person", "age": 3},
]


def _build(now: datetime, spec: dict) -> DiscoveryCandidate:
    prov = spec["prov"]
    return _candidate(
        now, cid=f"{prov}:{spec['id']}", provider=prov, title=spec["title"],
        url=f"https://example.com/{prov}/{spec['id']}", category=spec["cat"],
        lat=spec["lat"], lng=spec["lng"], location_name=spec["loc"], description=spec["desc"],
        tags=spec["tags"], start_offset_days=spec.get("days"),
        price_min=spec.get("pmin"), price_max=spec.get("pmax"),
        price_basis=spec.get("basis"), age_min=spec.get("age"),
    )


def demo_candidates(now: Optional[datetime] = None) -> List[DiscoveryCandidate]:
    """The full demo pool (all scenarios), independent of any query."""
    now = now or _utcnow()
    return [_build(now, spec) for spec in _POOL]


class FixtureProvider:
    """Offline, query-aware provider over a curated demo pool (no network/keys)."""

    name = "fixture"

    def __init__(self, *, clock=None) -> None:
        self._clock = clock or _utcnow

    async def search(self, request: DiscoveryRequest) -> List[DiscoveryCandidate]:
        pool = demo_candidates(self._clock())
        terms = {t for t in _TOKEN.findall(request.query.lower()) if len(t) >= 3}
        if not terms:
            return pool[:_FALLBACK_LIMIT]
        scored = []
        for candidate in pool:
            tags = candidate.attributes.get("tags", [])
            text = " ".join([
                candidate.title, candidate.category or "",
                candidate.description or "", " ".join(tags),
            ]).lower()
            hits = len(terms & set(_TOKEN.findall(text)))
            if hits:
                scored.append((hits, candidate))
        if not scored:
            return pool[:_FALLBACK_LIMIT]
        scored.sort(key=lambda pair: (-pair[0], pair[1].candidate_id))
        return [candidate for _, candidate in scored][:_DEFAULT_LIMIT]
