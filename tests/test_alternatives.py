from __future__ import annotations

from app.core.alternatives import _path_with_turn_penalty, generate_route_candidates
from app.core.costs import BALANCED
from app.core.models import Edge, Graph, Node
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


def test_low_turn_path_prefers_simple_street_sequence() -> None:
    nodes = {
        node_id: Node(node_id=node_id, lon=0.0, lat=0.0, x=0.0, y=0.0)
        for node_id in {1, 2, 3, 4, 10, 99}
    }
    graph = Graph(
        nodes=nodes,
        edges={
            101: Edge(101, 1, 2, [(0.0, 0.0), (0.0, 0.0)], 60.0, "Alpha Street", base_time_s=60.0),
            102: Edge(102, 2, 3, [(0.0, 0.0), (0.0, 0.0)], 60.0, "Beta Street", base_time_s=60.0),
            103: Edge(103, 3, 4, [(0.0, 0.0), (0.0, 0.0)], 60.0, "Gamma Street", base_time_s=60.0),
            104: Edge(104, 4, 99, [(0.0, 0.0), (0.0, 0.0)], 60.0, "Delta Street", base_time_s=60.0),
            201: Edge(
                201,
                1,
                10,
                [(0.0, 0.0), (0.0, 0.0)],
                130.0,
                "Direct Street",
                base_time_s=130.0,
            ),
            202: Edge(
                202,
                10,
                99,
                [(0.0, 0.0), (0.0, 0.0)],
                130.0,
                "Direct Street",
                base_time_s=130.0,
            ),
        },
    )

    path = _path_with_turn_penalty(graph, 1, 99, BALANCED, turn_penalty_s=90.0)

    assert path == [201, 202]
