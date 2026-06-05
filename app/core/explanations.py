from __future__ import annotations

from dataclasses import replace

from app.core.models import Edge, HillEvent, RouteOption, UserPrefs


def _qualifying_event(edge: Edge) -> tuple[str, float] | None:
    uphill_grade = max(edge.sustained_uphill_grade_20m, edge.sustained_uphill_grade_50m)
    uphill_grade = max(uphill_grade, edge.max_uphill_grade)
    downhill_grade = max(edge.sustained_downhill_grade_20m, edge.sustained_downhill_grade_50m)
    downhill_grade = max(downhill_grade, edge.max_downhill_grade)

    if uphill_grade >= 0.06:
        return "uphill", uphill_grade
    if downhill_grade >= 0.08:
        return "downhill", downhill_grade
    return None


def _event_from_edge(edge: Edge, start_dist_m: float, direction: str, grade: float) -> HillEvent:
    if direction == "uphill":
        elevation_change = edge.gain_m
        average_grade = edge.gain_m / edge.length_m if edge.length_m > 0 else 0.0
        length_above_8 = edge.length_above_8pct_up_m
        length_above_10 = edge.length_above_10pct_up_m
    else:
        elevation_change = -edge.loss_m
        average_grade = -edge.loss_m / edge.length_m if edge.length_m > 0 else 0.0
        length_above_8 = edge.length_m if grade >= 0.08 else 0.0
        length_above_10 = edge.length_m if grade >= 0.10 else 0.0

    return HillEvent(
        street_name=edge.street_name,
        start_dist_m=start_dist_m,
        end_dist_m=start_dist_m + edge.length_m,
        length_m=edge.length_m,
        direction=direction,  # type: ignore[arg-type]
        elevation_change_m=elevation_change,
        average_grade=average_grade,
        max_sustained_grade=grade,
        length_above_8pct_m=length_above_8,
        length_above_10pct_m=length_above_10,
    )


def _merge_events(previous: HillEvent, current: HillEvent) -> HillEvent:
    combined_length = current.end_dist_m - previous.start_dist_m
    elevation_change = previous.elevation_change_m + current.elevation_change_m
    average_grade = elevation_change / combined_length if combined_length > 0 else 0.0
    return replace(
        previous,
        end_dist_m=current.end_dist_m,
        length_m=combined_length,
        elevation_change_m=elevation_change,
        average_grade=average_grade,
        max_sustained_grade=max(previous.max_sustained_grade, current.max_sustained_grade),
        length_above_8pct_m=previous.length_above_8pct_m + current.length_above_8pct_m,
        length_above_10pct_m=previous.length_above_10pct_m + current.length_above_10pct_m,
    )


def detect_hill_events(route_edges: list[Edge]) -> list[HillEvent]:
    events: list[HillEvent] = []
    cumulative_dist_m = 0.0
    for edge in route_edges:
        qualifier = _qualifying_event(edge)
        if qualifier is None:
            cumulative_dist_m += edge.length_m
            continue

        direction, grade = qualifier
        current = _event_from_edge(edge, cumulative_dist_m, direction, grade)
        if events:
            previous = events[-1]
            gap = current.start_dist_m - previous.end_dist_m
            if (
                previous.street_name == current.street_name
                and previous.direction == current.direction
                and gap <= 20.0
            ):
                events[-1] = _merge_events(previous, current)
            else:
                events.append(current)
        else:
            events.append(current)
        cumulative_dist_m += edge.length_m
    return events


def _minutes(time_s: float) -> int:
    return max(0, round(time_s / 60.0))


def _grade_pct(grade: float) -> str:
    return f"{round(grade * 100):.0f}%"


def _miles(distance_m: float) -> str:
    return f"{distance_m / 1609.344:.1f} mi"


def explain_route(option: RouteOption, fastest: RouteOption | None, prefs: UserPrefs) -> str:
    prefix = "Recommended" if option.label == "recommended" else option.label.capitalize()
    base = f"{prefix}: {_minutes(option.metrics.time_s)} min, {_miles(option.metrics.distance_m)}."

    if fastest is None or option.edge_ids == fastest.edge_ids:
        if option.metrics.max_abs_grade > 0:
            return f"{base} Max grade is {_grade_pct(option.metrics.max_abs_grade)}."
        return base

    delta_s = option.metrics.time_s - fastest.metrics.time_s
    delta_min = max(0, round(delta_s / 60.0))
    minute_word = "minute" if delta_min == 1 else "minutes"
    option_grade = _grade_pct(option.metrics.max_abs_grade)
    fastest_grade = _grade_pct(fastest.metrics.max_abs_grade)

    if option.metrics.max_abs_grade < fastest.metrics.max_abs_grade:
        return (
            f"{base} This is about {delta_min} {minute_word} slower than the fastest route, "
            f"but avoids the steepest hill. Max grade is {option_grade}, versus "
            f"{fastest_grade} on the fastest route. Distance above 10% uphill is near zero."
        )

    return (
        f"{base} This is about {delta_min} {minute_word} slower than the fastest route. "
        f"Max grade is {option_grade}, versus {fastest_grade} on the fastest route."
    )
