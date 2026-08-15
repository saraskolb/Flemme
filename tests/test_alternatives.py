from __future__ import annotations

from app.core.alternatives import (
    _path_with_turn_penalty,
    _path_with_visible_turn_penalty,
    generate_route_candidates,
)
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


def test_visible_turn_path_ignores_tiny_intersection_fragments() -> None:
    nodes = {
        node_id: Node(node_id=node_id, lon=0.0, lat=0.0, x=0.0, y=0.0)
        for node_id in {1, 2, 3, 4, 5, 10, 11, 99}
    }
    graph = Graph(
        nodes=nodes,
        edges={
            101: Edge(101, 1, 2, [(0.0, 0.0), (0.0, 0.0)], 100.0, "Page Street", base_time_s=100.0),
            102: Edge(102, 2, 3, [(0.0, 0.0), (0.0, 0.0)], 5.0, "Broderick Street", base_time_s=5.0),
            103: Edge(103, 3, 4, [(0.0, 0.0), (0.0, 0.0)], 100.0, "Page Street", base_time_s=100.0),
            104: Edge(104, 4, 5, [(0.0, 0.0), (0.0, 0.0)], 100.0, "Scott Street", base_time_s=100.0),
            105: Edge(105, 5, 99, [(0.0, 0.0), (0.0, 0.0)], 100.0, "Duboce Avenue", base_time_s=100.0),
            201: Edge(201, 1, 10, [(0.0, 0.0), (0.0, 0.0)], 165.0, "Oak Street", base_time_s=165.0),
            202: Edge(202, 10, 11, [(0.0, 0.0), (0.0, 0.0)], 165.0, "Pierce Street", base_time_s=165.0),
            203: Edge(203, 11, 99, [(0.0, 0.0), (0.0, 0.0)], 165.0, "Waller Street", base_time_s=165.0),
        },
    )

    raw_turn_path = _path_with_turn_penalty(graph, 1, 99, BALANCED, turn_penalty_s=90.0)
    visible_turn_path = _path_with_visible_turn_penalty(
        graph,
        1,
        99,
        BALANCED,
        turn_penalty_s=90.0,
    )

    assert raw_turn_path == [201, 202, 203]
    assert visible_turn_path == [101, 102, 103, 104, 105]


def test_fastest_route_notes_when_it_is_also_flattest() -> None:
    nodes = {
        1: Node(node_id=1, lon=-122.0, lat=37.0, x=0.0, y=0.0),
        99: Node(node_id=99, lon=-121.99, lat=37.0, x=1_000.0, y=0.0),
    }
    graph = Graph(
        nodes=nodes,
        edges={
            101: Edge(
                101,
                1,
                99,
                [(-122.0, 37.0), (-121.99, 37.0)],
                1_000.0,
                "Flat Street",
                base_time_s=600.0,
            ),
        },
    )

    routes = generate_route_candidates(graph, 1, 99, BALANCED)

    assert [route.label for route in routes] == ["fastest"]
    assert "also the flattest practical route Flemme found" in routes[0].explanation


def test_practically_identical_flatter_route_is_collapsed_into_fastest_note() -> None:
    nodes = {
        node_id: Node(node_id=node_id, lon=-122.0, lat=37.0, x=0.0, y=0.0)
        for node_id in {1, 2, 3, 98, 99}
    }
    graph = Graph(
        nodes=nodes,
        edges={
            101: Edge(
                101,
                1,
                2,
                [(-122.0, 37.0), (-121.99, 37.0)],
                1_000.0,
                "03RD Street",
                base_time_s=600.0,
                gain_m=4.4,
                max_uphill_grade=0.49,
                max_abs_grade=0.49,
                sustained_uphill_grade_20m=0.49,
                length_above_6pct_up_m=9.0,
                length_above_8pct_up_m=9.0,
                length_above_10pct_up_m=9.0,
                length_above_12pct_up_m=9.0,
            ),
            102: Edge(
                102,
                2,
                99,
                [(-121.99, 37.0), (-121.98, 37.0)],
                1_000.0,
                "Kearny Street",
                base_time_s=600.0,
            ),
            201: Edge(
                201,
                1,
                3,
                [(-122.0, 37.0), (-121.9902, 37.0)],
                1_030.0,
                "03RD Street",
                base_time_s=620.0,
                max_uphill_grade=0.05,
                max_abs_grade=0.05,
            ),
            202: Edge(
                202,
                3,
                99,
                [(-121.9902, 37.0), (-121.98, 37.0)],
                1_000.0,
                "Kearny Street",
                base_time_s=605.0,
            ),
            301: Edge(
                301,
                1,
                98,
                [(-122.0, 37.0), (-121.9902, 37.0)],
                1_030.0,
                "03RD Street",
                base_time_s=620.0,
                max_uphill_grade=0.05,
                max_abs_grade=0.05,
            ),
            302: Edge(
                302,
                98,
                99,
                [(-121.9902, 37.0), (-121.98, 37.0)],
                1_000.0,
                "Kearny Street",
                base_time_s=605.0,
            ),
        },
    )

    routes = generate_route_candidates(graph, 1, 99, BALANCED)

    assert [route.label for route in routes] == ["fastest"]
    assert "also the flattest practical route Flemme found" in routes[0].explanation
    assert "10%+ uphill stretch is only 9 m" in routes[0].explanation
