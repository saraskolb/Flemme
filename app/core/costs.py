from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from math import inf

from app.core.models import Edge, RouteMetrics, UserPrefs

FASTEST = UserPrefs(
    mode="fastest",
    lambda_uphill=0.25,
    lambda_downhill=0.10,
    lambda_max_grade=0.25,
    lambda_safety=0.50,
    lambda_barrier=1.00,
    lambda_uncertainty=0.25,
)

BALANCED = UserPrefs(
    mode="balanced",
    lambda_uphill=1.50,
    lambda_downhill=0.70,
    lambda_max_grade=1.00,
    lambda_safety=1.00,
    lambda_barrier=1.50,
    lambda_uncertainty=0.50,
)

AVOID_HILLS = UserPrefs(
    mode="avoid_hills",
    lambda_uphill=4.00,
    lambda_downhill=2.00,
    lambda_max_grade=2.00,
    lambda_safety=1.00,
    lambda_barrier=1.50,
    lambda_uncertainty=0.50,
    hard_max_grade=0.10,
)

ACCESSIBILITY = UserPrefs(
    mode="accessibility",
    lambda_uphill=5.00,
    lambda_downhill=3.00,
    lambda_max_grade=3.00,
    lambda_safety=1.25,
    lambda_barrier=5.00,
    lambda_uncertainty=1.00,
    hard_max_grade=0.083,
    forbid_stairs=True,
)


def prefs_for_mode(mode: str) -> UserPrefs:
    if mode == "fastest":
        return replace(FASTEST)
    if mode == "avoid_hills":
        return replace(AVOID_HILLS)
    if mode == "accessibility":
        return replace(ACCESSIBILITY)
    if mode == "custom":
        return replace(BALANCED, mode="custom")
    return replace(BALANCED)


def uphill_penalty_curve(g: float) -> float:
    g = max(0.0, g)
    if g <= 0.06:
        return 0.0
    if g <= 0.10:
        return ((g - 0.06) / 0.04) ** 2
    return 1.0 + 3.0 * ((g - 0.10) / 0.06) ** 2


def downhill_penalty_curve(g: float) -> float:
    g = max(0.0, g)
    if g <= 0.08:
        return 0.0
    if g <= 0.12:
        return ((g - 0.08) / 0.04) ** 2
    return 1.0 + 2.0 * ((g - 0.12) / 0.08) ** 2


def max_grade_penalty(
    max_abs_grade: float, soft: float = 0.10, hard: float = 0.16, tau_s: float = 90.0
) -> float:
    max_abs_grade = max(0.0, max_abs_grade)
    if max_abs_grade <= soft:
        return 0.0
    x = (max_abs_grade - soft) / max(hard - soft, 1e-9)
    return tau_s * x * x


def edge_time_s(edge: Edge, prefs: UserPrefs) -> float:
    precomputed = edge.base_time_s + edge.slope_time_s
    if precomputed > 0:
        return precomputed
    return edge.length_m / max(prefs.flat_speed_mps, 1e-9)


def uphill_discomfort(edge: Edge) -> float:
    uphill_grade = max(edge.sustained_uphill_grade_20m, edge.sustained_uphill_grade_50m)
    uphill_grade = max(uphill_grade, edge.max_uphill_grade)
    steep_length = edge.length_above_6pct_up_m
    if steep_length <= 0 and uphill_grade > 0.06:
        steep_length = edge.length_m
    return max(0.0, steep_length * uphill_penalty_curve(uphill_grade) * 0.20)


def downhill_discomfort(edge: Edge) -> float:
    downhill_grade = max(edge.sustained_downhill_grade_20m, edge.sustained_downhill_grade_50m)
    downhill_grade = max(downhill_grade, edge.max_downhill_grade)
    if downhill_grade <= 0.08:
        return 0.0
    return max(0.0, edge.length_m * downhill_penalty_curve(downhill_grade) * 0.15)


def edge_allowed(edge: Edge, prefs: UserPrefs) -> bool:
    if prefs.forbid_stairs and edge.stairs:
        return False
    if prefs.hard_max_grade is not None and edge.max_abs_grade > prefs.hard_max_grade:
        return False
    if prefs.mode == "accessibility":
        if edge.stairs:
            return False
        if edge.wheelchair_access == "no":
            return False
        if edge.sidewalk_availability == "none":
            return False
        if edge.sidewalk_width_m is not None and edge.sidewalk_width_m < 1.2:
            return False
    return True


def edge_cost(edge: Edge, prefs: UserPrefs) -> float:
    if not edge_allowed(edge, prefs):
        return inf

    hard = prefs.hard_max_grade if prefs.hard_max_grade is not None else 0.16
    score = (
        edge_time_s(edge, prefs)
        + prefs.lambda_uphill * uphill_discomfort(edge)
        + prefs.lambda_downhill * downhill_discomfort(edge)
        + prefs.lambda_max_grade
        * max_grade_penalty(edge.max_abs_grade, soft=prefs.soft_max_grade, hard=hard)
        + prefs.lambda_safety * max(0.0, edge.traffic_safety_score)
        + prefs.lambda_barrier * max(0.0, edge.barrier_penalty)
        + prefs.lambda_uncertainty * max(0.0, edge.uncertainty_penalty)
    )
    return max(0.0, score)


def make_edge_cost(prefs: UserPrefs) -> Callable[[Edge], float]:
    return lambda edge: edge_cost(edge, prefs)


def route_metrics(edges: list[Edge], prefs: UserPrefs) -> RouteMetrics:
    time_s = sum(edge_time_s(edge, prefs) for edge in edges)
    distance_m = sum(edge.length_m for edge in edges)
    gain_m = sum(edge.gain_m for edge in edges)
    loss_m = sum(edge.loss_m for edge in edges)
    max_uphill_grade = max((edge.max_uphill_grade for edge in edges), default=0.0)
    max_downhill_grade = max((edge.max_downhill_grade for edge in edges), default=0.0)
    max_abs_grade = max((edge.max_abs_grade for edge in edges), default=0.0)
    hill = sum(uphill_discomfort(edge) for edge in edges)
    downhill = sum(downhill_discomfort(edge) for edge in edges)
    safety = sum(max(0.0, edge.traffic_safety_score) for edge in edges)
    barrier = sum(max(0.0, edge.barrier_penalty) for edge in edges)
    uncertainty = sum(max(0.0, edge.uncertainty_penalty) for edge in edges)
    score = sum(edge_cost(edge, prefs) for edge in edges)

    return RouteMetrics(
        time_s=time_s,
        distance_m=distance_m,
        gain_m=gain_m,
        loss_m=loss_m,
        max_uphill_grade=max_uphill_grade,
        max_downhill_grade=max_downhill_grade,
        max_abs_grade=max_abs_grade,
        hill_discomfort=hill,
        downhill_discomfort=downhill,
        safety_penalty=safety,
        barrier_penalty=barrier,
        uncertainty_penalty=uncertainty,
        route_score=score,
    )
