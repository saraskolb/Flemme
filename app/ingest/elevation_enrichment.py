from __future__ import annotations

from statistics import median

from app.core.grade import aggregate_edge_grade_metrics
from app.core.models import Edge, ElevationSample, Graph
from app.core.smoothing import smooth_elevation_profile
from app.ingest.elevation import ElevationProvider
from app.ingest.graph_builder import densify_geometry


def unique_densified_points(
    graph: Graph,
    sample_spacing_m: float,
) -> list[tuple[float, float]]:
    points_by_key: dict[str, tuple[float, float]] = {}
    for edge in graph.edges.values():
        for lon, lat, _dist_m in densify_geometry(edge.geometry, spacing_m=sample_spacing_m):
            points_by_key.setdefault(f"{lat:.7f},{lon:.7f}", (lat, lon))
    return list(points_by_key.values())


def prefetch_graph_elevations(
    graph: Graph,
    elevation_provider: ElevationProvider,
    sample_spacing_m: float,
) -> int:
    points = unique_densified_points(graph, sample_spacing_m=sample_spacing_m)
    elevation_provider.elevations(points)
    return len(points)


def samples_for_geometry(
    geometry: list[tuple[float, float]],
    elevation_provider: ElevationProvider,
    sample_spacing_m: float,
) -> list[ElevationSample]:
    densified = densify_geometry(geometry, spacing_m=sample_spacing_m)
    elevations = elevation_provider.elevations([(lat, lon) for lon, lat, _ in densified])
    samples = [
        ElevationSample(dist_m=dist_m, z_raw_m=z_m, z_smooth_m=z_m)
        for (lon, lat, dist_m), z_m in zip(densified, elevations, strict=True)
    ]
    return smooth_elevation_profile(samples)


def update_edge_elevation_metrics(
    edge: Edge,
    samples: list[ElevationSample],
    flat_speed_mps: float = 1.34,
) -> None:
    metrics = aggregate_edge_grade_metrics(samples)
    edge.samples = samples
    edge.gain_m = metrics["gain_m"]
    edge.loss_m = metrics["loss_m"]
    edge.mean_grade = metrics["mean_grade"]
    edge.max_uphill_grade = metrics["max_uphill_grade"]
    edge.max_downhill_grade = metrics["max_downhill_grade"]
    edge.max_abs_grade = metrics["max_abs_grade"]
    edge.sustained_uphill_grade_20m = metrics["sustained_uphill_grade_20m"]
    edge.sustained_downhill_grade_20m = metrics["sustained_downhill_grade_20m"]
    edge.sustained_uphill_grade_50m = metrics["sustained_uphill_grade_50m"]
    edge.sustained_downhill_grade_50m = metrics["sustained_downhill_grade_50m"]
    edge.length_above_6pct_up_m = metrics["length_above_6pct_up_m"]
    edge.length_above_8pct_up_m = metrics["length_above_8pct_up_m"]
    edge.length_above_10pct_up_m = metrics["length_above_10pct_up_m"]
    edge.length_above_12pct_up_m = metrics["length_above_12pct_up_m"]
    edge.base_time_s = edge.length_m / flat_speed_mps
    edge.slope_time_s = 0.0


def enrich_graph_elevations(
    graph: Graph,
    elevation_provider: ElevationProvider,
    sample_spacing_m: float,
) -> Graph:
    prefetch_graph_elevations(
        graph,
        elevation_provider=elevation_provider,
        sample_spacing_m=sample_spacing_m,
    )
    node_elevations: dict[int, list[float]] = {}
    for edge in graph.edges.values():
        samples = samples_for_geometry(
            edge.geometry,
            elevation_provider=elevation_provider,
            sample_spacing_m=sample_spacing_m,
        )
        update_edge_elevation_metrics(edge, samples)
        if samples:
            node_elevations.setdefault(edge.source, []).append(samples[0].z_smooth_m)
            node_elevations.setdefault(edge.target, []).append(samples[-1].z_smooth_m)

    for node_id, elevations in node_elevations.items():
        if node_id in graph.nodes and elevations:
            graph.nodes[node_id].z_m = median(elevations)
    return graph
