from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from hashlib import sha256
from math import ceil
from typing import Literal

from pydantic import BaseModel, Field

from app.core.costs import prefs_for_mode
from app.core.models import Edge, Graph, RouteOption, UserPrefs


class LatLon(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class PreferencesIn(BaseModel):
    mode: Literal["fastest", "balanced", "avoid_hills", "accessibility", "custom"] = "balanced"
    flat_speed_mps: float | None = Field(default=None, gt=0)
    lambda_uphill: float | None = Field(default=None, ge=0)
    lambda_downhill: float | None = Field(default=None, ge=0)
    lambda_max_grade: float | None = Field(default=None, ge=0)
    lambda_safety: float | None = Field(default=None, ge=0)
    lambda_barrier: float | None = Field(default=None, ge=0)
    lambda_uncertainty: float | None = Field(default=None, ge=0)
    soft_max_grade: float | None = Field(default=None, ge=0)
    hard_max_grade: float | None = Field(default=None, ge=0)
    max_extra_time_s_for_flatter_route: int | None = Field(default=None, ge=0)
    forbid_stairs: bool | None = None


class RouteRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    preferences: PreferencesIn = Field(default_factory=PreferencesIn)


class DebugRouteRequest(BaseModel):
    start_node: int = 1
    goal_node: int = 99
    preferences: PreferencesIn = Field(default_factory=PreferencesIn)


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=1, max_length=240)


class GeocodeResponse(BaseModel):
    query: str
    lat: float
    lon: float
    display_name: str


class GeocodeSuggestionOut(GeocodeResponse):
    place_id: str


class GeocodeSuggestionsResponse(BaseModel):
    suggestions: list[GeocodeSuggestionOut]


class LocationObservation(LatLon):
    accuracy_m: float | None = Field(default=None, ge=0)
    heading: float | None = Field(default=None, ge=0, le=360)
    speed_mps: float | None = Field(default=None, ge=0)
    observed_at: str | None = Field(default=None, max_length=80)


class RouteFeedbackRequest(BaseModel):
    feedback_type: Literal[
        "good_route",
        "weird_turn",
        "too_steep",
        "unsafe",
        "bad_name",
        "other",
    ]
    graph_version: str | None = Field(default=None, max_length=120)
    route_label: str | None = Field(default=None, max_length=80)
    route_edge_ids: list[int] = Field(default_factory=list, max_length=10_000)
    direction_street_names: list[str | None] = Field(default_factory=list, max_length=500)
    origin_address: str | None = Field(default=None, max_length=240)
    destination_address: str | None = Field(default=None, max_length=240)
    origin: LatLon | None = None
    destination: LatLon | None = None
    current_position: LocationObservation | None = None
    active_step_index: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1_000)
    route_id: str | None = Field(default=None, max_length=120)
    step_id: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)


class RouteFeedbackResponse(BaseModel):
    feedback_id: str
    saved_at: str
    path: str
    duplicate: bool = False


class RouteMetricsOut(BaseModel):
    time_s: float
    distance_m: float
    gain_m: float
    loss_m: float
    max_uphill_grade: float
    max_downhill_grade: float
    max_abs_grade: float
    hill_discomfort: float
    downhill_discomfort: float
    safety_penalty: float
    barrier_penalty: float
    uncertainty_penalty: float
    route_score: float


class HillEventOut(BaseModel):
    street_name: str | None
    start_dist_m: float
    end_dist_m: float
    length_m: float
    direction: Literal["uphill", "downhill"]
    elevation_change_m: float
    average_grade: float
    max_sustained_grade: float
    length_above_8pct_m: float
    length_above_10pct_m: float


class DirectionStepOut(BaseModel):
    step_id: str
    maneuver: Literal["depart", "continue", "turn_left", "turn_right", "u_turn"]
    start_distance_m: float
    end_distance_m: float
    instruction: str
    street_name: str | None
    distance_m: float
    time_s: float
    gain_m: float
    loss_m: float
    max_uphill_grade: float
    geometry: list[tuple[float, float]]


class RouteBoundsOut(BaseModel):
    south: float
    west: float
    north: float
    east: float


class RouteComparisonOut(BaseModel):
    extra_time_s: float
    extra_distance_m: float
    gain_delta_m: float
    max_uphill_grade_delta: float
    avoided_10pct_uphill_m: float


class RouteRecommendationOut(BaseModel):
    title: str
    summary: str
    badge: str
    reason_codes: list[str]


class ElevationProfilePointOut(BaseModel):
    distance_m: float
    elevation_m: float
    grade: float


