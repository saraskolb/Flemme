from __future__ import annotations

from app.google.routes_baseline import google_maps_walking_directions_url


def test_google_maps_walking_directions_url_uses_walking_mode() -> None:
    url = google_maps_walking_directions_url(
        "1737 Post Street, San Francisco, CA",
        "1227 Page Street, San Francisco, CA",
    )

    assert url.startswith("https://www.google.com/maps/dir/?")
    assert "origin=1737+Post+Street%2C+San+Francisco%2C+CA" in url
    assert "destination=1227+Page+Street%2C+San+Francisco%2C+CA" in url
    assert "travelmode=walking" in url
