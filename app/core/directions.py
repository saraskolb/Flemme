from __future__ import annotations

from math import atan2, cos, degrees, radians

from app.core.costs import edge_time_s
from app.core.edge_naming import edge_label
from app.core.models import Coordinate, DirectionStep, Edge, UserPrefs

SHORT_CROSSING_GROUP_M = 18.0


def _direction_key(edge: Edge) -> str:
    label = edge_label(edge)
    if label.text:
        return f"name:{label.text}"
    if label.kind == "connector":
        return "connector:generic"
    return label.key


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


def _group_label_text(group: list[Edge]) -> str | None:
    return edge_label(group[0]).text


def _group_distance_m(group: list[Edge]) -> float:
    return sum(edge.length_m for edge in group)


def _absorb_short_cross_street_groups(groups: list[list[Edge]]) -> list[list[Edge]]:
    simplified = [list(group) for group in groups]
    index = 1
    while index < len(simplified) - 1:
        previous_name = _group_label_text(simplified[index - 1])
        current_name = _group_label_text(simplified[index])
        next_name = _group_label_text(simplified[index + 1])
        is_short_crossing = _group_distance_m(simplified[index]) <= SHORT_CROSSING_GROUP_M
        if (
            previous_name
            and previous_name == next_name
            and current_name != previous_name
            and is_short_crossing
        ):
            simplified[index - 1].extend(simplified[index])
            simplified[index - 1].extend(simplified[index + 1])
            del simplified[index : index + 2]
            index = max(1, index - 1)
            continue
        index += 1
    return simplified


def _step_from_edges(
    edges: list[Edge],
    prefs: UserPrefs,
    previous_bearing: float | None,
    is_first: bool,
    toward_name: str | None = None,
) -> tuple[DirectionStep, float]:
    geometry = _merge_geometry(edges)
    bearing = _bearing(geometry)
    label = edge_label(edges[0])
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
    if label.kind == "connector" and not label.text:
        if toward_name:
            prefix = f"Walk {_compass_from_bearing(bearing)} toward" if is_first else (
                f"{_turn_instruction(previous_bearing or bearing, bearing)} toward"
            )
            instruction = f"{prefix} {toward_name} for {format_distance(distance_m)}{hill_note}."
        else:
            prefix = f"Walk {_compass_from_bearing(bearing)}" if is_first else (
                _turn_instruction(previous_bearing or bearing, bearing)
            )
            instruction = f"{prefix} for {format_distance(distance_m)}{hill_note}."
    else:
        instruction = f"{prefix} {label.text} for {format_distance(distance_m)}{hill_note}."
    return (
        DirectionStep(
            instruction=instruction,
            street_name=toward_name if label.kind == "connector" and toward_name else label.text,
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
        key = _direction_key(edge)
        if groups and _direction_key(groups[-1][-1]) == key:
            groups[-1].append(edge)
        else:
            groups.append([edge])
    groups = _absorb_short_cross_street_groups(groups)

    steps: list[DirectionStep] = []
    previous_bearing: float | None = None
    for index, group in enumerate(groups):
        toward_name = None
        if edge_label(group[0]).kind == "connector":
            for later_group in groups[index + 1 :]:
                later_label = edge_label(later_group[0])
                if later_label.kind != "connector" and later_label.text:
                    toward_name = later_label.text
                    break
            if not toward_name:
                for edge in reversed(group):
                    label = edge_label(edge)
                    if label.text:
                        toward_name = label.text
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