class RouteDataQualityOut(BaseModel):
    elevation_coverage: float
    sidewalk_coverage: float
    wheelchair_coverage: float
    name_coverage: float
    has_stairs: bool


class RouteOptionOut(BaseModel):
    route_id: str
    label: str
    title: str
    badge: str
    edge_ids: list[int]
    geometry: list[tuple[float, float]]
    bounds: RouteBoundsOut
    metrics: RouteMetricsOut
    comparison: RouteComparisonOut
    recommendation: RouteRecommendationOut
    elevation_profile: list[ElevationProfilePointOut]
    data_quality: RouteDataQualityOut
    warnings: list[str]
    hill_events: list[HillEventOut]
    directions: list[DirectionStepOut]
    explanation: str


class RouteResponse(BaseModel):
    routes: list[RouteOptionOut]
    graph_version: str
    recommended_route_id: str


class HealthResponse(BaseModel):
    status: str
    graph_version: str
    production_graph_loaded: bool
    graph_status: Literal["unconfigured", "missing", "available", "ready"]
    route_ready: bool


def preferences_to_user_prefs(preferences: PreferencesIn) -> UserPrefs:
    base = prefs_for_mode(preferences.mode)
    overrides = preferences.model_dump(exclude_none=True)
    return replace(base, **overrides)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _maneuver(
    instruction: str, index: int
) -> Literal["depart", "continue", "turn_left", "turn_right", "u_turn"]:
    if index == 0:
        return "depart"
    normalized = instruction.casefold()
    if "turn right" in normalized:
        return "turn_right"
    if "turn left" in normalized:
        return "turn_left"
    if "turn around" in normalized:
        return "u_turn"
    return "continue"


def _route_bounds(option: RouteOption) -> RouteBoundsOut:
    if not option.geometry:
        return RouteBoundsOut(south=0.0, west=0.0, north=0.0, east=0.0)
    lons = [point[0] for point in option.geometry]
    lats = [point[1] for point in option.geometry]
    return RouteBoundsOut(south=min(lats), west=min(lons), north=max(lats), east=max(lons))


def _steep_uphill_m(option: RouteOption) -> float:
    return sum(event.length_above_10pct_m for event in option.hill_events)


def _comparison(option: RouteOption, fastest: RouteOption) -> RouteComparisonOut:
    return RouteComparisonOut(
        extra_time_s=option.metrics.time_s - fastest.metrics.time_s,
        extra_distance_m=option.metrics.distance_m - fastest.metrics.distance_m,
        gain_delta_m=option.metrics.gain_m - fastest.metrics.gain_m,
        max_uphill_grade_delta=(option.metrics.max_uphill_grade - fastest.metrics.max_uphill_grade),
        avoided_10pct_uphill_m=max(0.0, _steep_uphill_m(fastest) - _steep_uphill_m(option)),
    )


def _recommendation(
    option: RouteOption,
    fastest: RouteOption,
    comparison: RouteComparisonOut,
) -> RouteRecommendationOut:
    reasons: list[str] = []
    if comparison.avoided_10pct_uphill_m > 5.0:
        reasons.append("avoids_steepest_climb")
    if comparison.max_uphill_grade_delta < -0.01:
        reasons.append("lower_max_grade")
    if 0 < comparison.extra_time_s <= 300:
        reasons.append("small_time_tradeoff")
    if option.metrics.distance_m <= fastest.metrics.distance_m:
        reasons.append("no_distance_penalty")

    if option.label == "recommended":
        title = "Gentler route" if "lower_max_grade" in reasons else "Recommended walk"
        badge = "Best balance"
    elif option.label == "flattest":
        title = "Gentlest route"
        badge = "Gentlest"
    elif option.label == "accessible":
        title = "Avoids stairs"
        badge = "Accessibility"
        reasons.append("avoids_stairs")
    else:
        title = "Fastest route"
        badge = "Fastest"
        reasons.append("fastest")
    return RouteRecommendationOut(
        title=title,
        summary=option.explanation,
        badge=badge,
        reason_codes=list(dict.fromkeys(reasons)),
    )


def _edge_has_elevation(edge: Edge, graph: Graph) -> bool:
    if len(edge.samples) >= 2:
        return True
    source = graph.nodes.get(edge.source)
    target = graph.nodes.get(edge.target)
    return bool(source and target and source.z_m is not None and target.z_m is not None)


def _coverage_length(edges: list[Edge], predicate: Callable[[Edge], bool]) -> float:
    total = sum(edge.length_m for edge in edges)
    if total <= 0:
        return 0.0
    covered = sum(edge.length_m for edge in edges if predicate(edge))
    return min(1.0, max(0.0, covered / total))


