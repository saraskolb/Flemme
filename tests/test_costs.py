from __future__ import annotations

import math

import pytest

from app.core.alternatives import profile_path
from app.core.costs import (
    ACCESSIBILITY,
    AVOID_HILLS,
    BALANCED,
    FASTEST,
    downhill_penalty_curve,
    edge_cost,
    max_grade_penalty,
    uphill_penalty_curve,
)
from app.core.models import Edge, Graph, Node
from app.db.repositories import SyntheticGraphRepository


def test_penalties_are_zero_below_thresholds() -> None:
    assert uphill_penalty_curve(0.06) == 0.0
    assert downhill_penalty_curve(0.08) == 0.0
    assert max_grade_penalty(0.10) == 0.0


def test_costs_are_always_nonnegative_for_profiles() -> None:
    graph = SyntheticGraphRepository().load_graph()
    for prefs in [FASTEST, BALANCED, AVOID_HILLS, ACCESSIBILITY]:
        for edge in graph.edges.values():
            cost = edge_cost(edge, prefs)
            assert cost >= 0.0 or math.isinf(cost)


def test_ab_fixture_ranking_by_profile() -> None:
    graph = SyntheticGraphRepository().load_graph()

    assert profile_path(graph, 1, 99, FASTEST) == [101, 102, 103]
    assert profile_path(graph, 1, 99, BALANCED) == [201, 202]
    assert profile_path(graph, 1, 99, AVOID_HILLS) == [201, 202]
    assert profile_path(graph, 1, 99, ACCESSIBILITY) == [201, 202]


def test_avoid_hills_forbids_route_over_hard_grade() -> None:
    graph = SyntheticGraphRepository().load_graph()

    steep_edge = graph.edges[102]

    assert steep_edge.max_uphill_grade == pytest.approx(0.16)
    assert steep_edge.max_abs_grade == pytest.approx(0.16)
    assert math.isinf(edge_cost(steep_edge, AVOID_HILLS))


def test_avoid_hills_does_not_avoid_steep_downhill() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=0.0, lat=0.0),
            2: Node(2, lon=0.0, lat=0.0),
            3: Node(3, lon=0.0, lat=0.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(0.0, 0.0), (1.0, 0.0)],
                length_m=100.0,
                base_time_s=100.0,
                loss_m=20.0,
                max_downhill_grade=0.20,
                max_abs_grade=0.20,
                sustained_downhill_grade_20m=0.20,
            ),
            2: Edge(
                edge_id=2,
                source=1,
                target=3,
                geometry=[(0.0, 0.0), (0.5, 0.0)],
                length_m=80.0,
                base_time_s=80.0,
            ),
            3: Edge(
                edge_id=3,
                source=3,
                target=2,
                geometry=[(0.5, 0.0), (1.0, 0.0)],
                length_m=80.0,
                base_time_s=80.0,
            ),
        },
    )

    downhill_edge = graph.edges[1]

    assert edge_cost(downhill_edge, AVOID_HILLS) == pytest.approx(100.0)
    assert profile_path(graph, 1, 2, AVOID_HILLS) == [1]
