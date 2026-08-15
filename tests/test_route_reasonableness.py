from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.alternatives import build_route_option, generate_route_candidates, profile_path
from app.core.costs import BALANCED, FASTEST
from app.core.models import Edge, Graph, Node
from app.core.route_reasonableness import diagnose_route, route_time_budget_s


def _edge(
    edge_id: int,
    base_time_s: float,
    length_m: float,
    max_uphill_grade: float,
    length_above_6pct_up_m: float = 0.0,
    length_above_8pct_up_m: float = 0.0,
    length_above_10pct_up_m: float = 0.0,
    length_above_12pct_up_m: float = 0.0,
    street_name: str = "Route",
) -> Edge:
    return Edge(
        edge_id=edge_id,
        source=1,
        target=99,
        geometry=[(-122.0, 37.0), (-121.99, 37.0)],
        length_m=length_m,
        street_name=street_name,
        base_time_s=base_time_s,
        gain_m=max_uphill_grade * length_above_6pct_up_m,
        max_uphill_grade=max_uphill_grade,
        max_abs_grade=max_uphill_grade,
        sustained_uphill_grade_20m=max_uphill_grade,
        sustained_uphill_grade_50m=max_uphill_grade,
        length_above_6pct_up_m=length_above_6pct_up_m,
        length_above_8pct_up_m=length_above_8pct_up_m,
        length_above_10pct_up_m=length_above_10pct_up_m,
        length_above_12pct_up_m=length_above_12pct_up_m,
    )


def _reasonableness_graph() -> Graph:
    return Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0, x=0.0, y=0.0),
            99: Node(99, lon=-121.99, lat=37.0, x=1_000.0, y=0.0),
        },
        edges={
            101: _edge(
                101,
                base_time_s=600.0,
                length_m=1_000.0,
                max_uphill_grade=0.30,
                length_above_6pct_up_m=100.0,
                length_above_8pct_up_m=100.0,
                length_above_10pct_up_m=100.0,
                length_above_12pct_up_m=100.0,
                street_name="Fast Steep Street",
            ),
            201: _edge(
                201,
                base_time_s=830.0,
                length_m=1_180.0,
                max_uphill_grade=0.12,
                length_above_6pct_up_m=50.0,
                length_above_8pct_up_m=30.0,
                length_above_10pct_up_m=10.0,
                street_name="Middle Way",
            ),
            301: _edge(
                301,
                base_time_s=1_000.0,
                length_m=1_520.0,
                max_uphill_grade=0.06,
                street_name="Overlong Flat Road",
            ),
        },
    )


def test_reasonableness_policy_rejects_overlong_flat_default() -> None:
    graph = _reasonableness_graph()
    prefs = replace(BALANCED, max_extra_time_s_for_flatter_route=500)

    assert profile_path(graph, 1, 99, BALANCED) == [301]

    routes = generate_route_candidates(graph, 1, 99, prefs)
    by_label = {route.label: route for route in routes}

    assert by_label["fastest"].edge_ids == [101]
    assert by_label["recommended"].edge_ids == [201]
    assert by_label["recommended"].metrics.time_s <= route_time_budget_s(by_label["fastest"])
    assert by_label["recommended"].metrics.max_uphill_grade == pytest.approx(0.12)
    assert by_label["recommended"].metrics.time_s < by_label["flattest"].metrics.time_s


def test_route_diagnostics_explain_why_overlong_route_is_not_reasonable() -> None:
    graph = _reasonableness_graph()
    fastest = build_route_option(graph, [101], "fastest", FASTEST)
    overlong = build_route_option(graph, [301], "recommended", BALANCED)

    diagnostics = diagnose_route(
        overlong,
        fastest,
        graph.route_edges(overlong.edge_ids),
        graph.route_edges(fastest.edge_ids),
    )

    assert diagnostics.within_time_budget is False
    assert diagnostics.hill_benefit_score > 0.0
    assert diagnostics.is_reasonable_recommendation is False


def test_route_diagnostics_reject_indirect_detour_even_with_hill_savings() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0, x=0.0, y=0.0),
            99: Node(99, lon=-121.99, lat=37.0, x=1_000.0, y=0.0),
        },
        edges={
            101: _edge(
                101,
                base_time_s=600.0,
                length_m=1_000.0,
                max_uphill_grade=0.25,
                length_above_6pct_up_m=130.0,
                length_above_8pct_up_m=130.0,
                length_above_10pct_up_m=130.0,
                length_above_12pct_up_m=130.0,
                street_name="Direct Steep Street",
            ),
            201: _edge(
                201,
                base_time_s=720.0,
                length_m=1_300.0,
                max_uphill_grade=0.08,
                length_above_6pct_up_m=20.0,
                street_name="Indirect Flat Street",
            ),
        },
    )
    fastest = build_route_option(graph, [101], "fastest", FASTEST)
    indirect = build_route_option(graph, [201], "recommended", BALANCED)

    diagnostics = diagnose_route(
        indirect,
        fastest,
        graph.route_edges(indirect.edge_ids),
        graph.route_edges(fastest.edge_ids),
    )

    assert diagnostics.directness_ratio > 1.45
    assert diagnostics.within_time_budget is True
    assert diagnostics.hill_benefit_score > 0.0
    assert diagnostics.within_shape_budget is False
    assert diagnostics.is_reasonable_recommendation is False


def test_route_diagnostics_reject_many_extra_direction_steps() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0, x=0.0, y=0.0),
            99: Node(99, lon=-121.99, lat=37.0, x=1_000.0, y=0.0),
        },
        edges={
            101: _edge(
                101,
                base_time_s=600.0,
                length_m=1_000.0,
                max_uphill_grade=0.25,
                length_above_6pct_up_m=160.0,
                length_above_8pct_up_m=160.0,
                length_above_10pct_up_m=160.0,
                length_above_12pct_up_m=160.0,
                street_name="Direct Steep Street",
            ),
            **{
                200 + index: _edge(
                    200 + index,
                    base_time_s=85.0,
                    length_m=130.0,
                    max_uphill_grade=0.04,
                    street_name=f"Jog {index}",
                )
                for index in range(1, 9)
            },
        },
    )
    fastest = build_route_option(graph, [101], "fastest", FASTEST)
    joggy = build_route_option(
        graph,
        [201, 202, 203, 204, 205, 206, 207, 208],
        "recommended",
        BALANCED,
    )

    diagnostics = diagnose_route(
        joggy,
        fastest,
        graph.route_edges(joggy.edge_ids),
        graph.route_edges(fastest.edge_ids),
    )

    assert diagnostics.direction_step_delta == 7
    assert diagnostics.turn_penalty > 0.0
    assert diagnostics.within_direction_budget is False
    assert diagnostics.is_reasonable_recommendation is False
