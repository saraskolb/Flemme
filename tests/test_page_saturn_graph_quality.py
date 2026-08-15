from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pytest

from app.api.schemas import PreferencesIn, preferences_to_user_prefs
from app.core.alternatives import generate_route_candidates
from app.core.graph_quality import (
    audit_edge_name_quality,
    audit_graph_integrity,
    audit_route_direction_quality,
)
from app.core.models import Node
from app.core.snapping import nearest_node
from app.db.repositories import JSONGraphRepository

PAGE_SATURN_GRAPH = Path("data/graphs/page_saturn_tight_walk_graph.json")
PAGE_STREET_ORIGIN = (37.7714654, -122.4412496)
SATURN_STEPS_DESTINATION = (37.76273, -122.44052)


def _distance_m(left: tuple[float, float], node: Node) -> float:
    lat, lon = left
    radius_m = 6_371_008.8
    dlat = radians(node.lat - lat)
    dlon = radians(node.lon - lon)
    haversine = (
        sin(dlat / 2.0) ** 2
        + cos(radians(lat)) * cos(radians(node.lat)) * sin(dlon / 2.0) ** 2
    )
    return 2.0 * radius_m * asin(sqrt(haversine))


@pytest.mark.skipif(
    not PAGE_SATURN_GRAPH.exists(),
    reason="Local Page-Saturn graph cache has not been generated.",
)
def test_page_saturn_graph_route_is_named_and_snaps_to_destination() -> None:
    graph = JSONGraphRepository(PAGE_SATURN_GRAPH).load_graph()
    start_node = nearest_node(
        graph,
        lat=PAGE_STREET_ORIGIN[0],
        lon=PAGE_STREET_ORIGIN[1],
    )
    goal_node = nearest_node(
        graph,
        lat=SATURN_STEPS_DESTINATION[0],
        lon=SATURN_STEPS_DESTINATION[1],
    )
    assert start_node is not None
    assert goal_node is not None
    assert _distance_m(PAGE_STREET_ORIGIN, start_node) < 50.0
    assert _distance_m(SATURN_STEPS_DESTINATION, goal_node) < 25.0

    integrity_issues = audit_graph_integrity(graph)
    name_quality = audit_edge_name_quality(graph)
    routes = generate_route_candidates(
        graph,
        start_node.node_id,
        goal_node.node_id,
        preferences_to_user_prefs(PreferencesIn(mode="balanced")),
    )

    assert integrity_issues == []
    assert name_quality.missing_display_name_edges == 0
    assert name_quality.datasf_name_rate >= 0.70
    assert name_quality.generic_non_stairs_rate <= 0.16
    assert audit_route_direction_quality(routes) == []
    recommended = next(route for route in routes if route.label == "recommended")
    street_names = [step.street_name for step in recommended.directions]
    assert street_names[-1] == "Saturn Street"
    assert "Buena Vista Ave East" in street_names
