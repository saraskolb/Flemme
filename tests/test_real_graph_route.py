from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.models import Edge, Graph, Node
from app.db.repositories import save_graph_json
from app.main import app


def test_route_uses_graph_json_path_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = Graph(
        nodes={
            1: Node(node_id=1, lon=1.0, lat=0.0, x=1.0, y=0.0),
            2: Node(node_id=2, lon=2.0, lat=0.0, x=2.0, y=0.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(1.0, 0.0), (2.0, 0.0)],
                length_m=50.0,
                base_time_s=50.0,
            )
        },
        version="real-json-test",
    )
    graph_path = tmp_path / "real_graph.json"
    save_graph_json(graph, graph_path)
    monkeypatch.setenv("GRAPH_JSON_PATH", str(graph_path))

    response = TestClient(app).post(
        "/route",
        json={
            "origin": {"lat": 0.0, "lon": 1.0},
            "destination": {"lat": 0.0, "lon": 2.0},
            "preferences": {"mode": "balanced"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["routes"][0]["edge_ids"] == [1]
