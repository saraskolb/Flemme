from __future__ import annotations

from typing import Any

from pyproj import Geod, Transformer

from app.core.edge_naming import assign_edge_display_names
from app.core.grade import aggregate_edge_grade_metrics, reverse_samples
from app.core.models import Edge, ElevationSample, Graph, Node
from app.core.smoothing import smooth_elevation_profile
from app.ingest.elevation import ElevationProvider, FlatElevationProvider

GEOD = Geod(ellps="WGS84")
WGS84_TO_UTM10 = Transformer.from_crs("EPSG:4326", "EPSG:26910", always_xy=True)


def geometry_length_m(geometry: list[tuple[float, float]]) -> float:
    total = 0.0
    for left, right in zip(geometry, geometry[1:], strict=False):
        _, _, distance_m = GEOD.inv(left[0], left[1], right[0], right[1])
        total += distance_m
    return total


def densify_geometry(
    geometry: list[tuple[float, float]], spacing_m: float = 20.0
) -> list[tuple[float, float, float]]:
    if len(geometry) < 2:
        raise ValueError("Geometry must contain at least two coordinates.")
    if spacing_m <= 0:
        raise ValueError("spacing_m must be positive.")

    points: list[tuple[float, float, float]] = [(geometry[0][0], geometry[0][1], 0.0)]
    cumulative_m = 0.0
    for left, right in zip(geometry, geometry[1:], strict=False):
        _, _, segment_length_m = GEOD.inv(left[0], left[1], right[0], right[1])
        intermediate_count = max(0, int(segment_length_m // spacing_m))
        intermediate = (
            GEOD.npts(left[0], left[1], right[0], right[1], intermediate_count)
            if intermediate_count > 0
            else []
        )
        segment_points = [*intermediate, right]
        previous = left
        for point in segment_points:
            _, _, step_m = GEOD.inv(previous[0], previous[1], point[0], point[1])
            cumulative_m += step_m
            points.append((point[0], point[1], cumulative_m))
            previous = point
    return points


def _node_from_raw(node_id: int, raw_node: dict[str, float], z_m: float | None = None) -> Node:
    lon = float(raw_node["lon"])
    lat = float(raw_node["lat"])
    x, y = WGS84_TO_UTM10.transform(lon, lat)
    return Node(
        node_id=node_id,
        lon=lon,
        lat=lat,
        x=float(x),
        y=float(y),
        z_m=z_m,
        node_type="osm_node",
    )


def _edge_attrs(raw_segment: dict[str, Any]) -> dict[str, Any]:
    tags = raw_segment.get("tags", {})
    highway = str(tags.get("highway", "path"))
    sidewalk = tags.get("sidewalk")
    return {
        "street_name": tags.get("name"),
        "edge_type": highway,
        "access": str(tags.get("access") or tags.get("foot") or "unknown"),
        "sidewalk_availability": str(sidewalk) if sidewalk is not None else None,
        "sidewalk_width_m": None,
        "wheelchair_access": tags.get("wheelchair"),
        "stairs": highway == "steps",
        "surface": tags.get("surface"),
        "osm_way_id": raw_segment.get("osm_way_id"),
        "source_tags": {str(key): str(value) for key, value in tags.items()},
    }


def _edge_from_samples(
    edge_id: int,
    source: int,
    target: int,
    geometry: list[tuple[float, float]],
    samples: list[ElevationSample],
    attrs: dict[str, Any],
) -> Edge:
    metrics = aggregate_edge_grade_metrics(samples)
    length_m = geometry_length_m(geometry)
    return Edge(
        edge_id=edge_id,
        source=source,
        target=target,
        geometry=geometry,
        length_m=length_m,
        samples=samples,
        base_time_s=length_m / 1.34,
        slope_time_s=0.0,
        street_name=attrs["street_name"],
        edge_type=attrs["edge_type"],
        access=attrs["access"],
        sidewalk_availability=attrs["sidewalk_availability"],
        sidewalk_width_m=attrs["sidewalk_width_m"],
        wheelchair_access=attrs["wheelchair_access"],
        stairs=attrs["stairs"],
        surface=attrs["surface"],
        osm_way_id=attrs["osm_way_id"],
        source_tags=attrs["source_tags"],
        gain_m=metrics["gain_m"],
        loss_m=metrics["loss_m"],
        mean_grade=metrics["mean_grade"],
        max_uphill_grade=metrics["max_uphill_grade"],
        max_downhill_grade=metrics["max_downhill_grade"],
        max_abs_grade=metrics["max_abs_grade"],
        sustained_uphill_grade_20m=metrics["sustained_uphill_grade_20m"],
        sustained_downhill_grade_20m=metrics["sustained_downhill_grade_20m"],
        sustained_uphill_grade_50m=metrics["sustained_uphill_grade_50m"],
        sustained_downhill_grade_50m=metrics["sustained_downhill_grade_50m"],
        length_above_6pct_up_m=metrics["length_above_6pct_up_m"],
        length_above_8pct_up_m=metrics["length_above_8pct_up_m"],
        length_above_10pct_up_m=metrics["length_above_10pct_up_m"],
        length_above_12pct_up_m=metrics["length_above_12pct_up_m"],
    )


def _samples_for_geometry(
    geometry: list[tuple[float, float]],
    elevation_provider: ElevationProvider,
    spacing_m: float,
) -> list[ElevationSample]:
    densified = densify_geometry(geometry, spacing_m=spacing_m)
    return _samples_for_densified(densified, elevation_provider)


def _samples_for_densified(
    densified: list[tuple[float, float, float]],
    elevation_provider: ElevationProvider,
) -> list[ElevationSample]:
    elevations = elevation_provider.elevations([(lat, lon) for lon, lat, _ in densified])
    samples = [
        ElevationSample(dist_m=dist_m, z_raw_m=z_m, z_smooth_m=z_m)
        for (lon, lat, dist_m), z_m in zip(densified, elevations, strict=True)
    ]
    return smooth_elevation_profile(samples)


def build_directed_graph(
    raw_segments: list[dict[str, Any]],
    elevation_provider: ElevationProvider | None = None,
    graph_version: str = "sf-osm-dev",
    sample_spacing_m: float = 20.0,
) -> Graph:
    """Build a directed Flemme graph from raw OSM node-pair segments."""
    provider = elevation_provider or FlatElevationProvider()
    nodes: dict[int, Node] = {}
    edges: dict[int, Edge] = {}
    next_edge_id = 1
    densified_by_index: list[list[tuple[float, float, float]]] = []
    unique_points: dict[str, tuple[float, float]] = {}

    for raw_segment in raw_segments:
        geometry = [tuple(point) for point in raw_segment["geometry"]]
        densified = densify_geometry(geometry, spacing_m=sample_spacing_m)
        densified_by_index.append(densified)
        for lon, lat, _ in densified:
            unique_points[f"{lat:.7f},{lon:.7f}"] = (lat, lon)

    provider.elevations(list(unique_points.values()))

    for raw_segment, densified in zip(raw_segments, densified_by_index, strict=True):
        source_id = int(raw_segment["source_osm_node_id"])
        target_id = int(raw_segment["target_osm_node_id"])
        geometry = [tuple(point) for point in raw_segment["geometry"]]
        samples = _samples_for_densified(densified, provider)

        nodes[source_id] = _node_from_raw(
            source_id, raw_segment["source"], z_m=samples[0].z_smooth_m
        )
        nodes[target_id] = _node_from_raw(
            target_id, raw_segment["target"], z_m=samples[-1].z_smooth_m
        )

        attrs = _edge_attrs(raw_segment)
        edges[next_edge_id] = _edge_from_samples(
            next_edge_id,
            source_id,
            target_id,
            geometry,
            samples,
            attrs,
        )
        next_edge_id += 1

        reverse_geometry = list(reversed(geometry))
        reverse_edge_samples = reverse_samples(samples)
        edges[next_edge_id] = _edge_from_samples(
            next_edge_id,
            target_id,
            source_id,
            reverse_geometry,
            reverse_edge_samples,
            attrs,
        )
        next_edge_id += 1

    return assign_edge_display_names(Graph(nodes=nodes, edges=edges, version=graph_version))
