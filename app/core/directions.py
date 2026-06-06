from __future__ import annotations

from math import atan2, cos, degrees, radians

from app.core.costs import edge_time_s
from app.core.models import Coordinate, DirectionStep, Edge, UserPrefs


def _display_name(edge: Edge) -> str:
    if edge.street_name:
        return edge.street_name
    if edge.edge_type in {"footway", "path", "pedestrian", "crossing"}:
        return "pedestrian path"
    if edge.edge_type == "steps":
        return "stairs"
    return edge.edge_type.replace("_", " ")


def _compass_from_bearing(bearing_deg: float) -> str:
    directions = [
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    ]
    index = round((bearing_deg % 360.0) / 45.0) % 8
    return directions[index]


def _bearing(geometry: list[Coordinate]) -> float:
    if len(geometry) < 2:
        return 0.0
    lon1, lat1 = geometry[0]
    lon2, lat2 = geometry[-1]
    mean_lat = radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * cos(mean_lat)
    dy = lat2 - lat1
    return (degrees(atan2(dx, dy)) + 360.0) % 360.0


def _turn_instruction(previous_bearing: float, current_bearing: float) -> str:
    delta = ((current_bearing - previous_bearing + 540.0) % 360.0) - 180.0
    if abs(delta) < 30:
        return "Continue"
    if abs(delta) > 150:
        return "Turn around"
    if delta > 0:
        return "Turn right"
    return "Turn left"


def _merge_geometry(edges: list[Edge]) -> list[Coordinate]:
    geometry: list[Coordinate] = []
    for edge in edges:
        if not geometry:
            geometry.extend(edge.geometry)
        elif edge.geometry:
            if geometry[-1] == edge.geometry[0]:
                geometry.extend(edge.geometry[1:])
            else:
                geometry.extend(edge.geometry)
    return geometry


def _step_from_edges(
    edges: list[Edge],
    prefs: UserPrefs,
    previous_bearing: float | None,
    is_first: bool,
    toward_name: str | None = None,
) -> tuple[DirectionStep, float]:
    geometry = _merge_geometry(edges)
    bearing = _bearing(geometry)
    name = _display_name(edges[0])
    instruction_name = name
    if name == "pedestrian path" and toward_name:
        instruction_name = f"pedestrian path toward {toward_name}"
    distance_m = sum(edge.length_m for edge in edges)
    time_s = sum(edge_time_s(edge, prefs) for edge in edges)
    gain_m = sum(edge.gain_m for edge in edges)
    loss_m = sum(edge.loss_m for edge in edges)
    max_uphill_grade = max((edge.max_uphill_grade for edge in edges), default=0.0)
    prefix = f"Walk {_compass_from_bearing(bearing)} on" if is_first else (
        f"{_turn_instruction(previous_bearing or bearing, bearing)} onto"
    )
    hill_note = ""
    if max_uphill_grade >= 0.06:
        hill_note = f"; uphill up to {round(max_uphill_grade * 100):.0f}%"
    instruction = f"{prefix} {instruction_name} for {format_distance(distance_m)}{hill_note}."
    return (
        DirectionStep(
            instruction=instruction,
            street_name=name,
            distance_m=distance_m,
            time_s=time_s,
            gain_m=gain_m,
            loss_m=loss_m,
            max_uphill_grade=max_uphill_grade,
            geometry=geometry,
        ),
        bearing,
    )


def format_distance(distance_m: float) -> str:
    if distance_m < 160.934:
        return f"{round(distance_m)} m"
    miles = distance_m / 1609.344
    return f"{miles:.1f} mi"


def build_directions(route_edges: list[Edge], prefs: UserPrefs) -> list[DirectionStep]:
    if not route_edges:
        return []

    groups: list[list[Edge]] = []
    for edge in route_edges:
        key = _display_name(edge)
        if groups and _display_name(groups[-1][-1]) == key:
            groups[-1].append(edge)
        else:
            groups.append([edge])

    steps: list[DirectionStep] = []
    previous_bearing: float | None = None
    for index, group in enumerate(groups):
        toward_name = None
        if _display_name(group[0]) == "pedestrian path":
            for later_group in groups[index + 1 :]:
                later_name = _display_name(later_group[0])
                if later_name != "pedestrian path":
                    toward_name = later_name
                    break
        step, previous_bearing = _step_from_edges(
            group,
            prefs,
            previous_bearing,
            is_first=index == 0,
            toward_name=toward_name,
        )
        steps.append(step)
    return steps
