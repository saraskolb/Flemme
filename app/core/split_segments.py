from __future__ import annotations

from app.core.models import ElevationSample


def regular_breakpoints(length_m: float, every_m: float = 15.0) -> list[float]:
    if length_m < 0:
        raise ValueError("length_m must be nonnegative.")
    if every_m <= 0:
        raise ValueError("every_m must be positive.")
    if length_m == 0:
        return [0.0]

    points = [0.0]
    current = every_m
    while current < length_m:
        points.append(round(current, 6))
        current += every_m
    points.append(float(length_m))
    return points


def _sample_grade(sample: ElevationSample) -> float:
    if sample.rolling_grade_20m is not None:
        return sample.rolling_grade_20m
    if sample.grade is not None:
        return sample.grade
    return 0.0


def grade_threshold_breakpoints(
    samples: list[ElevationSample], thresholds: list[float]
) -> list[float]:
    if len(samples) < 2:
        return []

    points: list[float] = []
    normalized_thresholds = sorted(abs(threshold) for threshold in thresholds)
    for left, right in zip(samples, samples[1:], strict=False):
        left_abs = abs(_sample_grade(left))
        right_abs = abs(_sample_grade(right))
        if left.dist_m == right.dist_m:
            continue
        for threshold in normalized_thresholds:
            crosses = (left_abs < threshold <= right_abs) or (right_abs < threshold <= left_abs)
            if not crosses or left_abs == right_abs:
                continue
            ratio = (threshold - left_abs) / (right_abs - left_abs)
            if 0.0 <= ratio <= 1.0:
                points.append(left.dist_m + ratio * (right.dist_m - left.dist_m))
    return sorted(points)


def local_extrema_breakpoints(
    samples: list[ElevationSample], min_prominence: float = 0.02
) -> list[float]:
    if len(samples) < 3:
        return []

    points: list[float] = []
    grades = [_sample_grade(sample) for sample in samples]
    for index in range(1, len(samples) - 1):
        previous_grade = grades[index - 1]
        current_grade = grades[index]
        next_grade = grades[index + 1]
        is_peak = current_grade > previous_grade and current_grade > next_grade
        is_valley = current_grade < previous_grade and current_grade < next_grade
        prominence = min(abs(current_grade - previous_grade), abs(current_grade - next_grade))
        if (is_peak or is_valley) and prominence >= min_prominence:
            points.append(samples[index].dist_m)
    return points


def merge_breakpoints(points: list[float], min_gap_m: float = 3.0) -> list[float]:
    if min_gap_m < 0:
        raise ValueError("min_gap_m must be nonnegative.")
    if not points:
        return []

    merged: list[float] = []
    for point in sorted(points):
        if point < 0:
            raise ValueError("Breakpoints cannot be negative.")
        if not merged or point - merged[-1] >= min_gap_m:
            merged.append(float(point))
        else:
            merged[-1] = (merged[-1] + float(point)) / 2.0
    return merged
