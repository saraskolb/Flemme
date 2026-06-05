from __future__ import annotations

from dataclasses import replace
from typing import Literal

from app.core.astar import astar, walking_time_heuristic
from app.core.costs import (
    AVOID_HILLS,
    FASTEST,
    edge_allowed,
    make_edge_cost,
    route_metrics,
)
from app.core.explanations import detect_hill_events, explain_route
from app.core.models import Edge, Graph, RouteOption, UserPrefs
from app.core.pareto import pareto_prune


def route_geometry(edges: list[Edge]) -> list[tuple[float, float]]:
    geometry: list[tuple[float, float]] = []
    for edge in edges:
        if not geometry:
            geometry.extend(edge.geometry)
        elif edge.geometry:
            if geometry[-1] == edge.geometry[0]:
                geometry.extend(edge.geometry[1:])
            else:
                geometry.extend(edge.geometry)
    return geometry


def build_route_option(
    graph: Graph,
    edge_ids: list[int],
    label: Literal["fastest", "balanced", "flattest", "recommended", "accessible"],
    prefs: UserPrefs,
) -> RouteOption:
    edges = graph.route_edges(edge_ids)
    return RouteOption(
        label=label,
        edge_ids=list(edge_ids),
        geometry=route_geometry(edges),
        metrics=route_metrics(edges, prefs),
        hill_events=detect_hill_events(edges),
        explanation="",
    )


def _path_for_profile(graph: Graph, start: int, goal: int, prefs: UserPrefs) -> list[int] | None:
    heuristic = walking_time_heuristic(graph)
    return astar(
        graph=graph,
        start_node=start,
        goal_node=goal,
        edge_cost=make_edge_cost(prefs),
        heuristic=heuristic,
        edge_allowed=lambda edge: edge_allowed(edge, prefs),
    )


def _overlap_ratio(left: RouteOption, right: RouteOption) -> float:
    left_edges = set(left.edge_ids)
    right_edges = set(right.edge_ids)
    if not left_edges or not right_edges:
        return 0.0
    return len(left_edges & right_edges) / min(len(left_edges), len(right_edges))


def _deduplicate(options: list[RouteOption], max_overlap: float = 0.95) -> list[RouteOption]:
    unique: list[RouteOption] = []
    for option in options:
        if any(tuple(option.edge_ids) == tuple(existing.edge_ids) for existing in unique):
            continue
        if any(_overlap_ratio(option, existing) > max_overlap for existing in unique):
            continue
        unique.append(option)
    return unique


def generate_route_candidates(
    graph: Graph, start: int, goal: int, user_prefs: UserPrefs
) -> list[RouteOption]:
    candidates: list[RouteOption] = []

    fastest_path = _path_for_profile(graph, start, goal, FASTEST)
    if fastest_path is not None:
        candidates.append(build_route_option(graph, fastest_path, "fastest", FASTEST))

    recommendation_prefs = user_prefs
    if user_prefs.mode == "fastest":
        recommendation_prefs = FASTEST
    elif user_prefs.mode == "avoid_hills":
        recommendation_prefs = AVOID_HILLS
    elif user_prefs.mode == "accessibility":
        recommendation_prefs = replace(user_prefs, forbid_stairs=True)

    recommended_path = _path_for_profile(graph, start, goal, recommendation_prefs)
    if recommended_path is not None:
        label: Literal["recommended", "accessible"] = (
            "accessible" if recommendation_prefs.mode == "accessibility" else "recommended"
        )
        candidates.append(build_route_option(graph, recommended_path, label, recommendation_prefs))

    flattest_prefs = replace(
        AVOID_HILLS,
        max_extra_time_s_for_flatter_route=user_prefs.max_extra_time_s_for_flatter_route,
    )
    flattest_path = _path_for_profile(graph, start, goal, flattest_prefs)
    if flattest_path is not None:
        flattest = build_route_option(graph, flattest_path, "flattest", flattest_prefs)
        if candidates:
            fastest = candidates[0]
            budget = fastest.metrics.time_s + user_prefs.max_extra_time_s_for_flatter_route
            if flattest.metrics.time_s <= budget:
                candidates.append(flattest)
        else:
            candidates.append(flattest)

    candidates = pareto_prune(_deduplicate(candidates))
    fastest_option = next((option for option in candidates if option.label == "fastest"), None)
    if fastest_option is None and fastest_path is not None:
        fastest_option = build_route_option(graph, fastest_path, "fastest", FASTEST)

    for index, option in enumerate(candidates):
        candidates[index].explanation = explain_route(option, fastest_option, user_prefs)

    label_order = {"recommended": 0, "accessible": 0, "fastest": 1, "flattest": 2, "balanced": 3}
    return sorted(
        candidates,
        key=lambda option: (label_order[option.label], option.metrics.route_score),
    )


def best_route_for_profile(
    graph: Graph, start: int, goal: int, prefs: UserPrefs
) -> RouteOption | None:
    path = _path_for_profile(graph, start, goal, prefs)
    if path is None:
        return None
    return build_route_option(graph, path, "recommended", prefs)


def profile_path(graph: Graph, start: int, goal: int, prefs: UserPrefs) -> list[int] | None:
    return _path_for_profile(graph, start, goal, prefs)
