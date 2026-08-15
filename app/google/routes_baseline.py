from __future__ import annotations

from urllib.parse import urlencode


def google_maps_walking_directions_url(origin: str, destination: str) -> str:
    """Build a manual Google Maps walking comparison URL."""
    return "https://www.google.com/maps/dir/?" + urlencode(
        {
            "api": "1",
            "origin": origin,
            "destination": destination,
            "travelmode": "walking",
        }
    )


def fetch_google_walking_baseline(
    origin: tuple[float, float], destination: tuple[float, float]
) -> dict[str, object]:
    """Fetch a Google walking route later for validation and fallback comparison only."""
    raise NotImplementedError("Google route baselines are not wired in the first slice.")
