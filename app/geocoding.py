from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "https://nominatim.openstreetmap.org/search"
DEFAULT_PLACE_HINT = "San Francisco, CA"
DEFAULT_VIEWBOX = "-122.53,37.83,-122.35,37.70"
DEFAULT_USER_AGENT = "Flemme local route planner"


class GeocodingError(RuntimeError):
    """Raised when an address cannot be resolved to a route point."""


class GeocodingLookupError(GeocodingError):
    """Raised when the geocoder returns no usable match."""


class GeocodingServiceError(GeocodingError):
    """Raised when the remote geocoding service cannot be reached."""


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    query: str
    lat: float
    lon: float
    display_name: str


@dataclass(frozen=True, slots=True)
class GeocodeSuggestion:
    place_id: str
    result: GeocodeResult


LOCAL_HINTS: tuple[tuple[tuple[str, ...], GeocodeResult], ...] = (
    (
        ("1227", "page"),
        GeocodeResult(
            query="1227 Page Street, San Francisco, CA",
            lat=37.7714654,
            lon=-122.4412496,
            display_name="1227 Page Street, San Francisco, CA",
        ),
    ),
    (
        ("1840", "haight"),
        GeocodeResult(
            query="1840 Haight Street, San Francisco, CA",
            lat=37.7695111,
            lon=-122.4526159,
            display_name="1840 Haight Street, San Francisco, CA",
        ),
    ),
    (
        ("ferry", "building"),
        GeocodeResult(
            query="Ferry Building, San Francisco, CA",
            lat=37.7955,
            lon=-122.3937,
            display_name="Ferry Building, San Francisco, CA",
        ),
    ),
    (
        ("ocean", "beach"),
        GeocodeResult(
            query="Ocean Beach, San Francisco, CA",
            lat=37.7697,
            lon=-122.5108,
            display_name="Ocean Beach, San Francisco, CA",
        ),
    ),
    (
        ("whole", "foods", "stanyan"),
        GeocodeResult(
            query="Whole Foods Market Haight Street, San Francisco, CA",
            lat=37.769562,
            lon=-122.452782,
            display_name="Whole Foods Market, 690 Stanyan Street, San Francisco, CA",
        ),
    ),
    (
        ("whole", "foods", "stayan"),
        GeocodeResult(
            query="Whole Foods Market Haight Street, San Francisco, CA",
            lat=37.769562,
            lon=-122.452782,
            display_name="Whole Foods Market, 690 Stanyan Street, San Francisco, CA",
        ),
    ),
    (
        ("whole", "foods", "haight"),
        GeocodeResult(
            query="Whole Foods Market Haight Street, San Francisco, CA",
            lat=37.769562,
            lon=-122.452782,
            display_name="Whole Foods Market, 690 Stanyan Street, San Francisco, CA",
        ),
    ),
    (
        ("duboce", "park", "cafe"),
        GeocodeResult(
            query="Duboce Park Cafe, San Francisco, CA",
            lat=37.7691622,
            lon=-122.4315697,
            display_name="Duboce Park Cafe, 2 Sanchez Street, San Francisco, CA",
        ),
    ),
    (
        ("page", "broderick"),
        GeocodeResult(
            query="Page Street and Broderick Street, San Francisco, CA",
            lat=37.7714654,
            lon=-122.4412496,
            display_name="Page Street and Broderick Street, San Francisco, CA",
        ),
    ),
    (
        ("duboce", "noe"),
        GeocodeResult(
            query="Duboce Avenue and Noe Street, San Francisco, CA",
            lat=37.76919,
            lon=-122.43357,
            display_name="Duboce Avenue and Noe Street, San Francisco, CA",
        ),
    ),
    (
        ("1737", "post"),
        GeocodeResult(
            query="1737 Post Street, San Francisco, CA",
            lat=37.785372647,
            lon=-122.431366397,
            display_name="1737 Post Street, San Francisco, CA",
        ),
    ),
    (
        ("post", "webster"),
        GeocodeResult(
            query="Post Street and Webster Street, San Francisco, CA",
            lat=37.785372647,
            lon=-122.431366397,
            display_name="Post Street and Webster Street, San Francisco, CA",
        ),
    ),
)