def _route_data_quality(graph: Graph, option: RouteOption) -> RouteDataQualityOut:
    edges = graph.route_edges(option.edge_ids)
    return RouteDataQualityOut(
        elevation_coverage=_coverage_length(edges, lambda edge: _edge_has_elevation(edge, graph)),
        sidewalk_coverage=_coverage_length(
            edges, lambda edge: edge.sidewalk_availability not in {None, "", "unknown"}
        ),
        wheelchair_coverage=_coverage_length(
            edges, lambda edge: edge.wheelchair_access not in {None, "", "unknown"}
        ),
        name_coverage=_coverage_length(
            edges, lambda edge: bool(edge.display_name or edge.street_name)
        ),
        has_stairs=any(edge.stairs for edge in edges),
    )


def _route_warnings(option: RouteOption, quality: RouteDataQualityOut) -> list[str]:
    warnings: list[str] = []
    if quality.has_stairs:
        warnings.append("Includes stairs.")
    if quality.elevation_coverage < 0.8:
        warnings.append("Elevation coverage is incomplete on part of this route.")
    if option.label == "accessible" and quality.wheelchair_coverage < 0.8:
        warnings.append("Wheelchair and curb-ramp coverage is incomplete.")
    return warnings


def _raw_elevation_profile(graph: Graph, option: RouteOption) -> list[ElevationProfilePointOut]:
    points: list[ElevationProfilePointOut] = []
    cumulative_m = 0.0
    for edge in graph.route_edges(option.edge_ids):
        if edge.samples:
            sample_start_m = edge.samples[0].dist_m
            for sample in edge.samples:
                distance_m = cumulative_m + max(0.0, sample.dist_m - sample_start_m)
                grade = sample.rolling_grade_20m
                if grade is None:
                    grade = sample.grade if sample.grade is not None else edge.mean_grade
                if points and abs(points[-1].distance_m - distance_m) < 0.01:
                    continue
                points.append(
                    ElevationProfilePointOut(
                        distance_m=distance_m,
                        elevation_m=sample.z_smooth_m,
                        grade=grade,
                    )
                )
        else:
            source = graph.nodes.get(edge.source)
            target = graph.nodes.get(edge.target)
            if (
                source
                and source.z_m is not None
                and (not points or abs(points[-1].distance_m - cumulative_m) >= 0.01)
            ):
                points.append(
                    ElevationProfilePointOut(
                        distance_m=cumulative_m,
                        elevation_m=source.z_m,
                        grade=edge.mean_grade,
                    )
                )
            if target and target.z_m is not None:
                points.append(
                    ElevationProfilePointOut(
                        distance_m=cumulative_m + edge.length_m,
                        elevation_m=target.z_m,
                        grade=edge.mean_grade,
                    )
                )
        cumulative_m += edge.length_m
    return points


def _elevation_profile(
    graph: Graph,
    option: RouteOption,
    max_points: int = 96,
) -> list[ElevationProfilePointOut]:
    points = _raw_elevation_profile(graph, option)
    if len(points) <= max_points:
        return points
    stride = ceil((len(points) - 1) / (max_points - 1))
    sampled = points[::stride]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def route_option_to_out(
    option: RouteOption,
    *,
    graph: Graph,
    fastest: RouteOption,
) -> RouteOptionOut:
    route_id = _stable_id("route", graph.version, *option.edge_ids)
    comparison = _comparison(option, fastest)
    recommendation = _recommendation(option, fastest, comparison)
    quality = _route_data_quality(graph, option)
    cumulative_m = 0.0
    directions: list[DirectionStepOut] = []
    for index, step in enumerate(option.directions):
        start_distance_m = cumulative_m
        cumulative_m += step.distance_m
        directions.append(
            DirectionStepOut(
                step_id=_stable_id("step", route_id, index, step.street_name or ""),
                maneuver=_maneuver(step.instruction, index),
                start_distance_m=start_distance_m,
                end_distance_m=cumulative_m,
                **asdict(step),
            )
        )
    return RouteOptionOut(
        route_id=route_id,
        label=option.label,
        title=recommendation.title,
        badge=recommendation.badge,
        edge_ids=option.edge_ids,
        geometry=option.geometry,
        bounds=_route_bounds(option),
        metrics=RouteMetricsOut(**asdict(option.metrics)),
        comparison=comparison,
        recommendation=recommendation,
        elevation_profile=_elevation_profile(graph, option),
        data_quality=quality,
        warnings=_route_warnings(option, quality),
        hill_events=[HillEventOut(**asdict(event)) for event in option.hill_events],
        directions=directions,
        explanation=option.explanation,
    )
