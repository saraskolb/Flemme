from __future__ import annotations

from pathlib import Path

import pytest

from app.api.schemas import PreferencesIn, preferences_to_user_prefs
from app.core.alternatives import generate_route_candidates
from app.core.graph_quality import (
    audit_edge_name_quality,
    audit_graph_integrity,
    audit_route_direction_quality,
)
from app.core.snapping import snap_point_to_graph
from app.db.repositories import JSONGraphRepository

PANHANDLE_COLE_GRAPH = Path("data/graphs/panhandle_cole_walk_graph_dem_10m.json")
PAGE_STREET_ORIGIN = (37.7714654, -122.4412496)
COLE_CARL_DESTINATION = (37.76595, -122.45055)


@pytest.mark.skipif(
    not PANHANDLE_COLE_GRAPH.exists(),
    reason="Local Panhandle/Cole Valley graph cache has not been generated.",
)
def test_panhandle_cole_dense_graph_routes_around_steep_fastest_cut() -> None:
    graph = JSONGraphRepository(PANHANDLE_COLE_GRAPH).load_graph()
    start_node = snap_point_to_graph(
        graph,
        lat=PAGE_STREET_ORIGIN[0],
        lon=PAGE_STREET_ORIGIN[1],
    )
    goal_node = snap_point_to_graph(
        graph,
        lat=COLE_CARL_DESTINATION[0],
        lon=COLE_CARL_DESTINATION[1],
    )
    assert start_node is not None
    assert goal_node is not None

    name_quality = audit_edge_name_quality(graph)
    routes = generate_route_candidates(
        graph,
        start_node,
        goal_node,
        preferences_to_user_prefs(PreferencesIn(mode="balanced")),
    )
    recommended = next(route for route in routes if route.label == "recommended")
    fastest = next(route for route in routes if route.label == "fastest")
    street_names = [step.street_name for step in recommended.directions]

    assert audit_graph_integrity(graph) == []
    assert audit_route_direction_quality(routes) == []
    assert name_quality.missing_display_name_edges == 0
    assert name_quality.datasf_name_rate >= 0.70
    assert name_quality.generic_non_stairs_rate <= 0.16
    assert recommended.metrics.max_uphill_grade < fastest.metrics.max_uphill_grade
    assert "Page Street" in street_names
    assert "Cole Street" in street_names
    assert street_names[-1] == "Carl Street"
