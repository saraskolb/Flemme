from __future__ import annotations

from app.core.models import Edge, Graph, Node
from app.ingest.elevation_enrichment import (
    enrich_graph_elevations,
    prefetch_graph_elevations,
    unique_densified_points,
)


class MidpointHillProvider:
    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        elevations: list[float] = []
        for _lat, lon in points:
            distance_from_midpoint = abs(lon + 121.999)
            elevations.append(max(0.0, 10.0 - distance_from_midpoint * 10_000.0))
        return elevations


class CountingProvider:
    def __init__(self) -> None:
        self.requested_points: list[tuple[float, float]] = []

    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        self.requested_points.extend(points)
        return [1.0 for _point in points]


def test_prefetch_graph_elevations_deduplicates_reversed_edges() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=90.0,
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=1,
                geometry=[(-121.999, 37.0), (-122.0, 37.0)],
                length_m=90.0,
            ),
        },
    )
    provider = CountingProvider()

    unique_points = unique_densified_points(graph, sample_spacing_m=40.0)
    prefetched_count = prefetch_graph_elevations(
        graph,
        provider,
        sample_spacing_m=40.0,
    )

    assert prefetched_count == len(unique_points)
    assert provider.requested_points == unique_points
    assert len(unique_points) < 2 * 4


def test_enrich_graph_elevations_resamples_edges_without_canceling_gain_and_loss() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.998, lat=37.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.998, 37.0)],
                length_m=180.0,
                samples=[],
            )
        },
    )

    enrich_graph_elevations(graph, MidpointHillProvider(), sample_spacing_m=40.0)

    edge = graph.edges[1]
    assert len(edge.samples) > 2
    assert edge.gain_m > 0
    assert edge.loss_m > 0
    assert abs(edge.mean_grade) < edge.max_uphill_grade
    assert edge.max_downhill_grade > 0
