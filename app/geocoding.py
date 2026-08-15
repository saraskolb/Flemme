from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
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


LOCAL_HINTS: tuple[tuple[tuple[str, ...], GeocodeResult], ...] = (
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
