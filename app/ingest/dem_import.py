from __future__ import annotations

from pathlib import Path


def sample_dem_elevations(dem_path: Path, points_xy: list[tuple[float, float]]) -> list[float]:
    """Sample a local DEM raster at projected points.

    TODO:
    - Open a local DEM with rasterio.
    - Sample elevation at densified edge points.
    - Return elevation values plus confidence metadata.
    """
    raise NotImplementedError("DEM sampling is intentionally stubbed in the first slice.")
