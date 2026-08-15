from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from app.core.costs import effective_uphill_grade_for_cost, uphill_discomfort
from app.core.models import Coordinate, Edge, RouteOption

DEFAULT_EXTRA_TIME_RATIO = 0.25
MIN_EXTRA_TIME_S = 4 * 60.0
MAX_EXTRA_TIME_S = 8 * 60.0
MAX_DISTANCE_RATIO = 1.35
MAX_DIRECTNESS_RATIO = 1.45
MAX_DIRECTNESS_DELTA = 0.30
MAX_DIRECTION_STEP_RATIO = 1.75
MIN_MEANINGFUL_HILL_BENEFIT = 20.0
EXTRA_MINUTE_PENALTY = 25.0
DISTANCE_SHAPE_FREE_RATIO = 1.20
DIRECTNESS_SHAPE_FREE_RATIO = 1.40
DIRECTNESS_SHAPE_FREE_DELTA = 0.10
DIRECTION_STEP_FREE_DELTA = 2
EXTRA_DIRECTION_STEP_PENALTY = 12.0
SIMPLER_DIRECTION_STEP_BONUS = 8.0


@dataclass(frozen=True)
class UphillExposure:
    above_6pct_m: float
    above_8pct_m: float
    above_10pct_m: float
    above_12pct_m: float


@dataclass(frozen=True)
class RouteDiagnostics:
    time_delta_s: float
    time_ratio: float
    distance_delta_m: float
    distance_ratio: float
    directness_ratio: float
    directness_delta: float
    direction_step_delta: int
    direction_step_ratio: float
    max_uphill_grade_reduction: float
    hill_discomfort_saved: float
    exposure_saved: UphillExposure
    hill_benefit_score: float
    simplicity_bonus: float
    shape_penalty: float
    turn_penalty: float
    tradeoff_score: float
    time_budget_s: float
    within_time_budget: bool
    within_distance_budget: bool
    within_shape_budget: bool
    within_direction_budget: bool
    has_meaningful_hill_benefit: bool

    @property
    def is_reasonable_recommendation(self) -> bool:
        return (
            self.within_time_budget
            and self.within_distance_budget
            and self.within_shape_budget
            and self.within_direction_budget
            and self.has_meaningful_hill_benefit
            and self.tradeoff_score > 0.0
        )


def dynamic_extra_time_budget_s(fastest: RouteOption) -> float:
    ratio_budget = fastest.metrics.time_s * DEFAULT_EXTRA_TIME_RATIO
    return min(MAX_EXTRA_TIME_S, max(MIN_EXTRA_TIME_S, ratio_budget))


def route_time_budget_s(fastest: RouteOption) -> float:
    return fastest.metrics.time_s + dynamic_extra_time_budget_s(fastest)


def route_uphill_exposure(edges: list[Edge]) -> UphillExposure:
    return UphillExposure(
        above_6pct_m=sum(edge.length_above_6pct_up_m for edge in edges),
        above_8pct_m=sum(edge.length_above_8pct_up_m for edge in edges),
        above_10pct_m=sum(edge.length_above_10pct_up_m for edge in edges),
        above_12pct_m=sum(edge.length_above_12pct_up_m for edge in edges),
    )


def _route_effective_max_uphill_grade(edges: list[Edge]) -> float:
    if not edges:
        return 0.0
    return max(effective_uphill_grade_for_cost(edge) for edge in edges)


def _straight_line_distance_m(start: Coordinate, goal: Coordinate) -> float:
    lon1, lat1 = start
    lon2, lat2 = goal
    earth_radius_m = 6_371_000.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    haversine = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * earth_radius_m * asin(sqrt(haversine))


def route_directness_ratio(option: RouteOption) -> float:
    if len(option.geometry) < 2:
        return 1.0
    straight_line_m = _straight_line_distance_m(option.geometry[0], option.geometry[-1])
    if straight_line_m <= 0:
        return 1.0
    return max(1.0, option.metrics.distance_m / straight_line_m)


def _max_extra_direction_steps(fastest: RouteOption) -> int:
    return max(4, round(len(fastest.directions) * 0.5))


def _exposure_saved(candidate: UphillExposure, fastest: UphillExposure) -> UphillExposure:
    return UphillExposure(
        above_6pct_m=fastest.above_6pct_m - candidate.above_6pct_m,
        above_8pct_m=fastest.above_8pct_m - candidate.above_8pct_m,
        above_10pct_m=fastest.above_10pct_m - candidate.above_10pct_m,
        above_12pct_m=fastest.above_12pct_m - candidate.above_12pct_m,
    )


def _hill_benefit_score(
    candidate: RouteOption,
    fastest: RouteOption,
    candidate_edges: list[Edge],
    fastest_edges: list[Edge],
) -> tuple[float, UphillExposure, float, float]:
    candidate_exposure = route_uphill_exposure(candidate_edges)
    fastest_exposure = route_uphill_exposure(fastest_edges)
    exposure_saved = _exposure_saved(candidate_exposure, fastest_exposure)
    max_grade_reduction = _route_effective_max_uphill_grade(
        fastest_edges
    ) - _route_effective_max_uphill_grade(candidate_edges)
    discomfort_saved = sum(uphill_discomfort(edge) for edge in fastest_edges) - sum(
        uphill_discomfort(edge) for edge in candidate_edges
    )
    score = (
        max(0.0, discomfort_saved)
        + max(0.0, max_grade_reduction) * 600.0
        + max(0.0, exposure_saved.above_6pct_m) * 0.25
        + max(0.0, exposure_saved.above_8pct_m)
        + max(0.0, exposure_saved.above_10pct_m) * 2.0
        + max(0.0, exposure_saved.above_12pct_m) * 3.0
    )
    return score, exposure_saved, max_grade_reduction, discomfort_saved


