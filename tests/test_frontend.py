from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_shell_is_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Where are you going?" in response.text
    assert 'content="#b91c62"' in response.text
    assert "origin-address" in response.text
    assert "sheet-handle" in response.text
    assert "Collapse route details" in response.text
    assert "manifest.webmanifest" in response.text
    assert "locate-button" in response.text
    assert "use-location-button" in response.text
    assert "Use current location as start" in response.text
    assert "next-step" in response.text
    assert "Gentle hills" in response.text
    assert "Start walking" in response.text
    assert "Route feedback" in response.text
    assert 'type="module" src="/static/app.js"' in response.text


def test_frontend_assets_are_served() -> None:
    client = TestClient(app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "runRouteQuery" in response.text
    assert "installSuggestions" in response.text
    assert "renderRouteOptions" in response.text
    assert "renderSlope" in response.text
    assert "startWalking" in response.text
    assert "updateWalkProgress" in response.text
    assert "rerouteFromCurrent" in response.text
    assert "loadRouteFromQuery" in response.text
    assert "submitFeedback" in response.text
    assert "collapseSheet" in response.text
    assert "expandSheet" in response.text

    api = client.get("/static/api.js")
    map_asset = client.get("/static/map.js")
    assert api.status_code == 200
    assert "/geocode/suggest" in api.text
    assert "/feedback" in api.text
    assert map_asset.status_code == 200
    assert "tile.openstreetmap.org" in map_asset.text
    assert "invalidateSize" in map_asset.text


def test_frontend_pwa_assets_are_served() -> None:
    client = TestClient(app)

    manifest = client.get("/static/manifest.webmanifest")
    worker = client.get("/static/service-worker.js")
    styles = client.get("/static/styles.css")
    icon = client.get("/static/icon.svg")

    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "flemme"
    assert manifest.json()["display"] == "standalone"
    assert manifest.json()["theme_color"] == "#b91c62"
    assert worker.status_code == 200
    assert "flemme-shell-v14" in worker.text
    assert "/static/api.js" in worker.text
    assert "/static/map.js" in worker.text
    assert styles.status_code == 200
    assert "--brand: #b91c62" in styles.text
    assert ".plan-sheet" in styles.text
    assert ".route-query-bar" in styles.text
    assert ".route-reason" in styles.text
    assert ".walk-banner" in styles.text
    assert "--sheet-offset" in styles.text
    assert "touch-action: none" in styles.text
    assert "translateY(var(--sheet-offset))" in styles.text
    assert ".clean-map-tiles" in styles.text
    assert "border-radius: 999px" in styles.text
    assert icon.status_code == 200
    assert 'aria-label="flemme"' in icon.text
    assert 'fill="#b91c62"' in icon.text


def test_geocode_endpoint_resolves_local_validation_intersection() -> None:
    client = TestClient(app)

    response = client.post("/geocode", json={"address": "Page and Broderick"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lat"] == 37.7714654
    assert payload["lon"] == -122.4412496


def test_geocode_endpoint_resolves_citywide_demo_places() -> None:
    client = TestClient(app)

    response = client.post("/geocode", json={"address": "Ferry Building"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lat"] == 37.7955
    assert payload["lon"] == -122.3937


def test_geocode_endpoint_resolves_duboce_park_cafe_hint() -> None:
    client = TestClient(app)

    response = client.post("/geocode", json={"address": "Duboce Park Cafe"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lat"] == 37.7691622
    assert payload["lon"] == -122.4315697


def test_geocode_suggestions_return_local_places_without_network() -> None:
    client = TestClient(app)

    response = client.get("/geocode/suggest", params={"q": "whole foods"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestions"]
    assert payload["suggestions"][0]["place_id"].startswith("local_")
    assert "Whole Foods" in payload["suggestions"][0]["display_name"]
