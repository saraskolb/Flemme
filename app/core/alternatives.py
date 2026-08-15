from __future__ import annotations

from dataclasses import replace
from heapq import heappop, heappush
from math import inf
from typing import Literal

from app.core.astar import astar, walking_time_heuristic
from app.core.costs import (
    AVOID_HILLS,
    FASTEST,
    edge_allowed,
    edge_cost,
    edge_time_s,
    effective_uphill_grade_for_cost,
    make_edge_cost,
    route_metrics,
)
from app.core.directions import build_directions
from app.core.edge_naming import edge_label
from app.core.explanations import detect_hill_events, explain_route
from app.core.models import Edge, Graph, RouteOption, UserPrefs
from app.core.route_reasonableness import choose_reasonable_recommendation

PEAK_GRADE_CANDIDATE_CAPS = (0.10, 0.12, 0.14, 0.16, 0.18, 0.20)
LOW_TURN_CANDIDATE_PENALTY_S = 90.0
VISIBLE_TURN_CANDIDATE_PENALTY_S = 90.0
VISIBLE_TURN_FRAGMENT_M = 12.0
PRACTICAL_EQUIVALENT_MAX_TIME_DELTA_S = 60.0
PRACTICAL_EQUIVALENT_MAX_DISTANCE_DELTA_M = 75.0
PRACTICAL_EQUIVALENT_MAX_STEEP_EXPOSURE_DELTA_M = 20.0


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
            edge_allowed(edge, prefs)
            and effective_uphill_grade_for_cost(edge) <= max_uphill_grade
        ),
    )


def _route_choice_key(edge: Edge) -> str:
    label = edge_label(edge)
    return label.text or label.key


def _path_with_turn_penalty(
    graph: Graph,
    start: int,
    goal: int,
    prefs: UserPrefs,
    turn_penalty_s: float = LOW_TURN_CANDIDATE_PENALTY_S,
) -> list[int] | None:
    if start not in graph.nodes or goal not in graph.nodes:
        return None
    if start == goal:
        return []

    heuristic = walking_time_heuristic(graph)
    start_state = (start, "")
    frontier: list[tuple[float, int, float, int, str]] = []
    sequence = 0
    heappush(frontier, (heuristic(start, goal), sequence, 0.0, start, ""))
    cost_so_far: dict[tuple[int, str], float] = {start_state: 0.0}
    came_from: dict[tuple[int, str], tuple[tuple[int, str], int]] = {}
    goal_state: tuple[int, str] | None = None

    while frontier:
        _, _, current_cost, current_node, previous_key = heappop(frontier)
        current_state = (current_node, previous_key)
        if current_cost != cost_so_far.get(current_state, inf):
            continue
        if current_node == goal:
            goal_state = current_state
            break

        for edge in graph.outgoing_edges(current_node):
            if not edge_allowed(edge, prefs):
                continue
            current_key = _route_choice_key(edge)
            change_cost = (
                turn_penalty_s
                if previous_key and current_key != previous_key
                else 0.0
            )
            next_cost = current_cost + edge_time_s(edge, FASTEST) + change_cost
            next_state = (edge.target, current_key)
            if next_cost < cost_so_far.get(next_state, inf):
                cost_so_far[next_state] = next_cost
                came_from[next_state] = (current_state, edge.edge_id)
                sequence += 1
                priority = next_cost + heuristic(edge.target, goal)
                heappush(
                    frontier,
                    (priority, sequence, next_cost, edge.target, current_key),
                )

    if goal_state is None:
        return None

    edge_ids: list[int] = []
    current_state = goal_state
    while current_state != start_state:
        previous_state, edge_id = came_from[current_state]
        edge_ids.append(edge_id)
        current_state = previous_state
    edge_ids.reverse()
    return edge_ids


def _visible_route_choice_key(previous_key: str, edge: Edge) -> str:
    if previous_key and edge.length_m <= VISIBLE_TURN_FRAGMENT_M:
        return previous_key
    return _route_choice_key(edge)


