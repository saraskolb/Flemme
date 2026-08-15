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

PAGE_DUBOCE_GRAPH = Path("data/graphs/page_duboce_walk_graph.json")
PAGE_STREET_ORIGIN = (37.7714654, -122.4412496)
DUBOCE_NOE_DESTINATION = (37.76919, -122.43357)


@pytest.mark.skipif(
    not PAGE_DUBOCE_GRAPH.exists(),
    reason="Local Page-Duboce graph cache has not been generated.",
)
def test_page_duboce_graph_name_quality() -> None:
    graph = JSONGraphRepository(PAGE_DUBOCE_GRAPH).load_graph()

    integrity_issues = audit_graph_integrity(graph)
    name_quality = audit_edge_name_quality(graph)

    assert integrity_issues == []
    assert name_quality.missing_display_name_edges == 0
    assert name_quality.datasf_name_rate >= 0.70
    assert name_quality.generic_non_stairs_rate <= 0.16
    assert name_quality.long_generic_connector_edges <= 4
    assert name_quality.generic_unnamed_major_road_edges == 0


@pytest.mark.skipif(
    not PAGE_DUBOCE_GRAPH.exists(),
    reason="Local Page-Duboce graph cache has not been generated.",
)
def test_page_to_duboce_route_directions_use_specific_street_names() -> None:
    graph = JSONGraphRepository(PAGE_DUBOCE_GRAPH).load_graph()
    start_node = snap_point_to_graph(
        graph,
        lat=PAGE_STREET_ORIGIN[0],
        lon=PAGE_STREET_ORIGIN[1],
    )
    goal_node = snap_point_to_graph(
        graph,
        lat=DUBOCE_NOE_DESTINATION[0],
        lon=DUBOCE_NOE_DESTINATION[1],
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
    fastest_edges = graph.route_edges(fastest.edge_ids)

    assert audit_route_direction_quality(routes) == []
    street_names = [step.street_name for step in recommended.directions]
    assert street_names[:3] == ["Page Street", "Broderick Street", "Haight Street"]
    assert "Waller Street" in street_names
    assert "Carmelita Street" in street_names
    assert recommended.metrics.gain_m < fastest.metrics.gain_m
    assert sum(edge.length_above_6pct_up_m for edge in recommended_edges) < 10.0
    assert sum(edge.length_above_10pct_up_m for edge in recommended_edges) < 5.0
    assert sum(edge.length_above_6pct_up_m for edge in fastest_edges) > 300.0
