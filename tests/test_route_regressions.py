from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.api.schemas import PreferencesIn, preferences_to_user_prefs
from app.core.alternatives import generate_route_candidates
from app.core.models import Graph, RouteOption
from app.core.route_reasonableness import route_uphill_exposure
from app.core.snapping import snap_point_to_graph
from app.db.repositories import JSONGraphRepository

CITY_GRAPH = Path("data/graphs/sf_walk_graph_dem_10m.json")
ROUTE_CASES = Path("tests/fixtures/route_regression_cases.json")


@pytest.fixture(scope="session")
def city_graph() -> Graph:
    if not CITY_GRAPH.exists():
        pytest.skip(f"City graph cache has not been generated: {CITY_GRAPH}")
    return JSONGraphRepository(CITY_GRAPH).load_graph()


def _route_cases() -> Iterator[dict[str, Any]]:
    cases = json.loads(ROUTE_CASES.read_text(encoding="utf-8"))
    yield from cases


def _street_sequence(route: RouteOption) -> list[str]:
    streets: list[str] = []
    for step in route.directions:
        if step.street_name and step.street_name != (streets[-1] if streets else None):
            streets.append(step.street_name)
    return streets


def _route_by_label(routes: list[RouteOption], label: str) -> RouteOption:
    try:
        return next(route for route in routes if route.label == label)
    except StopIteration:
        labels = [route.label for route in routes]
        raise AssertionError(f"Expected route label {label!r}; got {labels}") from None


@pytest.mark.parametrize("case", list(_route_cases()), ids=lambda case: case["id"])
def test_citywide_route_regression_cases(city_graph: Graph, case: dict[str, Any]) -> None:
    start_node = snap_point_to_graph(
        city_graph,
        lat=case["origin"]["lat"],
        lon=case["origin"]["lon"],
    )
    goal_node = snap_point_to_graph(
        city_graph,
        lat=case["destination"]["lat"],
        lon=case["destination"]["lon"],
    )
    assert start_node is not None
    assert goal_node is not None

    prefs = preferences_to_user_prefs(PreferencesIn(**case.get("preferences", {})))
    routes = generate_route_candidates(city_graph, start_node, goal_node, prefs)
    assert routes

    expected = case["expected"]
    route = _route_by_label(routes, expected.get("route_label", "recommended"))
    streets = _street_sequence(route)
    exposure = route_uphill_exposure(city_graph.route_edges(route.edge_ids))

    if "street_sequence" in expected:
        assert streets == expected["street_sequence"]

    for street in expected.get("forbidden_streets", []):
        assert street not in streets

    if "max_direction_steps" in expected:
        assert len(route.directions) <= expected["max_direction_steps"]
    if "max_time_min" in expected:
        assert route.metrics.time_s / 60.0 <= expected["max_time_min"]
    if "max_distance_m" in expected:
        assert route.metrics.distance_m <= expected["max_distance_m"]
    if "max_uphill_grade_pct" in expected:
        assert route.metrics.max_uphill_grade * 100.0 <= expected["max_uphill_grade_pct"]
    if "max_10pct_uphill_m" in expected:
        assert exposure.above_10pct_m <= expected["max_10pct_uphill_m"]
    if "max_12pct_uphill_m" in expected:
        assert exposure.above_12pct_m <= expected["max_12pct_uphill_m"]
