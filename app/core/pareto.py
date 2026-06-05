from __future__ import annotations

from app.core.models import RouteMetrics, RouteOption


def dominates(a: RouteMetrics, b: RouteMetrics) -> bool:
    comparable_a = (
        a.time_s,
        a.distance_m,
        a.max_abs_grade,
        a.hill_discomfort,
        a.downhill_discomfort,
        a.safety_penalty,
        a.barrier_penalty,
        a.uncertainty_penalty,
        a.route_score,
    )
    comparable_b = (
        b.time_s,
        b.distance_m,
        b.max_abs_grade,
        b.hill_discomfort,
        b.downhill_discomfort,
        b.safety_penalty,
        b.barrier_penalty,
        b.uncertainty_penalty,
        b.route_score,
    )
    no_worse = all(
        left <= right + 1e-9 for left, right in zip(comparable_a, comparable_b, strict=True)
    )
    strictly_better = any(
        left < right - 1e-9 for left, right in zip(comparable_a, comparable_b, strict=True)
    )
    return no_worse and strictly_better


def pareto_prune(options: list[RouteOption]) -> list[RouteOption]:
    pruned: list[RouteOption] = []
    for option in options:
        dominated = any(
            dominates(other.metrics, option.metrics) for other in options if other is not option
        )
        if dominated:
            continue
        pruned.append(option)
    return pruned
