from __future__ import annotations

from typing import Any


def preprocess_raw_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepare raw pedestrian segments for routing.

    TODO:
    - Densify geometries to 2-5 m spacing.
    - Sample DEM elevation.
    - Smooth elevation profiles.
    - Compute grade metrics.
    - Split steep or attribute-changing segments.
    - Create directed edges and precompute profile costs.
    - Persist results to PostGIS.
    """
    raise NotImplementedError("Preprocessing is intentionally stubbed in the first slice.")
