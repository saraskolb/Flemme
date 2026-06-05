from __future__ import annotations

from dataclasses import replace

from app.core.models import ElevationSample


def _validate_distances(samples: list[ElevationSample]) -> None:
    for previous, current in zip(samples, samples[1:], strict=False):
        if current.dist_m <= previous.dist_m:
            raise ValueError("Elevation sample distances must be strictly increasing.")


def compute_grades(samples: list[ElevationSample]) -> list[ElevationSample]:
    if len(samples) < 2:
        return [replace(sample, grade=None) for sample in samples]

    _validate_distances(samples)
    graded = [replace(samples[0], grade=None)]
    for previous, current in zip(samples, samples[1:], strict=False):
        dx = current.dist_m - previous.dist_m
        dz = current.z_smooth_m - previous.z_smooth_m
        graded.append(replace(current, grade=dz / dx))
    return graded


def compute_gain_loss(samples: list[ElevationSample]) -> tuple[float, float]:
    if len(samples) < 2:
        return 0.0, 0.0

    _validate_distances(samples)
    gain = 0.0
    loss = 0.0
    for previous, current in zip(samples, samples[1:], strict=False):
        dz = current.z_smooth_m - previous.z_smooth_m
        if dz > 0:
            gain += dz
        else:
            loss += abs(dz)
    return gain, loss


def _interpolate_z(samples: list[ElevationSample], dist_m: float) -> float:
    if dist_m <= samples[0].dist_m:
        return samples[0].z_smooth_m
    if dist_m >= samples[-1].dist_m:
        return samples[-1].z_smooth_m

    for left, right in zip(samples, samples[1:], strict=False):
        if left.dist_m <= dist_m <= right.dist_m:
            span = right.dist_m - left.dist_m
            if span <= 0:
                raise ValueError("Elevation sample distances must be strictly increasing.")
            ratio = (dist_m - left.dist_m) / span
            return left.z_smooth_m + ratio * (right.z_smooth_m - left.z_smooth_m)

    return samples[-1].z_smooth_m


def rolling_grade(samples: list[ElevationSample], window_m: float) -> list[float]:
    if window_m <= 0:
        raise ValueError("Rolling grade window must be positive.")
    if len(samples) < 2:
        return [0.0 for _ in samples]

    _validate_distances(samples)
    grades: list[float] = []
    first_dist = samples[0].dist_m
    for sample in samples:
        start_dist = max(first_dist, sample.dist_m - window_m)
        span = sample.dist_m - start_dist
        if span <= 0:
            grades.append(0.0)
            continue
        start_z = _interpolate_z(samples, start_dist)
        grades.append((sample.z_smooth_m - start_z) / span)
    return grades


def with_rolling_grades(samples: list[ElevationSample]) -> list[ElevationSample]:
    graded = compute_grades(samples)
    grades_20m = rolling_grade(graded, 20.0)
    grades_50m = rolling_grade(graded, 50.0)
    return [
        replace(sample, rolling_grade_20m=grade_20m, rolling_grade_50m=grade_50m)
        for sample, grade_20m, grade_50m in zip(graded, grades_20m, grades_50m, strict=True)
    ]


def aggregate_edge_grade_metrics(samples: list[ElevationSample]) -> dict[str, float]:
    if len(samples) < 2:
        return {
            "gain_m": 0.0,
            "loss_m": 0.0,
            "mean_grade": 0.0,
            "max_uphill_grade": 0.0,
            "max_downhill_grade": 0.0,
            "max_abs_grade": 0.0,
            "sustained_uphill_grade_20m": 0.0,
            "sustained_downhill_grade_20m": 0.0,
            "sustained_uphill_grade_50m": 0.0,
            "sustained_downhill_grade_50m": 0.0,
            "length_above_6pct_up_m": 0.0,
            "length_above_8pct_up_m": 0.0,
            "length_above_10pct_up_m": 0.0,
            "length_above_12pct_up_m": 0.0,
        }

    graded = with_rolling_grades(samples)
    gain, loss = compute_gain_loss(graded)
    total_length = graded[-1].dist_m - graded[0].dist_m
    interval_grades: list[tuple[float, float]] = []
    for previous, current in zip(graded, graded[1:], strict=False):
        length_m = current.dist_m - previous.dist_m
        grade = (current.z_smooth_m - previous.z_smooth_m) / length_m
        interval_grades.append((length_m, grade))

    uphill_grades = [max(0.0, grade) for _, grade in interval_grades]
    downhill_grades = [max(0.0, -grade) for _, grade in interval_grades]
    rolling_20 = [sample.rolling_grade_20m or 0.0 for sample in graded]
    rolling_50 = [sample.rolling_grade_50m or 0.0 for sample in graded]

    def length_above(threshold: float) -> float:
        return sum(length_m for length_m, grade in interval_grades if grade > threshold)

    max_uphill = max(uphill_grades, default=0.0)
    max_downhill = max(downhill_grades, default=0.0)
    return {
        "gain_m": gain,
        "loss_m": loss,
        "mean_grade": (graded[-1].z_smooth_m - graded[0].z_smooth_m) / total_length
        if total_length > 0
        else 0.0,
        "max_uphill_grade": max_uphill,
        "max_downhill_grade": max_downhill,
        "max_abs_grade": max(max_uphill, max_downhill),
        "sustained_uphill_grade_20m": max(
            (max(0.0, grade) for grade in rolling_20), default=0.0
        ),
        "sustained_downhill_grade_20m": max(
            (max(0.0, -grade) for grade in rolling_20), default=0.0
        ),
        "sustained_uphill_grade_50m": max(
            (max(0.0, grade) for grade in rolling_50), default=0.0
        ),
        "sustained_downhill_grade_50m": max(
            (max(0.0, -grade) for grade in rolling_50), default=0.0
        ),
        "length_above_6pct_up_m": length_above(0.06),
        "length_above_8pct_up_m": length_above(0.08),
        "length_above_10pct_up_m": length_above(0.10),
        "length_above_12pct_up_m": length_above(0.12),
    }


def reverse_samples(samples: list[ElevationSample]) -> list[ElevationSample]:
    if not samples:
        return []

    _validate_distances(samples)
    total_length = samples[-1].dist_m - samples[0].dist_m
    reversed_samples = [
        ElevationSample(
            dist_m=total_length - (sample.dist_m - samples[0].dist_m),
            z_raw_m=sample.z_raw_m,
            z_smooth_m=sample.z_smooth_m,
        )
        for sample in reversed(samples)
    ]
    return with_rolling_grades(reversed_samples)