def diagnose_route(
    candidate: RouteOption,
    fastest: RouteOption,
    candidate_edges: list[Edge],
    fastest_edges: list[Edge],
    time_budget_s: float | None = None,
) -> RouteDiagnostics:
    budget = time_budget_s if time_budget_s is not None else route_time_budget_s(fastest)
    time_delta_s = candidate.metrics.time_s - fastest.metrics.time_s
    time_ratio = (
        candidate.metrics.time_s / fastest.metrics.time_s if fastest.metrics.time_s > 0 else 1.0
    )
    distance_delta_m = candidate.metrics.distance_m - fastest.metrics.distance_m
    distance_ratio = (
        candidate.metrics.distance_m / fastest.metrics.distance_m
        if fastest.metrics.distance_m > 0
        else 1.0
    )
    directness = route_directness_ratio(candidate)
    fastest_directness = route_directness_ratio(fastest)
    directness_limit = max(MAX_DIRECTNESS_RATIO, fastest_directness + MAX_DIRECTNESS_DELTA)
    directness_delta = directness - fastest_directness
    fastest_direction_steps = len(fastest.directions)
    direction_step_delta = len(candidate.directions) - fastest_direction_steps
    direction_step_ratio = (
        len(candidate.directions) / fastest_direction_steps
        if fastest_direction_steps > 0
        else 1.0
    )
    hill_benefit, exposure_saved, max_grade_reduction, discomfort_saved = _hill_benefit_score(
        candidate,
        fastest,
        candidate_edges,
        fastest_edges,
    )
    extra_minutes = max(0.0, time_delta_s) / 60.0
    shape_penalty = (
        max(0.0, distance_ratio - DISTANCE_SHAPE_FREE_RATIO) * 180.0
        + max(0.0, directness - DIRECTNESS_SHAPE_FREE_RATIO) * 180.0
        + max(0.0, directness_delta - DIRECTNESS_SHAPE_FREE_DELTA) * 120.0
    )
    turn_penalty = (
        max(0, direction_step_delta - DIRECTION_STEP_FREE_DELTA)
        * EXTRA_DIRECTION_STEP_PENALTY
    )
    simplicity_bonus = max(0, -direction_step_delta) * SIMPLER_DIRECTION_STEP_BONUS
    tradeoff_score = (
        hill_benefit
        + simplicity_bonus
        - extra_minutes * EXTRA_MINUTE_PENALTY
        - shape_penalty
        - turn_penalty
    )
    has_enough_direction_budget = direction_step_delta <= _max_extra_direction_steps(fastest)
    if fastest_direction_steps >= 4:
        has_enough_direction_budget = (
            has_enough_direction_budget
            and direction_step_ratio <= MAX_DIRECTION_STEP_RATIO
        )

    return RouteDiagnostics(
        time_delta_s=time_delta_s,
        time_ratio=time_ratio,
        distance_delta_m=distance_delta_m,
        distance_ratio=distance_ratio,
        directness_ratio=directness,
        directness_delta=directness_delta,
        direction_step_delta=direction_step_delta,
        direction_step_ratio=direction_step_ratio,
        max_uphill_grade_reduction=max_grade_reduction,
        hill_discomfort_saved=discomfort_saved,
        exposure_saved=exposure_saved,
        hill_benefit_score=hill_benefit,
        simplicity_bonus=simplicity_bonus,
        shape_penalty=shape_penalty,
        turn_penalty=turn_penalty,
        tradeoff_score=tradeoff_score,
        time_budget_s=budget,
        within_time_budget=candidate.metrics.time_s <= budget,
        within_distance_budget=distance_ratio <= MAX_DISTANCE_RATIO,
        within_shape_budget=(
            directness <= directness_limit
            and directness_delta <= MAX_DIRECTNESS_DELTA
        ),
        within_direction_budget=has_enough_direction_budget,
        has_meaningful_hill_benefit=hill_benefit >= MIN_MEANINGFUL_HILL_BENEFIT,
    )


def choose_reasonable_recommendation(
    candidates: list[RouteOption],
    fastest: RouteOption,
    candidate_edges: dict[tuple[int, ...], list[Edge]],
) -> RouteOption:
    fastest_edges = candidate_edges[tuple(fastest.edge_ids)]
    budget = route_time_budget_s(fastest)
    scored: list[tuple[RouteDiagnostics, RouteOption]] = []

    for candidate in candidates:
        if tuple(candidate.edge_ids) == tuple(fastest.edge_ids):
            continue
        diagnostics = diagnose_route(
            candidate,
            fastest,
            candidate_edges[tuple(candidate.edge_ids)],
            fastest_edges,
            time_budget_s=budget,
        )
        if diagnostics.is_reasonable_recommendation:
            scored.append((diagnostics, candidate))

    if not scored:
        return fastest

    return max(
        scored,
        key=lambda item: (
            item[0].tradeoff_score,
            -item[0].time_delta_s,
            -item[0].distance_delta_m,
        ),
    )[1]
