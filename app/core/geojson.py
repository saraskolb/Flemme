from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from app.core.models import Edge, Graph, RouteOption

GeoJSONGeometryType = Literal["LineString", "Point"]


def _line_feature(
    geometry: list[tuple[float, float]], properties: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": geometry,
        },
        "properties": properties,
    }


def _point_feature(lon: float, lat: float, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": properties,
    }


def edge_debug_properties(edge: Edge, sequence: int) -> dict[str, Any]:
    return {
        "feature_type": "edge",
        "sequence": sequence,
        "edge_id": edge.edge_id,
        "source": edge.source,
        "target": edge.target,
        "osm_way_id": edge.osm_way_id,
        "street_name": edge.street_name,
        "edge_type": edge.edge_type,
        "access": edge.access,
        "stairs": edge.stairs,
        "surface": edge.surface,
        "length_m": edge.length_m,
        "gain_m": edge.gain_m,
        "loss_m": edge.loss_m,
        "max_uphill_grade_pct": edge.max_uphill_grade * 100.0,
        "max_downhill_grade_pct": edge.max_downhill_grade * 100.0,
        "max_abs_grade_pct": edge.max_abs_grade * 100.0,
        "length_above_8pct_up_m": edge.length_above_8pct_up_m,
        "length_above_10pct_up_m": edge.length_above_10pct_up_m,
        "source_tags": edge.source_tags,
    }


def route_to_geojson(
    graph: Graph,
    option: RouteOption,
    start_node: int | None = None,
    goal_node: int | None = None,
    include_edges: bool = True,
) -> dict[str, Any]:
    metrics = asdict(option.metrics)
    features: list[dict[str, Any]] = [
        _line_feature(
            option.geometry,
            {
                "feature_type": "route",
                "label": option.label,
                "edge_ids": option.edge_ids,
                "explanation": option.explanation,
                **metrics,
            },
        )
    ]

    if include_edges:
        for sequence, edge in enumerate(graph.route_edges(option.edge_ids), start=1):
            features.append(_line_feature(edge.geometry, edge_debug_properties(edge, sequence)))

    if start_node is not None and start_node in graph.nodes:
        node = graph.nodes[start_node]
        features.append(
            _point_feature(
                node.lon,
                node.lat,
                {
                    "feature_type": "snap_point",
                    "role": "origin",
                    "node_id": node.node_id,
                },
            )
        )

    if goal_node is not None and goal_node in graph.nodes:
        node = graph.nodes[goal_node]
        features.append(
            _point_feature(
                node.lon,
                node.lat,
                {
                    "feature_type": "snap_point",
                    "role": "destination",
                    "node_id": node.node_id,
                },
            )
        )

    return {
        "type": "FeatureCollection",
        "properties": {
            "graph_version": graph.version,
            "route_label": option.label,
        },
        "features": features,
    }
