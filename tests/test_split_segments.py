from __future__ import annotations

import pytest

from app.core.models import ElevationSample
from app.core.split_segments import (
    grade_threshold_breakpoints,
    local_extrema_breakpoints,
    merge_breakpoints,
    regular_breakpoints,
)


def test_regular_breakpoints_include_ends() -> None:
    assert regular_breakpoints(45.0, every_m=15.0) == [0.0, 15.0, 30.0, 45.0]


def test_short_steep_section_gets_threshold_breakpoints() -> None:
    samples = [
        ElevationSample(0.0, 0.0, 0.0, rolling_grade_20m=0.02),
        ElevationSample(10.0, 0.0, 0.0, rolling_grade_20m=0.15),
        ElevationSample(20.0, 0.0, 0.0, rolling_grade_20m=0.02),
    ]

    points = grade_threshold_breakpoints(samples, thresholds=[0.06, 0.10, 0.12])

    assert len(points) >= 2
    assert min(points) > 0.0
    assert max(points) < 20.0


def test_local_extrema_breakpoints_find_grade_peak() -> None:
    samples = [
        ElevationSample(0.0, 0.0, 0.0, rolling_grade_20m=0.02),
        ElevationSample(10.0, 0.0, 0.0, rolling_grade_20m=0.12),
        ElevationSample(20.0, 0.0, 0.0, rolling_grade_20m=0.03),
    ]

    assert local_extrema_breakpoints(samples) == [10.0]


def test_breakpoints_are_deduplicated_with_minimum_gap() -> None:
    merged = merge_breakpoints([0.0, 1.0, 10.0, 10.5, 20.0], min_gap_m=3.0)

    assert merged == pytest.approx([0.5, 10.25, 20.0])
