from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ingest.elevation import (
    FlatElevationProvider,
    RasterElevationProvider,
    parse_open_meteo_elevation_response,
    parse_usgs_epqs_response,
)


def test_flat_elevation_provider_returns_constant_values() -> None:
    provider = FlatElevationProvider(z_m=12.5)

    assert provider.elevations([(37.0, -122.0), (38.0, -123.0)]) == [12.5, 12.5]


def test_parse_usgs_epqs_value_response() -> None:
    assert parse_usgs_epqs_response({"value": 42.25}) == 42.25


def test_parse_usgs_epqs_nested_response() -> None:
    payload = {
        "USGS_Elevation_Point_Query_Service": {
            "Elevation_Query": {
                "Elevation": "31.2",
            }
        }
    }

    assert parse_usgs_epqs_response(payload) == 31.2


def test_parse_open_meteo_batch_response() -> None:
    payload = [{"elevation": 12.0}, {"elevation": "18.5"}]

    assert parse_open_meteo_elevation_response(payload) == [12.0, 18.5]


def test_parse_open_meteo_elevation_list_response() -> None:
    payload = {"elevation": [12.0, "18.5"]}

    assert parse_open_meteo_elevation_response(payload) == [12.0, 18.5]


def test_raster_elevation_provider_samples_local_dem(tmp_path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin  # type: ignore[import-untyped]

    dem_path = tmp_path / "tiny_dem.tif"
    data = np.array([[10.0, 20.0], [30.0, 40.0]], dtype="float32")
    with rasterio.open(
        dem_path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(-122.0, 38.0, 0.1, 0.1),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(data, 1)

    provider = RasterElevationProvider(dem_path)

    assert provider.elevations([(37.95, -121.95), (37.85, -121.85)]) == [10.0, 40.0]
