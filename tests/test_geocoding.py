from __future__ import annotations

from app.geocoding import geocode_address


def test_geocode_address_uses_local_hint_for_1737_post() -> None:
    result = geocode_address("1737 Post Street")

    assert result.display_name == "1737 Post Street, San Francisco, CA"
    assert result.lat == 37.785372647
    assert result.lon == -122.431366397


def test_geocode_address_uses_local_hint_for_whole_foods_stanyan() -> None:
    result = geocode_address("the whole foods on stayan street")

    assert result.display_name == (
        "Whole Foods Market, 690 Stanyan Street, San Francisco, CA"
    )
    assert result.lat == 37.769562
    assert result.lon == -122.452782
