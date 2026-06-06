from __future__ import annotations

import json
from pathlib import Path

from app.core.models import Edge, Graph, Node
from app.db.repositories import save_graph_json
from app.debug.export_route import export_route_debug_map


def test_export_route_debug_map_writes_geojson_and_html(tmp_path: Path) -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0, x=0.0, y=0.0),
            2: Node(2, lon=-121.999, lat=37.0, x=100.0, y=0.0),
        },
        edges={
            10: Edge(
                edge_id=10,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=100.0,
                street_name="Page Street",
                base_time_s=75.0,
            )
        },
        version="debug-test",
    )
    graph_path = tmp_path / "graph.json"
    geojson_path = tmp_path / "route.geojson"
    html_path = tmp_path / "route.html"
    save_graph_json(graph, graph_path)

    routes = export_route_debug_map(
        graph_path=graph_path,
        origin_lat=37.0,
        origin_lon=-122.0,
        destination_lat=37.0,
        destination_lon=-121.999,
        mode="balanced",
        route_label="all",
        geojson_output=geojson_path,
        html_output=html_path,
    )

    assert routes[0].edge_ids == [10]
    geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert geojson["features"][0]["properties"]["route_label"] == "fastest"
    html = html_path.read_text(encoding="utf-8")
    assert "Flemme Route Debug Map" in html
    assert "Page Street" in html
