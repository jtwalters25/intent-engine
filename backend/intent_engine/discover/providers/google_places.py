"""Google Places Text Search (Legacy); no inferred dollar prices or age policy.

Legacy eligibility and Places attribution/storage terms must be reviewed before
live rollout. One search page is requested; no implicit details/pagination calls.
"""

from .base import BaseProvider, ProviderConfigError, ProviderRateLimited, ProviderResponseError
from .ticketmaster import required_text


class GooglePlacesProvider(BaseProvider):
    name = "google_places"
    env_key = "GOOGLE_PLACES_API_KEY"

    def _build_request(self, request):
        params = {"key": self._require_key(), "query": request.query}
        if request.location:
            params["query"] += " " + request.location
        if request.has_precise_location:
            params["location"] = f"{request.latitude},{request.longitude}"
            params["radius"] = 10000
        return "https://maps.googleapis.com/maps/api/place/textsearch/json", params

    def _parse(self, payload, request, retrieved_at):
        if not isinstance(payload, dict):
            raise ProviderResponseError("google_places: malformed response body")
        status = payload.get("status")
        if status == "ZERO_RESULTS":
            return []
        if status == "OVER_QUERY_LIMIT":
            raise ProviderRateLimited("google_places: quota exceeded")
        if status == "REQUEST_DENIED":
            raise ProviderConfigError("google_places: request denied; check server configuration")
        if status != "OK":
            raise ProviderResponseError("google_places: provider response failed")
        return self._safe_items(payload.get("results"), lambda item: self._item(item, retrieved_at))

    def _item(self, item, retrieved_at):
        from urllib.parse import urlencode
        from intent_engine.discover.schemas import DiscoveryCandidate

        provider_id = required_text(item.get("place_id"))
        url = "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": required_text(item.get("name")), "query_place_id": provider_id})
        location = item.get("geometry", {}).get("location", {})
        types = item.get("types", [])
        if not isinstance(types, list) or any(not isinstance(value, str) for value in types):
            raise ValueError("invalid place types")
        values = {
            "title": required_text(item.get("name")), "location_name": item.get("formatted_address"),
            "latitude": location.get("lat"), "longitude": location.get("lng"),
            "category": types[0] if types else None,
            "description": None, "start_time": None, "end_time": None,
            "price_min": None, "price_max": None, "currency": None,
            "age_min": None, "age_max": None,
        }
        candidate = DiscoveryCandidate(
            candidate_id=self._candidate_id(provider_id), provider=self.name,
            provider_id=provider_id, source_url=url, retrieved_at=retrieved_at,
            attributes={key: item[key] for key in ("price_level", "html_attributions", "business_status") if key in item},
            **values,
        )
        fields = {"title": "name", "location_name": "formatted_address", "latitude": "geometry.location.lat", "longitude": "geometry.location.lng", "category": "types[0]"}
        candidate.provenance = self._evidence({key: getattr(candidate, key) for key in values}, fields, source_url=url, retrieved_at=retrieved_at)
        candidate.provenance.update(self._evidence({"availability": None, "price_basis": None, "duration_minutes": None}, {}, source_url=url, retrieved_at=retrieved_at))
        return candidate
