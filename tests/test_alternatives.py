from __future__ import annotations

from app.core.alternatives import generate_route_candidates
from app.core.costs import BALANCED
from app.db.repositories import SyntheticGraphRepository


def test_generate_route_candidates_returns_fastest_and_recommended() -> None:
    graph = SyntheticGraphRepository().load_graph()

    routes = generate_route_candidates(graph, 1, 99, BALANCED)
    by_label = {route.label: route for route in routes}

    assert by_label["fastest"].edge_ids == [101, 102, 103]
    assert by_label["recommended"].edge_ids == [201, 202]


def test_route_candidates_are_deduplicated_by_edge_overlap() -> None:
    graph = SyntheticGraphRepository().load_graph()

    routes = generate_route_candidates(graph, 1, 99, BALANCED)
    edge_signatures = [tuple(route.edge_ids) for route in routes]

    assert len(edge_signatures) == len(set(edge_signatures))
