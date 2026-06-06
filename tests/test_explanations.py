from __future__ import annotations

import pytest

from app.core.alternatives import build_route_option
from app.core.costs import BALANCED, FASTEST
from app.core.explanations import detect_hill_events, explain_route
from app.core.models import Edge, Graph, Node


def _steep_edge(edge_id: int, source: int, target: int, length_m: float = 30.0) -> Edge:
    return Edge(
        edge_id=edge_id,
        source=source,
        target=target,
        geometry=[(float(source), 0.0), (float(target), 0.0)],
        length_m=length_m,
        street_name="Same Hill",
        gain_m=length_m * 0.12,
        mean_grade=0.12,
        max_uphill_grade=0.12,
        max_abs_grade=0.12,
        sustained_uphill_grade_20m=0.12,
        length_above_8pct_up_m=length_m,
        length_above_10pct_up_m=length_m,
        base_time_s=length_m,
    )


def test_adjacent_steep_edges_on_same_street_merge() -> None:
    events = detect_hill_events([_steep_edge(1, 1, 2), _steep_edge(2, 2, 3)])

    assert len(events) == 1
    assert events[0].length_m == pytest.approx(60.0)
    assert events[0].max_sustained_grade == pytest.approx(0.12)
    assert events[0].length_above_10pct_m == pytest.approx(60.0)


def test_steep_downhill_is_not_reported_as_hill_event() -> None:
    downhill = Edge(
        edge_id=1,
        source=1,
        target=2,
        geometry=[(0.0, 0.0), (1.0, 0.0)],
        length_m=100.0,
        loss_m=20.0,
        max_downhill_grade=0.20,
        max_abs_grade=0.20,
        sustained_downhill_grade_20m=0.20,
        base_time_s=100.0,
    )

    assert detect_hill_events([downhill]) == []


def test_recommended_route_explanation_mentions_tradeoff_and_avoided_grade() -> None:
    nodes = {
        1: Node(1, lon=0.0, lat=0.0, x=0.0, y=0.0),
        2: Node(2, lon=1.0, lat=0.0, x=1.0, y=0.0),
        3: Node(3, lon=2.0, lat=0.0, x=2.0, y=0.0),
    }
    steep = _steep_edge(1, 1, 2, length_m=60.0)
    gentle = Edge(
        edge_id=2,
        source=1,
        target=3,
        geometry=[(0.0, 0.0), (2.0, 0.0)],
        length_m=70.0,
        max_uphill_grade=0.06,
        max_abs_grade=0.06,
        sustained_uphill_grade_20m=0.06,
        base_time_s=120.0,
    )
    graph = Graph(nodes=nodes, edges={1: steep, 2: gentle})
    fastest = build_route_option(graph, [1], "fastest", FASTEST)
    recommended = build_route_option(graph, [2], "recommended", BALANCED)

    explanation = explain_route(recommended, fastest, BALANCED)

    assert "1 minute slower" in explanation
    assert "12%" in explanation


def test_sub_minute_tradeoff_does_not_say_zero_minutes() -> None:
    nodes = {
        1: Node(1, lon=0.0, lat=0.0, x=0.0, y=0.0),
        2: Node(2, lon=1.0, lat=0.0, x=1.0, y=0.0),
        3: Node(3, lon=2.0, lat=0.0, x=2.0, y=0.0),
    }
    steep = _steep_edge(1, 1, 2, length_m=60.0)
    gentle = Edge(
        edge_id=2,
        source=1,
        target=3,
        geometry=[(0.0, 0.0), (2.0, 0.0)],
        length_m=70.0,
        max_uphill_grade=0.06,
        max_abs_grade=0.06,
        sustained_uphill_grade_20m=0.06,
        base_time_s=89.0,
    )
    graph = Graph(nodes=nodes, edges={1: steep, 2: gentle})
    fastest = build_route_option(graph, [1], "fastest", FASTEST)
    recommended = build_route_option(graph, [2], "recommended", BALANCED)

    explanation = explain_route(recommended, fastest, BALANCED)

    assert "less than 1 minute slower" in explanation
    assert "0 minutes" not in explanation
