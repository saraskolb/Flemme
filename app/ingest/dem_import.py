from __future__ import annotations

from pathlib import Path

from app.ingest.elevation import USGSElevationProvider


def sample_dem_elevations(dem_path: Path, points_xy: list[tuple[float, float]]) -> list[float]:
    """Sample a local DEM raster at projected points.

    TODO:
    - Open a local DEM with rasterio.
    - Sample elevation at densified edge points.
    - Return elevation values plus confidence metadata.
    """
    raise NotImplementedError("DEM sampling is intentionally stubbed in the first slice.")


def sample_usgs_epqs_elevations(
    points_lat_lon: list[tuple[float, float]], cache_path: Path | None = None
) -> list[float]:
    """Sample USGS EPQS elevations for a small set of WGS84 points.

    This is useful for early validation routes. City-wide production loading
    should prefer a local DEM raster to avoid one HTTP request per point.
    """
    return USGSElevationProvider(cache_path=cache_path).elevations(points_lat_lon)
