from __future__ import annotations

import pytest

from app.core.grade import (
    aggregate_edge_grade_metrics,
    compute_gain_loss,
    compute_grades,
    reverse_samples,
    rolling_grade,
)
from app.core.models import ElevationSample


def test_100m_segment_rising_10m_returns_10_percent_grade() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=100.0, z_raw_m=10.0, z_smooth_m=10.0),
    ]

    graded = compute_grades(samples)
    metrics = aggregate_edge_grade_metrics(samples)

    assert graded[1].grade == pytest.approx(0.10)
    assert metrics["max_uphill_grade"] == pytest.approx(0.10)
    assert metrics["gain_m"] == pytest.approx(10.0)


def test_reverse_direction_turns_uphill_into_downhill() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=100.0, z_raw_m=10.0, z_smooth_m=10.0),
    ]

    reversed_samples = reverse_samples(samples)

    assert reversed_samples[1].grade == pytest.approx(-0.10)
    metrics = aggregate_edge_grade_metrics(reversed_samples)
    assert metrics["max_downhill_grade"] == pytest.approx(0.10)


def test_rolling_20m_grade_detects_short_steep_section() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=10.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=20.0, z_raw_m=2.0, z_smooth_m=2.0),
        ElevationSample(dist_m=30.0, z_raw_m=2.0, z_smooth_m=2.0),
    ]

    grades = rolling_grade(samples, window_m=20.0)

    assert max(grades) == pytest.approx(0.10)


def test_gain_loss_are_direction_sensitive() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=50.0, z_raw_m=5.0, z_smooth_m=5.0),
        ElevationSample(dist_m=100.0, z_raw_m=3.0, z_smooth_m=3.0),
    ]

    gain, loss = compute_gain_loss(samples)

    assert gain == pytest.approx(5.0)
    assert loss == pytest.approx(2.0)


def test_zero_length_intervals_are_rejected() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=0.0, z_smooth_m=0.0),
        ElevationSample(dist_m=0.0, z_raw_m=1.0, z_smooth_m=1.0),
    ]

    with pytest.raises(ValueError):
        compute_grades(samples)
