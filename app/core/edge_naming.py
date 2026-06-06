from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import atan2, cos, degrees, radians
from typing import Any

from pyproj import Transformer
from shapely import STRtree  # type: ignore[import-untyped]
from shapely.geometry import LineString  # type: ignore[import-untyped]

from app.core.models import Coordinate, Edge, Graph

CONNECTOR_FOOTWAY_TAGS = {"sidewalk", "crossing", "traffic_island", "link"}
MAX_CONNECTOR_NAME_SEARCH_M = 300.0
DEFAULT_STREET_MATCH_DISTANCE_M = 28.0
MAX_BEARING_SCORE_PENALTY_M = 45.0
WGS84_TO_UTM10 = Transformer.from_crs("EPSG:4326", "EPSG:26910", always_xy=True)
SUFFIX_EXPANSIONS = {
    "AL": "Alley",
    "ALY": "Alley",
    "AV": "Avenue",
    "AVE": "Avenue",
    "BL": "Boulevard",
    "BLVD": "Boulevard",
    "CIR": "Circle",
    "CT": "Court",
    "DR": "Drive",
    "HWY": "Highway",
    "LN": "Lane",
    "LOOP": "Loop",
    "PATH": "Path",
    "PKWY": "Parkway",
    "PL": "Place",
    "RD": "Road",
    "ST": "Street",
    "TER": "Terrace",
    "TR": "Terrace",
    "WALK": "Walk",
    "WAY": "Way",
    "WY": "Way",
}
ROAD_TYPES = {
    "living_street",
    "pedestrian",
    "primary",
    "residential",
    "secondary",
    "service",
    "tertiary",
    "unclassified",
}


@dataclass(frozen=True)
class EdgeLabel:
    text: str | None
    key: str
    kind: str


@dataclass(frozen=True)
class OfficialStreetName:
    display_name: str
    source_dataset: str
    source_feature_id: str
    geometry: list[Coordinate]
    active: bool = True
    properties: dict[str, Any] | None = None


def tag(edge: Edge, key: str) -> str | None:
    value = edge.source_tags.get(key)
    return value.strip().lower() if value else None


def is_alley(edge: Edge) -> bool:
    return edge.edge_type == "service" and tag(edge, "service") == "alley"


def is_connector(edge: Edge) -> bool:
    if edge.street_name or edge.stairs or is_alley(edge):
        return False
    if edge.edge_type == "crossing":
        return True
    footway = tag(edge, "footway")
    if footway in CONNECTOR_FOOTWAY_TAGS:
        return True
    highway = tag(edge, "highway") or edge.edge_type
    return highway == "footway" and edge.edge_type != "path"


def fallback_display_name(edge: Edge) -> tuple[str, str]:
    if edge.stairs or edge.edge_type == "steps":
        return "stairs", "generic_stairs"
    if is_alley(edge):
        return "alley", "generic_alley"
    if edge.edge_type in {"path", "footway"}:
        return "walking path", "generic_path"
    if edge.edge_type in ROAD_TYPES:
        return "unnamed street", "generic_unnamed_street"
    return edge.edge_type.replace("_", " "), "generic_edge_type"


def format_street_name(raw_name: str) -> str:
    """Format uppercase civic street names into user-facing title case."""
    cleaned = " ".join(raw_name.replace("*NO STREET SUFFIX", "").split())
    if not cleaned:
        return raw_name

    tokens = cleaned.split(" ")
    formatted: list[str] = []
    for index, token in enumerate(tokens):
        upper = token.upper().strip(".")
        if index == len(tokens) - 1 and upper in SUFFIX_EXPANSIONS:
            formatted.append(SUFFIX_EXPANSIONS[upper])
        elif upper.startswith(("I-", "US-", "HWY")) or upper.isdigit() or _is_ordinal(upper):
            formatted.append(upper)
        else:
            formatted.append(token.lower().title())
    return " ".join(formatted)


def edge_label(edge: Edge) -> EdgeLabel:
    if edge.street_name:
        display_name = edge.display_name or edge.street_name
        return EdgeLabel(display_name, f"named:{display_name}", "named")
    if is_connector(edge):
        if edge.display_name and edge.name_source != "generic_connector":
            return EdgeLabel(edge.display_name, f"connector:{edge.display_name}", "connector")
        return EdgeLabel(None, "connector:generic", "connector")

    label_text = edge.display_name
    if not label_text:
        label_text, _ = fallback_display_name(edge)

    if edge.stairs or edge.edge_type == "steps":
        return EdgeLabel(label_text, "stairs", "stairs")
    if is_alley(edge):
        return EdgeLabel(label_text, "alley", "alley")
    if edge.edge_type in {"path", "footway"}:
        return EdgeLabel(label_text, "walking_path", "path")
    if edge.edge_type in ROAD_TYPES:
        return EdgeLabel(label_text, f"road:{label_text}", "unnamed_street")
    return EdgeLabel(label_text, f"kind:{edge.edge_type}", "way")


