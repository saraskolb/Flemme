from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_feedback_endpoint_appends_route_feedback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    feedback_path = tmp_path / "route_feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_JSONL_PATH", str(feedback_path))
    client = TestClient(app)

    response = client.post(
        "/feedback",
        json={
            "feedback_type": "weird_turn",
            "graph_version": "test-graph",
            "route_label": "recommended",
            "route_edge_ids": [101, 102],
            "direction_street_names": ["Page Street", "Baker Street"],
            "origin_address": "1227 Page Street",
            "destination_address": "Duboce Park Cafe",
            "origin": {"lat": 37.7714654, "lon": -122.4412496},
            "destination": {"lat": 37.7691622, "lon": -122.4315697},
            "current_position": {
                "lat": 37.77,
                "lon": -122.44,
                "accuracy_m": 8.0,
                "observed_at": "2026-08-15T00:00:00Z",
            },
            "note": "This crossed the street twice for no reason.",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback_id"]
    assert payload["path"] == str(feedback_path)

    records = [json.loads(line) for line in feedback_path.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["feedback_type"] == "weird_turn"
    assert records[0]["route_edge_ids"] == [101, 102]
    assert records[0]["current_position"]["accuracy_m"] == 8.0
