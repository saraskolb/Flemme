from __future__ import annotations

from app.ingest.elevation import (
    FlatElevationProvider,
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
