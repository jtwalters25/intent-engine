"""Single-page Ticketmaster Discovery retrieval with structured evidence."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

from .base import BaseProvider, ProviderResponseError


def required_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("required provider text is missing")
    return value.strip()


def source_url(value: Any) -> str:
    value = required_text(value)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid source URL")
    return value


class TicketmasterProvider(BaseProvider):
    name = "ticketmaster"
    env_key = "TICKETMASTER_API_KEY"

    def _build_request(self, request):
        params = {"apikey": self._require_key(), "keyword": request.query, "size": self._max_results}
        if request.has_precise_location:
            params["latlong"] = f"{request.latitude},{request.longitude}"
        elif request.location:
            # Preserve the user's location as keyword text rather than guess a city.
            params["keyword"] += " " + request.location
        if request.start_date:
            params["localStartDateTime"] = f"{request.start_date.isoformat()}T00:00:00,*"
        if request.end_date:
            start = request.start_date.isoformat() + "T00:00:00" if request.start_date else "*"
            params["localStartDateTime"] = f"{start},{request.end_date.isoformat()}T23:59:59"
        return "https://app.ticketmaster.com/discovery/v2/events.json", params

    def _parse(self, payload, request, retrieved_at):
        if not isinstance(payload, dict):
            raise ProviderResponseError("ticketmaster: malformed response body")
        if "fault" in payload or "errors" in payload:
            raise ProviderResponseError("ticketmaster: provider rejected request")
        embedded = payload.get("_embedded", {})
        if not isinstance(embedded, dict):
            raise ProviderResponseError("ticketmaster: malformed embedded results")
        return self._safe_items(embedded.get("events", []), lambda item: self._item(item, retrieved_at))

    def _item(self, item, retrieved_at):
        from intent_engine.discover.schemas import DiscoveryCandidate

        provider_id = required_text(item.get("id"))
        url = source_url(item.get("url"))
        venues = item.get("_embedded", {}).get("venues", [])
        venue = venues[0] if venues else {}
        location = venue.get("location", {})
        classifications = item.get("classifications", [])
        classification = classifications[0] if classifications else {}
        start = item.get("dates", {}).get("start", {})
        end = item.get("dates", {}).get("end", {})
        values = {
            "title": required_text(item.get("name")),
            "category": classification.get("genre", {}).get("name"),
            "location_name": venue.get("name"),
            "latitude": location.get("latitude"), "longitude": location.get("longitude"),
            "start_time": None, "end_time": None,
            "price_min": None, "price_max": None, "currency": None,
            "age_min": None, "age_max": None,
        }
        for name, dates in (("start_time", start), ("end_time", end)):
            if dates.get("dateTime") and not dates.get("dateTBD") and not dates.get("dateTBA") and not dates.get("timeTBA") and not dates.get("noSpecificTime"):
                parsed = datetime.fromisoformat(dates["dateTime"].replace("Z", "+00:00"))
                if parsed.utcoffset() is not None:
                    values[name] = parsed
        ranges = item.get("priceRanges", [])
        if ranges:
            currencies = {entry.get("currency") for entry in ranges}
            if len(currencies) == 1 and None not in currencies:
                values["currency"] = next(iter(currencies))
                mins = [Decimal(str(entry["min"])) for entry in ranges if entry.get("min") is not None]
                maxs = [Decimal(str(entry["max"])) for entry in ranges if entry.get("max") is not None]
                values["price_min"] = min(mins) if mins else None
                values["price_max"] = max(maxs) if maxs else None
        fields = {
            "title": "name", "category": "classifications[0].genre.name",
            "location_name": "_embedded.venues[0].name",
            "latitude": "_embedded.venues[0].location.latitude",
            "longitude": "_embedded.venues[0].location.longitude",
            "start_time": "dates.start.dateTime", "end_time": "dates.end.dateTime",
            "price_min": "priceRanges[].min", "price_max": "priceRanges[].max", "currency": "priceRanges[].currency",
        }
        # Validate/coerce structured scalar values before recording matching evidence.
        candidate = DiscoveryCandidate(
            candidate_id=self._candidate_id(provider_id), provider=self.name,
            provider_id=provider_id, source_url=url, retrieved_at=retrieved_at,
            description=item.get("info"), **values,
        )
        values = {key: getattr(candidate, key) for key in values}
        candidate.provenance = self._evidence(values, fields, source_url=url, retrieved_at=retrieved_at)
        if candidate.description is not None:
            candidate.provenance["description"] = self._extracted(candidate.description, extractor="ticketmaster-text-pass-through-v1", source_url=url, retrieved_at=retrieved_at)
        else:
            candidate.provenance.update(self._evidence({"description": None}, {}, source_url=url, retrieved_at=retrieved_at))
        candidate.provenance.update(self._evidence({"availability": None, "price_basis": None, "duration_minutes": None}, {}, source_url=url, retrieved_at=retrieved_at))
        return candidate