def assign_edge_display_names(graph: Graph) -> Graph:
    named_edges_by_node: dict[int, list[Edge]] = {}
    connector_edges_by_node: dict[int, list[Edge]] = {}
    for edge in graph.edges.values():
        if not edge.display_name and edge.street_name:
            edge.display_name = edge.street_name
            edge.name_source = "osm"
            edge.source_dataset = edge.source_dataset or "openstreetmap"
            edge.source_feature_id = edge.source_feature_id or (
                str(edge.osm_way_id) if edge.osm_way_id is not None else None
            )
            edge.name_confidence = edge.name_confidence or 0.85
            edge.name_status = "osm_named"
        if edge.street_name:
            named_edges_by_node.setdefault(edge.source, []).append(edge)
            named_edges_by_node.setdefault(edge.target, []).append(edge)
        elif is_connector(edge):
            connector_edges_by_node.setdefault(edge.source, []).append(edge)
            connector_edges_by_node.setdefault(edge.target, []).append(edge)

    for edge in graph.edges.values():
        if edge.display_name:
            continue
        if is_connector(edge):
            inferred_name = _nearest_reachable_street_name(
                edge,
                named_edges_by_node,
                connector_edges_by_node,
            )
            if inferred_name:
                edge.display_name = inferred_name
                edge.name_source = "inferred_reachable_street"
                edge.source_dataset = edge.source_dataset or "graph_topology"
                edge.name_confidence = edge.name_confidence or 0.55
                edge.name_status = "inferred_street_name"
            else:
                edge.display_name = "walkway"
                edge.name_source = "generic_connector"
                edge.name_confidence = edge.name_confidence or 0.2
                edge.name_status = "generic_connector"
            continue

        edge.display_name, edge.name_source = fallback_display_name(edge)
        edge.name_confidence = edge.name_confidence or 0.25
        edge.name_status = edge.name_source

    return graph


def apply_official_street_names(
    graph: Graph,
    centerlines: list[OfficialStreetName],
    max_distance_m: float = DEFAULT_STREET_MATCH_DISTANCE_M,
) -> Graph:
    """Attach official city street names to graph edges by spatial matching."""
    if not centerlines:
        return graph

    street_lines = [_projected_line(centerline.geometry) for centerline in centerlines]
    tree = STRtree(street_lines)

    for edge in graph.edges.values():
        if len(edge.geometry) < 2:
            continue
        edge_line = _projected_line(edge.geometry)
        search_geom = edge_line.buffer(max_distance_m)
        candidate_indexes = tree.query(search_geom)
        best_match: tuple[float, float, OfficialStreetName] | None = None
        edge_bearing = _bearing(edge.geometry)
        normalized_osm_name = _normalize_name(edge.street_name or "")

        for raw_index in candidate_indexes:
            index = int(raw_index)
            centerline = centerlines[index]
            street_line = street_lines[index]
            distance_m = edge_line.distance(street_line)
            if distance_m > max_distance_m:
                continue
            bearing_delta = _parallel_bearing_delta(edge_bearing, _bearing(centerline.geometry))
            if bearing_delta > 75.0 and distance_m > 8.0 and not is_connector(edge):
                continue

            bearing_penalty_m = min(
                MAX_BEARING_SCORE_PENALTY_M,
                bearing_delta * 0.65,
            )
            score = distance_m + bearing_penalty_m
            if not centerline.active:
                score += 30.0
            if normalized_osm_name and normalized_osm_name == _normalize_name(
                centerline.display_name
            ):
                score -= 18.0

            if best_match is None or score < best_match[0]:
                best_match = (score, distance_m, centerline)

        if best_match is None:
            continue

        _, distance_m, centerline = best_match
        confidence = max(0.35, min(1.0, 1.0 - (distance_m / max_distance_m) * 0.45))
        edge.display_name = centerline.display_name
        edge.name_source = "datasf_centerline"
        edge.source_dataset = centerline.source_dataset
        edge.source_feature_id = centerline.source_feature_id
        edge.name_confidence = confidence
        edge.name_status = "official_street_name" if centerline.active else "retired_street_name"

    return assign_edge_display_names(graph)


def _nearest_reachable_street_name(
    edge: Edge,
    named_edges_by_node: dict[int, list[Edge]],
    connector_edges_by_node: dict[int, list[Edge]],
) -> str | None:
    edge_bearing = _bearing(edge.geometry)
    best_by_node = {edge.source: 0.0, edge.target: 0.0}
    queue = [(0.0, edge.source), (0.0, edge.target)]
    candidates: list[tuple[float, str]] = []

    while queue:
        distance_m, node_id = heappop(queue)
        if distance_m > best_by_node.get(node_id, float("inf")):
            continue
        for candidate in named_edges_by_node.get(node_id, []):
            if not candidate.street_name:
                continue
            bearing_penalty_m = (
                _parallel_bearing_delta(edge_bearing, _bearing(candidate.geometry)) * 1.5
            )
            candidates.append((distance_m + bearing_penalty_m, candidate.street_name))

        for connector in connector_edges_by_node.get(node_id, []):
            if connector.edge_id == edge.edge_id:
                continue
            next_node = connector.target if connector.source == node_id else connector.source
            next_distance_m = distance_m + connector.length_m
            if next_distance_m > MAX_CONNECTOR_NAME_SEARCH_M:
                continue
            if next_distance_m < best_by_node.get(next_node, float("inf")):
                best_by_node[next_node] = next_distance_m
                heappush(queue, (next_distance_m, next_node))

    if not candidates:
        return None
    return min(candidates)[1]


def _projected_line(geometry: list[Coordinate]) -> LineString:
    return LineString([WGS84_TO_UTM10.transform(lon, lat) for lon, lat in geometry])


def _bearing(geometry: list[Coordinate]) -> float:
    if len(geometry) < 2:
        return 0.0
    lon1, lat1 = geometry[0]
    lon2, lat2 = geometry[-1]
    mean_lat = radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * cos(mean_lat)
    dy = lat2 - lat1
    return (degrees(atan2(dx, dy)) + 360.0) % 360.0


def _parallel_bearing_delta(first: float, second: float) -> float:
    delta = abs(((first - second + 180.0) % 360.0) - 180.0)
    return min(delta, abs(delta - 180.0))


def _normalize_name(name: str) -> str:
    return " ".join(format_street_name(name).casefold().replace(".", "").split())


def _is_ordinal(token: str) -> bool:
    return (
        len(token) > 2
        and token[:-2].isdigit()
        and token[-2:] in {"ST", "ND", "RD", "TH"}
    )