def _path_with_visible_turn_penalty(
    graph: Graph,
    start: int,
    goal: int,
    prefs: UserPrefs,
    turn_penalty_s: float = VISIBLE_TURN_CANDIDATE_PENALTY_S,
) -> list[int] | None:
    if start not in graph.nodes or goal not in graph.nodes:
        return None
    if start == goal:
        return []

    heuristic = walking_time_heuristic(graph)
    start_state = (start, "")
    frontier: list[tuple[float, int, float, int, str]] = []
    sequence = 0
    heappush(frontier, (heuristic(start, goal), sequence, 0.0, start, ""))
    cost_so_far: dict[tuple[int, str], float] = {start_state: 0.0}
    came_from: dict[tuple[int, str], tuple[tuple[int, str], int]] = {}
    goal_state: tuple[int, str] | None = None

    while frontier:
        _, _, current_cost, current_node, previous_key = heappop(frontier)
        current_state = (current_node, previous_key)
        if current_cost != cost_so_far.get(current_state, inf):
            continue
        if current_node == goal:
            goal_state = current_state
            break

        for edge in graph.outgoing_edges(current_node):
            if not edge_allowed(edge, prefs):
                continue
            current_key = _visible_route_choice_key(previous_key, edge)
            change_cost = (
                turn_penalty_s
                if previous_key and current_key != previous_key
                else 0.0
            )
            next_cost = current_cost + edge_cost(edge, prefs) + change_cost
            next_state = (edge.target, current_key)
            if next_cost < cost_so_far.get(next_state, inf):
                cost_so_far[next_state] = next_cost
                came_from[next_state] = (current_state, edge.edge_id)
                sequence += 1
                priority = next_cost + heuristic(edge.target, goal)
                heappush(
                    frontier,
                    (priority, sequence, next_cost, edge.target, current_key),
                )

    if goal_state is None:
        return None

    edge_ids: list[int] = []
    current_state = goal_state
    while current_state != start_state:
        previous_state, edge_id = came_from[current_state]
        edge_ids.append(edge_id)
        current_state = previous_state
    edge_ids.reverse()
    return edge_ids


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


def _direction_signature(option: RouteOption) -> tuple[str, ...]:
    return tuple(
        (step.street_name or "").strip().casefold()
        for step in option.directions
        if step.street_name
    )


def _uphill_10pct_distance_m(option: RouteOption) -> float:
    return sum(event.length_above_10pct_m for event in option.hill_events)


def _is_same_practical_route(candidate: RouteOption, fastest: RouteOption) -> bool:
    candidate_signature = _direction_signature(candidate)
    fastest_signature = _direction_signature(fastest)
    if not candidate_signature or candidate_signature != fastest_signature:
        return False

    time_delta_s = abs(candidate.metrics.time_s - fastest.metrics.time_s)
    distance_delta_m = abs(candidate.metrics.distance_m - fastest.metrics.distance_m)
    steep_exposure_delta_m = abs(
        _uphill_10pct_distance_m(candidate) - _uphill_10pct_distance_m(fastest)
    )
    return (
        time_delta_s <= PRACTICAL_EQUIVALENT_MAX_TIME_DELTA_S
        and distance_delta_m <= PRACTICAL_EQUIVALENT_MAX_DISTANCE_DELTA_M
        and steep_exposure_delta_m <= PRACTICAL_EQUIVALENT_MAX_STEEP_EXPOSURE_DELTA_M
    )


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

    low_turn_path = _path_with_turn_penalty(graph, start, goal, prefs)
    if low_turn_path is not None:
        candidates.append(_candidate_option(graph, low_turn_path, prefs))

    visible_turn_path = _path_with_visible_turn_penalty(graph, start, goal, prefs)
    if visible_turn_path is not None:
        candidates.append(_candidate_option(graph, visible_turn_path, prefs))

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
    fastest_is_flattest = False
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
            recommended_option = build_route_option(
                graph,
                recommended.edge_ids,
                "recommended",
                user_prefs,
            )
            if _is_same_practical_route(recommended_option, fastest):
                fastest_is_flattest = True
            else:
                candidates.append(recommended_option)
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
        if tuple(flattest_path) == tuple(fastest_path) or _is_same_practical_route(
            flattest,
            fastest,
        ):
            fastest_is_flattest = True
        elif (
            tuple(flattest.edge_ids) not in {tuple(option.edge_ids) for option in candidates}
            and flattest.metrics.time_s <= budget
        ):
            candidates.append(flattest)

    candidates = _deduplicate(candidates)
    for index, option in enumerate(candidates):
        candidates[index].explanation = explain_route(
            option,
            fastest,
            user_prefs,
            fastest_is_flattest=fastest_is_flattest,
        )

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
