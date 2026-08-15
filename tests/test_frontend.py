from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_shell_is_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "<h1>flemme</h1>" in response.text
    assert 'content="#f9a8d4"' in response.text
    assert "origin-address" in response.text
    assert "manifest.webmanifest" in response.text
    assert "locate-button" in response.text
    assert "use-location-button" in response.text
    assert "Use current location as start" in response.text
    assert "Current" in response.text
    assert "next-step" in response.text
    assert "data-preset" not in response.text
    assert "Page to Duboce" not in response.text
    assert "/static/app.js" in response.text


def test_frontend_assets_are_served() -> None:
    client = TestClient(app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "runRouteQuery" in response.text
    assert "/geocode" in response.text
    assert "/feedback" in response.text
    assert "useCurrentLocationForStart" in response.text
    assert "installViewportGuards" in response.text
    assert "invalidateSize" in response.text
    assert "basemaps.cartocdn.com" in response.text
    assert "routePolylineLayers" in response.text
    assert '"#f9a8d4"' in response.text


def test_frontend_pwa_assets_are_served() -> None:
    client = TestClient(app)

    manifest = client.get("/static/manifest.webmanifest")
    worker = client.get("/static/service-worker.js")
    styles = client.get("/static/styles.css")
    icon = client.get("/static/icon.svg")

    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "flemme"
    assert manifest.json()["display"] == "standalone"
    assert manifest.json()["theme_color"] == "#f9a8d4"
    assert worker.status_code == 200
    assert "flemme-shell-v11" in worker.text
    assert styles.status_code == 200
    assert "--brand: #f9a8d4" in styles.text
    assert 'font-family: "Snell Roundhand"' in styles.text
    assert "-webkit-text-stroke" in styles.text
    assert "rgb(31 41 55 / 0.28)" in styles.text
    assert "border-radius: 18px" in styles.text
    assert "--keyboard-offset" in styles.text
    assert "top: 12px" in styles.text
    assert "--mobile-top-safe-space" not in styles.text
    assert ".is-editing .query-panel" in styles.text
    assert ".clean-map-tiles" in styles.text
    assert ".route-tab-meta" in styles.text
    assert ".input-action-row input" in styles.text
    assert "border-radius: 999px" in styles.text
    assert "width: auto" in styles.text
    assert "touch-action: manipulation" in styles.text
    assert "height: 44px" in styles.text
    assert icon.status_code == 200
    assert 'aria-label="flemme"' in icon.text
    assert 'fill="#f9a8d4"' in icon.text


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
