from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_shell_is_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Flemme" in response.text
    assert "origin-address" in response.text
    assert "/static/app.js" in response.text


def test_frontend_assets_are_served() -> None:
    client = TestClient(app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "runRouteQuery" in response.text
    assert "/geocode" in response.text


def test_geocode_endpoint_resolves_local_validation_intersection() -> None:
    client = TestClient(app)

    response = client.post("/geocode", json={"address": "Page and Broderick"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lat"] == 37.7714654
    assert payload["lon"] == -122.4412496
