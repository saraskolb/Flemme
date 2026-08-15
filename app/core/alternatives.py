from __future__ import annotations

from dataclasses import replace
from typing import Literal

from app.core.astar import astar, walking_time_heuristic
from app.core.costs import (
    AVOID_HILLS,
    FASTEST,
    edge_allowed,
    edge_time_s,
    make_edge_cost,
    route_metrics,
)
from app.core.directions import build_directions
from app.core.explanations import detect_hill_events, explain_route
from app.core.models import Edge, Graph, RouteOption, UserPrefs
from app.core.route_reasonableness import choose_reasonable_recommendation

PEAK_GRADE_CANDIDATE_CAPS = (0.10, 0.12, 0.14, 0.16, 0.18, 0.20)


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
        directions=build_directions(edges, prefs),
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


def _path_with_max_uphill_grade(
    graph: Graph,
    start: int,
    goal: int,
    prefs: UserPrefs,
    max_uphill_grade: float,
) -> list[int] | None:
    heuristic = walking_time_heuristic(graph)
    return astar(
        graph=graph,
        start_node=start,
        goal_node=goal,
        edge_cost=lambda edge: edge_time_s(edge, FASTEST),
        heuristic=heuristic,
        edge_allowed=lambda edge: (
            edge_allowed(edge, prefs) and edge.max_uphill_grade <= max_uphill_grade
        ),
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


def _candidate_option(graph: Graph, edge_ids: list[int], prefs: UserPrefs) -> RouteOption:
    return build_route_option(graph, edge_ids, "recommended", prefs)


def _bounded_recommendation_candidates(
    graph: Graph,
    start: int,
    goal: int,
    prefs: UserPrefs,
) -> list[RouteOption]:
    candidates: list[RouteOption] = []

    profile_path = _path_for_profile(graph, start, goal, prefs)
    if profile_path is not None:
        candidates.append(_candidate_option(graph, profile_path, prefs))

    for cap in PEAK_GRADE_CANDIDATE_CAPS:
        capped_path = _path_with_max_uphill_grade(graph, start, goal, prefs, cap)
        if capped_path is not None:
            candidates.append(_candidate_option(graph, capped_path, prefs))

    avoid_hills_path = _path_for_profile(graph, start, goal, AVOID_HILLS)
    if avoid_hills_path is not None:
        candidates.append(_candidate_option(graph, avoid_hills_path, AVOID_HILLS))

    return _deduplicate(candidates)


def generate_route_candidates(
    graph: Graph, start: int, goal: int, user_prefs: UserPrefs
) -> list[RouteOption]:
    fastest_path = _path_for_profile(graph, start, goal, FASTEST)
    if fastest_path is None:
        return []

    fastest = build_route_option(graph, fastest_path, "fastest", FASTEST)
    candidates: list[RouteOption] = [fastest]

    if user_prefs.mode in {"balanced", "custom"}:
        recommendation_pool = _bounded_recommendation_candidates(graph, start, goal, user_prefs)
        candidate_edges = {
            tuple(option.edge_ids): graph.route_edges(option.edge_ids)
            for option in [fastest, *recommendation_pool]
        }
        recommended = choose_reasonable_recommendation(
            recommendation_pool,
            fastest,
            candidate_edges,
        )
        if tuple(recommended.edge_ids) != tuple(fastest.edge_ids):
            candidates.append(
                build_route_option(graph, recommended.edge_ids, "recommended", user_prefs)
            )
    elif user_prefs.mode != "fastest":
        recommendation_prefs = AVOID_HILLS if user_prefs.mode == "avoid_hills" else user_prefs
        if user_prefs.mode == "accessibility":
            recommendation_prefs = replace(user_prefs, forbid_stairs=True)

        recommended_path = _path_for_profile(graph, start, goal, recommendation_prefs)
        if recommended_path is not None and tuple(recommended_path) != tuple(fastest_path):
            label: Literal["recommended", "accessible"] = (
                "accessible" if recommendation_prefs.mode == "accessibility" else "recommended"
            )
            candidates.append(
                build_route_option(graph, recommended_path, label, recommendation_prefs)
            )

    flattest_prefs = replace(
        AVOID_HILLS,
        max_extra_time_s_for_flatter_route=user_prefs.max_extra_time_s_for_flatter_route,
    )
    flattest_path = _path_for_profile(graph, start, goal, flattest_prefs)
    if flattest_path is not None:
        flattest = build_route_option(graph, flattest_path, "flattest", flattest_prefs)
        budget = fastest.metrics.time_s + user_prefs.max_extra_time_s_for_flatter_route
        if (
            tuple(flattest.edge_ids) not in {tuple(option.edge_ids) for option in candidates}
            and flattest.metrics.time_s <= budget
        ):
            candidates.append(flattest)

    candidates = _deduplicate(candidates)
    for index, option in enumerate(candidates):
        candidates[index].explanation = explain_route(option, fastest, user_prefs)

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
