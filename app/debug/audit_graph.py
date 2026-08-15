from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal, cast

from app.api.schemas import PreferencesIn, preferences_to_user_prefs
from app.core.alternatives import generate_route_candidates
from app.core.graph_quality import (
    audit_edge_name_quality,
    audit_graph_integrity,
    audit_route_direction_quality,
)
from app.core.models import RouteOption
from app.core.snapping import snap_point_to_graph
from app.db.repositories import JSONGraphRepository

RouteMode = Literal["fastest", "balanced", "avoid_hills", "accessibility", "custom"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a Flemme graph cache.")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--origin-lat", type=float)
    parser.add_argument("--origin-lon", type=float)
    parser.add_argument("--destination-lat", type=float)
    parser.add_argument("--destination-lon", type=float)
    parser.add_argument(
        "--mode",
        choices=["fastest", "balanced", "avoid_hills", "accessibility", "custom"],
        default="balanced",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit nonzero if the graph misses the current quality thresholds.",
    )
    parser.add_argument("--min-datasf-name-rate", type=float, default=0.70)
    parser.add_argument("--max-generic-non-stairs-rate", type=float, default=0.16)
    parser.add_argument("--max-long-generic-connectors", type=int, default=4)
    return parser.parse_args()


def _route_candidates(args: argparse.Namespace, graph_path: Path) -> list[RouteOption]:
    has_route_args = all(
        value is not None
        for value in (
            args.origin_lat,
            args.origin_lon,
            args.destination_lat,
            args.destination_lon,
        )
    )
    if not has_route_args:
        return []

    graph = JSONGraphRepository(graph_path).load_graph()
    start_node = snap_point_to_graph(graph, lat=args.origin_lat, lon=args.origin_lon)
    goal_node = snap_point_to_graph(graph, lat=args.destination_lat, lon=args.destination_lon)
    if start_node is None or goal_node is None:
        raise ValueError("Could not snap origin or destination to graph.")
    prefs = preferences_to_user_prefs(PreferencesIn(mode=cast(RouteMode, args.mode)))
    return generate_route_candidates(graph, start_node, goal_node, prefs)


def _payload(args: argparse.Namespace) -> tuple[dict[str, object], bool]:
    graph = JSONGraphRepository(args.graph).load_graph()
    name_report = audit_edge_name_quality(graph)
    integrity_issues = audit_graph_integrity(graph)
    routes = _route_candidates(args, args.graph)
    direction_issues = audit_route_direction_quality(routes)
    route_summaries = [
        {
            "label": route.label,
            "time_min": round(route.metrics.time_s / 60.0, 1),
            "distance_mi": round(route.metrics.distance_m / 1609.344, 2),
            "max_uphill_grade_pct": round(route.metrics.max_uphill_grade * 100.0, 1),
            "street_sequence": [step.street_name for step in route.directions],
            "directions": [step.instruction for step in route.directions],
        }
        for route in routes
    ]

    failed = (
        bool(integrity_issues)
        or bool(direction_issues)
        or name_report.missing_display_name_edges > 0
        or name_report.datasf_name_rate < args.min_datasf_name_rate
        or name_report.generic_non_stairs_rate > args.max_generic_non_stairs_rate
        or name_report.long_generic_connector_edges > args.max_long_generic_connectors
        or name_report.generic_unnamed_major_road_edges > 0
    )
    return (
        {
            "graph": str(args.graph),
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "name_quality": name_report.as_dict(),
            "integrity_issues": [asdict(issue) for issue in integrity_issues],
            "direction_issues": [asdict(issue) for issue in direction_issues],
            "routes": route_summaries,
            "thresholds": {
                "min_datasf_name_rate": args.min_datasf_name_rate,
                "max_generic_non_stairs_rate": args.max_generic_non_stairs_rate,
                "max_long_generic_connectors": args.max_long_generic_connectors,
            },
            "passed": not failed,
        },
        failed,
    )


def _print_text(payload: dict[str, object]) -> None:
    quality = payload["name_quality"]
    assert isinstance(quality, dict)
    integrity_issues = cast(list[object], payload["integrity_issues"])
    direction_issues = cast(list[object], payload["direction_issues"])
    routes = cast(list[dict[str, object]], payload["routes"])
    print(f"Graph: {payload['graph']}")
    print(f"Nodes: {payload['nodes']}  Edges: {payload['edges']}")
    print(f"Display-name coverage: {quality['display_name_coverage']:.1%}")
    print(f"DataSF name rate: {quality['datasf_name_rate']:.1%}")
    print(f"Generic non-stairs rate: {quality['generic_non_stairs_rate']:.1%}")
    print(f"Long generic connectors: {quality['long_generic_connector_edges']}")
    print(f"Generic unnamed major-road edges: {quality['generic_unnamed_major_road_edges']}")
    print(f"Integrity issues: {len(integrity_issues)}")
    print(f"Direction issues: {len(direction_issues)}")
    for route in routes:
        street_sequence = cast(list[object], route["street_sequence"])
        print(
            f"{route['label']}: {route['time_min']} min, {route['distance_mi']} mi, "
            f"max uphill {route['max_uphill_grade_pct']}%, "
            f"{' -> '.join(str(name) for name in street_sequence)}"
        )
    print(f"Passed: {payload['passed']}")


def main() -> None:
    args = _parse_args()
    payload, failed = _payload(args)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_text(payload)
    if failed and args.fail_on_thresholds:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
