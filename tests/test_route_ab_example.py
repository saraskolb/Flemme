from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.alternatives import generate_route_candidates
from app.core.costs import BALANCED
from app.db.repositories import SyntheticGraphRepository
from app.main import app


def test_route_ab_example_passes_exactly() -> None:
    graph = SyntheticGraphRepository().load_graph()

    routes = generate_route_candidates(graph, 1, 99, BALANCED)
    by_label = {route.label: route for route in routes}

    assert by_label["fastest"].edge_ids == [101, 102, 103]
    assert by_label["recommended"].edge_ids == [201, 202]
    assert by_label["fastest"].metrics.time_s == pytest.approx(600.0)
    assert by_label["recommended"].metrics.time_s == pytest.approx(660.0)
    assert by_label["fastest"].metrics.max_abs_grade == pytest.approx(0.16)
    assert by_label["recommended"].metrics.max_abs_grade == pytest.approx(0.06)
    assert "1 minute slower" in by_label["recommended"].explanation
    assert "16%" in by_label["recommended"].explanation


def test_debug_synthetic_route_endpoint() -> None:
    client = TestClient(app)

    response = client.post(
        "/debug/route-on-synthetic-graph",
        json={"preferences": {"mode": "balanced"}},
    )

    assert response.status_code == 200
    payload = response.json()
    by_label = {route["label"]: route for route in payload["routes"]}
    assert payload["graph_version"] == "dev-synthetic-001"
    assert by_label["fastest"]["edge_ids"] == [101, 102, 103]
    assert by_label["recommended"]["edge_ids"] == [201, 202]
    assert by_label["recommended"]["directions"][0]["instruction"].startswith("Walk")
    assert "16%" in by_label["recommended"]["explanation"]
    assert by_label["recommended"]["route_id"].startswith("route_")
    assert by_label["recommended"]["title"] == "Gentler route"
    assert by_label["recommended"]["badge"] == "Best balance"
    assert by_label["recommended"]["comparison"]["extra_time_s"] == pytest.approx(60.0)
    assert by_label["recommended"]["comparison"]["avoided_10pct_uphill_m"] > 0
    assert "avoids_steepest_climb" in by_label["recommended"]["recommendation"]["reason_codes"]
    assert by_label["recommended"]["bounds"]["south"] <= by_label["recommended"]["bounds"]["north"]
    assert by_label["recommended"]["directions"][0]["step_id"].startswith("step_")
    assert by_label["recommended"]["directions"][0]["start_distance_m"] == 0
    assert by_label["recommended"]["directions"][0]["end_distance_m"] > 0
    assert by_label["recommended"]["directions"][0]["maneuver"] == "depart"
    assert by_label["recommended"]["data_quality"]["elevation_coverage"] >= 0


def test_production_route_endpoint_is_future_shaped_not_synthetic() -> None:
    client = TestClient(app)

    response = client.post(
        "/route",
        json={
            "origin": {"lat": 37.7749, "lon": -122.4194},
            "destination": {"lat": 37.8024, "lon": -122.4058},
            "preferences": {"mode": "balanced"},
        },
    )

    assert response.status_code == 501
    assert "Set GRAPH_JSON_PATH" in response.json()["detail"]
