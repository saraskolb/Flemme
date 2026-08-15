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

NOPA_FILLMORE_JAPANTOWN_GRAPH = Path(
    "data/graphs/nopa_fillmore_japantown_walk_graph_dem_10m.json"
)
PAGE_STREET_ORIGIN = (37.7714654, -122.4412496)
POST_WEBSTER_DESTINATION = (37.785372647, -122.431366397)
BLOCKED_SERVICE_VALUES = {"drive-through", "driveway", "parking_aisle"}


@pytest.mark.skipif(
    not NOPA_FILLMORE_JAPANTOWN_GRAPH.exists(),
    reason="Local NOPA/Fillmore/Japantown graph cache has not been generated.",
)
def test_nopa_fillmore_japantown_graph_routes_to_post_webster_cleanly() -> None:
    graph = JSONGraphRepository(NOPA_FILLMORE_JAPANTOWN_GRAPH).load_graph()
    start_node = snap_point_to_graph(
        graph,
        lat=PAGE_STREET_ORIGIN[0],
        lon=PAGE_STREET_ORIGIN[1],
    )
    goal_node = snap_point_to_graph(
        graph,
        lat=POST_WEBSTER_DESTINATION[0],
        lon=POST_WEBSTER_DESTINATION[1],
    )
    assert start_node is not None
    assert goal_node is not None

    routes = generate_route_candidates(
        graph,
        start_node,
        goal_node,
        preferences_to_user_prefs(PreferencesIn(mode="balanced")),
    )
    recommended = next(route for route in routes if route.label == "recommended")
    fastest = next(route for route in routes if route.label == "fastest")
    recommended_edges = graph.route_edges(recommended.edge_ids)
    street_names = [step.street_name for step in recommended.directions]

    name_quality = audit_edge_name_quality(graph)
    assert audit_graph_integrity(graph) == []
    assert audit_route_direction_quality(routes) == []
    assert name_quality.missing_display_name_edges == 0
    assert name_quality.datasf_name_rate >= 0.80
    assert name_quality.generic_non_stairs_rate <= 0.08
    assert name_quality.generic_unnamed_major_road_edges == 0
    assert name_quality.long_generic_connector_edges <= 6

    assert street_names == ["Page Street", "Divisadero Street", "Post Street"]
    assert "unnamed street" not in street_names
    assert all(
        edge.source_tags.get("service") not in BLOCKED_SERVICE_VALUES for edge in recommended_edges
    )
    assert recommended.metrics.max_uphill_grade <= 0.08
    assert fastest.metrics.max_uphill_grade > recommended.metrics.max_uphill_grade
