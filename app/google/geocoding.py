from __future__ import annotations


def geocode_address(address: str) -> tuple[float, float]:
    """Geocode an address through Google Maps in a future adapter."""
    raise NotImplementedError("Google geocoding is not wired in the first slice.")
