from __future__ import annotations

import pytest

from app.ingest.graph_builder import build_directed_graph


class EndpointClimbProvider:
    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        return [float(index * 10) for index, _ in enumerate(points)]


def test_build_directed_graph_creates_direction_sensitive_edges() -> None:
    raw_segments = [
        {
            "source_osm_node_id": 1,
            "target_osm_node_id": 2,
            "source": {"lat": 37.772, "lon": -122.439},
            "target": {"lat": 37.772, "lon": -122.438},
            "geometry": [(-122.439, 37.772), (-122.438, 37.772)],
            "tags": {"highway": "residential", "name": "Page Street"},
        }
    ]

    graph = build_directed_graph(
        raw_segments,
        elevation_provider=EndpointClimbProvider(),
        sample_spacing_m=500.0,
    )

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 2
    forward = graph.edges[1]
    reverse = graph.edges[2]
    assert forward.source == 1
    assert forward.target == 2
    assert forward.max_uphill_grade > 0.0
    assert reverse.source == 2
    assert reverse.target == 1
    assert reverse.max_uphill_grade == pytest.approx(0.0)
    assert reverse.max_downhill_grade == pytest.approx(forward.max_uphill_grade)
