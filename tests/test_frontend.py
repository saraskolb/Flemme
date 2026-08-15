from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_shell_is_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Flemme" in response.text
    assert "origin-address" in response.text
    assert "manifest.webmanifest" in response.text
    assert "locate-button" in response.text
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


def test_frontend_pwa_assets_are_served() -> None:
    client = TestClient(app)

    manifest = client.get("/static/manifest.webmanifest")
    worker = client.get("/static/service-worker.js")

    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    assert worker.status_code == 200
    assert "flemme-shell" in worker.text


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