def _with_place_hint(address: str, place_hint: str) -> str:
    query = " ".join(address.strip().split())
    if not query:
        raise GeocodingLookupError("Address is required.")
    if place_hint and place_hint.casefold() not in query.casefold():
        return f"{query}, {place_hint}"
    return query


def _local_match(query: str) -> GeocodeResult | None:
    normalized = query.casefold()
    for terms, result in LOCAL_HINTS:
        if all(term in normalized for term in terms):
            return result
    return None


def _place_id(prefix: str, display_name: str) -> str:
    digest = sha256(display_name.casefold().encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _local_suggestions(query: str, limit: int) -> list[GeocodeSuggestion]:
    terms = [term for term in query.casefold().replace(",", " ").split() if len(term) > 1]
    if not terms:
        return []

    matches: list[tuple[int, GeocodeSuggestion]] = []
    seen: set[tuple[float, float]] = set()
    for hint_terms, result in LOCAL_HINTS:
        haystack = f"{' '.join(hint_terms)} {result.display_name}".casefold()
        score = sum(term in haystack for term in terms)
        if score == 0:
            continue
        location_key = (result.lat, result.lon)
        if location_key in seen:
            continue
        seen.add(location_key)
        matches.append(
            (
                score,
                GeocodeSuggestion(
                    place_id=_place_id("local", result.display_name),
                    result=result,
                ),
            )
        )
    matches.sort(key=lambda item: (-item[0], item[1].result.display_name))
    return [suggestion for _, suggestion in matches[:limit]]


@lru_cache(maxsize=256)
def suggest_addresses(
    address: str,
    endpoint: str = DEFAULT_ENDPOINT,
    place_hint: str = DEFAULT_PLACE_HINT,
    viewbox: str = DEFAULT_VIEWBOX,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_s: float = 8.0,
    limit: int = 5,
) -> list[GeocodeSuggestion]:
    query = _with_place_hint(address, place_hint)
    local_results = _local_suggestions(address, limit)
    if local_results:
        return local_results

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "1",
        "countrycodes": "us",
        "viewbox": viewbox,
        "bounded": "0",
    }
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": user_agent},
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeocodingServiceError("Address suggestions are unavailable right now.") from exc

    if not isinstance(payload, list):
        return []
    suggestions: list[GeocodeSuggestion] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            result = _result_from_payload(query, item)
        except GeocodingLookupError:
            continue
        raw_place_id = str(item.get("place_id") or item.get("osm_id") or "")
        place_id = f"osm_{raw_place_id}" if raw_place_id else _place_id("osm", result.display_name)
        suggestions.append(GeocodeSuggestion(place_id=place_id, result=result))
    return suggestions[:limit]


@lru_cache(maxsize=256)
def geocode_address(
    address: str,
    endpoint: str = DEFAULT_ENDPOINT,
    place_hint: str = DEFAULT_PLACE_HINT,
    viewbox: str = DEFAULT_VIEWBOX,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_s: float = 8.0,
) -> GeocodeResult:
    query = _with_place_hint(address, place_hint)
    local_result = _local_match(query)
    if local_result is not None:
        return local_result

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "addressdetails": "1",
        "countrycodes": "us",
        "viewbox": viewbox,
        "bounded": "0",
    }
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": user_agent},
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeocodingServiceError("Address lookup is unavailable right now.") from exc

    if not isinstance(payload, list) or not payload:
        raise GeocodingLookupError(f"No address match found for {address!r}.")

    first = payload[0]
    if not isinstance(first, dict):
        raise GeocodingLookupError(f"No address match found for {address!r}.")
    return _result_from_payload(query, first)


def _result_from_payload(query: str, payload: dict[str, Any]) -> GeocodeResult:
    try:
        lat = float(payload["lat"])
        lon = float(payload["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingLookupError(f"No address match found for {query!r}.") from exc
    display_name = str(payload.get("display_name") or query)
    return GeocodeResult(query=query, lat=lat, lon=lon, display_name=display_name)
