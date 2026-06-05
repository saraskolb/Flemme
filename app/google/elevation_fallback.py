from __future__ import annotations


def fetch_google_elevation_fallback(points: list[tuple[float, float]]) -> list[float]:
    """Fetch Google elevation samples later as a fallback, not the primary DEM source."""
    raise NotImplementedError("Google elevation fallback is not wired in the first slice.")
