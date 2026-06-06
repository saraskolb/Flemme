from __future__ import annotations

from dataclasses import asdict, replace
from typing import Literal

from pydantic import BaseModel, Field

from app.core.costs import prefs_for_mode
from app.core.models import RouteOption, UserPrefs


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
    instruction: str
    street_name: str | None
    distance_m: float
    time_s: float
    gain_m: float
    loss_m: float
    max_uphill_grade: float
    geometry: list[tuple[float, float]]


class RouteOptionOut(BaseModel):
    label: str
    edge_ids: list[int]
    geometry: list[tuple[float, float]]
    metrics: RouteMetricsOut
    hill_events: list[HillEventOut]
    directions: list[DirectionStepOut]
    explanation: str


class RouteResponse(BaseModel):
    routes: list[RouteOptionOut]
    graph_version: str


class HealthResponse(BaseModel):
    status: str
    graph_version: str
    production_graph_loaded: bool


def preferences_to_user_prefs(preferences: PreferencesIn) -> UserPrefs:
    base = prefs_for_mode(preferences.mode)
    overrides = preferences.model_dump(exclude_none=True)
    return replace(base, **overrides)


def route_option_to_out(option: RouteOption) -> RouteOptionOut:
    return RouteOptionOut(
        label=option.label,
        edge_ids=option.edge_ids,
        geometry=option.geometry,
        metrics=RouteMetricsOut(**asdict(option.metrics)),
        hill_events=[HillEventOut(**asdict(event)) for event in option.hill_events],
        directions=[DirectionStepOut(**asdict(step)) for step in option.directions],
        explanation=option.explanation,
    )
