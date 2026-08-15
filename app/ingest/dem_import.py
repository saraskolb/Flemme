from __future__ import annotations

from pathlib import Path

from app.ingest.elevation import RasterElevationProvider, USGSElevationProvider


def sample_dem_elevations(dem_path: Path, points_lat_lon: list[tuple[float, float]]) -> list[float]:
    """Sample a local DEM raster at WGS84 lat/lon points."""
    return RasterElevationProvider(dem_path).elevations(points_lat_lon)


def sample_usgs_epqs_elevations(
    points_lat_lon: list[tuple[float, float]], cache_path: Path | None = None
) -> list[float]:
    """Sample USGS EPQS elevations for a small set of WGS84 points.

    This is useful for early validation routes. City-wide production loading
    should prefer a local DEM raster to avoid one HTTP request per point.
    """
    return USGSElevationProvider(cache_path=cache_path).elevations(points_lat_lon)
