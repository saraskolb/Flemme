from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from app.core.edge_naming import ROAD_TYPES
from app.core.models import Graph, RouteOption

VAGUE_DIRECTION_TERMS = (
    "pedestrian path",
    "walkway",
    "unnamed street",
    "walking path",
)
SHORT_TURN_M = 18.0
LONG_GENERIC_EDGE_M = 30.0
LOW_OFFICIAL_CONFIDENCE = 0.45
MAJOR_ROAD_TYPES = ROAD_TYPES - {"pedestrian", "service", "unclassified"}


@dataclass(frozen=True)
class EdgeNameQualityReport:
    total_edges: int
    missing_display_name_edges: int
    datasf_named_edges: int
    osm_named_edges: int
    inferred_named_edges: int
    generic_connector_edges: int
    generic_unnamed_street_edges: int
    generic_stairs_edges: int
    generic_edge_type_edges: int
    generic_non_stairs_edges: int
    generic_unnamed_major_road_edges: int
    long_generic_connector_edges: int
    long_generic_unnamed_street_edges: int
    low_confidence_official_edges: int
    name_source_counts: dict[str, int]
    edge_type_counts: dict[str, int]

    @property
    def display_name_coverage(self) -> float:
        if self.total_edges == 0:
            return 1.0
        return 1.0 - (self.missing_display_name_edges / self.total_edges)

    @property
    def datasf_name_rate(self) -> float:
        if self.total_edges == 0:
            return 0.0
        return self.datasf_named_edges / self.total_edges

    @property
    def generic_non_stairs_rate(self) -> float:
        if self.total_edges == 0:
            return 0.0
        return self.generic_non_stairs_edges / self.total_edges

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["display_name_coverage"] = self.display_name_coverage
        payload["datasf_name_rate"] = self.datasf_name_rate
        payload["generic_non_stairs_rate"] = self.generic_non_stairs_rate
        return payload


@dataclass(frozen=True)
class GraphIntegrityIssue:
    kind: str
    edge_id: int
    message: str


@dataclass(frozen=True)
class DirectionQualityIssue:
    route_label: str
    step_index: int
    reason: str
    instruction: str
    distance_m: float


def audit_edge_name_quality(
    graph: Graph,
    long_edge_m: float = LONG_GENERIC_EDGE_M,
    low_confidence: float = LOW_OFFICIAL_CONFIDENCE,
) -> EdgeNameQualityReport:
    name_source_counts = Counter(edge.name_source for edge in graph.edges.values())
    edge_type_counts = Counter(edge.edge_type for edge in graph.edges.values())
    generic_non_stairs_edges = sum(
        1
        for edge in graph.edges.values()
        if edge.name_source.startswith("generic") and edge.name_source != "generic_stairs"
    )

    return EdgeNameQualityReport(
        total_edges=len(graph.edges),
        missing_display_name_edges=sum(1 for edge in graph.edges.values() if not edge.display_name),
        datasf_named_edges=name_source_counts["datasf_centerline"],
        osm_named_edges=name_source_counts["osm"],
        inferred_named_edges=name_source_counts["inferred_reachable_street"],
        generic_connector_edges=name_source_counts["generic_connector"],
        generic_unnamed_street_edges=name_source_counts["generic_unnamed_street"],
        generic_stairs_edges=name_source_counts["generic_stairs"],
        generic_edge_type_edges=name_source_counts["generic_edge_type"],
        generic_non_stairs_edges=generic_non_stairs_edges,
        generic_unnamed_major_road_edges=sum(
            1
            for edge in graph.edges.values()
            if edge.name_source == "generic_unnamed_street" and edge.edge_type in MAJOR_ROAD_TYPES
        ),
        long_generic_connector_edges=sum(
            1
            for edge in graph.edges.values()
            if edge.name_source == "generic_connector" and edge.length_m > long_edge_m
        ),
        long_generic_unnamed_street_edges=sum(
            1
            for edge in graph.edges.values()
            if edge.name_source == "generic_unnamed_street" and edge.length_m > long_edge_m
        ),
        low_confidence_official_edges=sum(
            1
            for edge in graph.edges.values()
            if edge.name_source == "datasf_centerline" and edge.name_confidence < low_confidence
        ),
        name_source_counts=dict(sorted(name_source_counts.items())),
        edge_type_counts=dict(sorted(edge_type_counts.items())),
    )


def audit_graph_integrity(graph: Graph) -> list[GraphIntegrityIssue]:
    issues: list[GraphIntegrityIssue] = []
    for edge in graph.edges.values():
        if edge.source not in graph.nodes:
            issues.append(
                GraphIntegrityIssue(
                    kind="missing_source_node",
                    edge_id=edge.edge_id,
                    message=f"Edge {edge.edge_id} source node {edge.source} is missing.",
                )
            )
        if edge.target not in graph.nodes:
            issues.append(
                GraphIntegrityIssue(
                    kind="missing_target_node",
                    edge_id=edge.edge_id,
                    message=f"Edge {edge.edge_id} target node {edge.target} is missing.",
                )
            )
        if len(edge.geometry) < 2:
            issues.append(
                GraphIntegrityIssue(
                    kind="short_geometry",
                    edge_id=edge.edge_id,
                    message=f"Edge {edge.edge_id} geometry has fewer than two coordinates.",
                )
            )
        if edge.length_m <= 0:
            issues.append(
                GraphIntegrityIssue(
                    kind="nonpositive_length",
                    edge_id=edge.edge_id,
                    message=f"Edge {edge.edge_id} length is not positive.",
                )
            )
    return issues


def audit_route_direction_quality(
    routes: list[RouteOption],
    short_turn_m: float = SHORT_TURN_M,
    vague_terms: tuple[str, ...] = VAGUE_DIRECTION_TERMS,
) -> list[DirectionQualityIssue]:
    issues: list[DirectionQualityIssue] = []
    for route in routes:
        for index, step in enumerate(route.directions, start=1):
            normalized = step.instruction.casefold()
            for term in vague_terms:
                if term in normalized:
                    issues.append(
                        DirectionQualityIssue(
                            route_label=route.label,
                            step_index=index,
                            reason=f"vague_term:{term}",
                            instruction=step.instruction,
                            distance_m=step.distance_m,
                        )
                    )
            if not step.street_name:
                issues.append(
                    DirectionQualityIssue(
                        route_label=route.label,
                        step_index=index,
                        reason="missing_street_name",
                        instruction=step.instruction,
                        distance_m=step.distance_m,
                    )
                )
            if (
                step.distance_m <= short_turn_m
                and index < len(route.directions)
                and normalized.startswith("turn ")
                and " onto " in normalized
            ):
                issues.append(
                    DirectionQualityIssue(
                        route_label=route.label,
                        step_index=index,
                        reason="short_turn_fragment",
                        instruction=step.instruction,
                        distance_m=step.distance_m,
                    )
                )
    return issues
