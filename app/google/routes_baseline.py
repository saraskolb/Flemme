from __future__ import annotations


def fetch_google_walking_baseline(
    origin: tuple[float, float], destination: tuple[float, float]
) -> dict[str, object]:
    """Fetch a Google walking route later for validation and fallback comparison only."""
    raise NotImplementedError("Google route baselines are not wired in the first slice.")
