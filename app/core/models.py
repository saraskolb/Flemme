from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

Coordinate = tuple[float, float]


@dataclass(slots=True)
class Node:
    node_id: int
    lon: float
    lat: float
    x: float | None = None
    y: float | None = None
    z_m: float | None = None
    node_type: str = "intersection"


@dataclass(slots=True)
class ElevationSample:
    dist_m: float
    z_raw_m: float
    z_smooth_m: float
    grade: float | None = None
    rolling_grade_20m: float | None = None
    rolling_grade_50m: float | None = None


@dataclass(slots=True)
class Edge:
    edge_id: int
    source: int
    target: int
    geometry: list[Coordinate]
    length_m: float
    street_name: str | None = None
    edge_type: str = "sidewalk"
    access: str = "unknown"
    sidewalk_availability: str | None = None
    sidewalk_width_m: float | None = None
    wheelchair_access: str | None = None
    stairs: bool = False
    surface: str | None = None
    samples: list[ElevationSample] = field(default_factory=list)
    gain_m: float = 0.0
    loss_m: float = 0.0
    mean_grade: float = 0.0
    max_uphill_grade: float = 0.0
    max_downhill_grade: float = 0.0
    max_abs_grade: float = 0.0
    sustained_uphill_grade_20m: float = 0.0
    sustained_downhill_grade_20m: float = 0.0
    sustained_uphill_grade_50m: float = 0.0
    sustained_downhill_grade_50m: float = 0.0
    length_above_6pct_up_m: float = 0.0
    length_above_8pct_up_m: float = 0.0
    length_above_10pct_up_m: float = 0.0
    length_above_12pct_up_m: float = 0.0
    base_time_s: float = 0.0
    slope_time_s: float = 0.0
    traffic_safety_score: float = 0.0
    barrier_penalty: float = 0.0
    uncertainty_penalty: float = 0.0
    osm_way_id: int | None = None
    source_tags: dict[str, str] = field(default_factory=dict)
    display_name: str | None = None
    name_source: str = "unknown"
    source_dataset: str | None = None
    source_feature_id: str | None = None
    name_confidence: float = 0.0
    name_status: str = "unknown"


@dataclass(slots=True)
class UserPrefs:
    mode: Literal["fastest", "balanced", "avoid_hills", "accessibility", "custom"] = "balanced"
    flat_speed_mps: float = 1.34
    lambda_uphill: float = 1.50
    lambda_downhill: float = 0.70
    lambda_max_grade: float = 1.00
    lambda_safety: float = 1.00
    lambda_barrier: float = 1.50
    lambda_uncertainty: float = 0.50
    soft_max_grade: float = 0.10
    hard_max_grade: float | None = None
    max_extra_time_s_for_flatter_route: int = 300
    forbid_stairs: bool = False


@dataclass(slots=True)
class RouteMetrics:
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


@dataclass(slots=True)
class HillEvent:
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


@dataclass(slots=True)
class DirectionStep:
    instruction: str
    street_name: str | None
    distance_m: float
    time_s: float
    gain_m: float
    loss_m: float
    max_uphill_grade: float
    geometry: list[Coordinate]


@dataclass(slots=True)
class RouteOption:
    label: Literal["fastest", "balanced", "flattest", "recommended", "accessible"]
    edge_ids: list[int]
    geometry: list[Coordinate]
    metrics: RouteMetrics
    hill_events: list[HillEvent] = field(default_factory=list)
    directions: list[DirectionStep] = field(default_factory=list)
    explanation: str = ""


EdgeCost = Callable[[Edge], float]
Heuristic = Callable[[int, int], float]
EdgeAllowed = Callable[[Edge], bool]


@dataclass(slots=True)
class Graph:
    nodes: dict[int, Node]
    edges: dict[int, Edge]
    version: str = "dev-synthetic-001"
    adjacency: dict[int, list[Edge]] = field(init=False)

    def __post_init__(self) -> None:
        adjacency: dict[int, list[Edge]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges.values():
            adjacency.setdefault(edge.source, []).append(edge)
        for source_edges in adjacency.values():
            source_edges.sort(key=lambda edge: edge.edge_id)
        self.adjacency = adjacency

    def outgoing_edges(self, node_id: int) -> list[Edge]:
        return self.adjacency.get(node_id, [])

    def route_edges(self, edge_ids: list[int]) -> list[Edge]:
        return [self.edges[edge_id] for edge_id in edge_ids]
