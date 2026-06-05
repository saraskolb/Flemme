from __future__ import annotations

import pytest

from app.core.models import ElevationSample
from app.core.smoothing import hampel_filter, smooth_elevation_profile


def test_single_elevation_spike_is_reduced() -> None:
    values = [10.0, 10.1, 10.0, 50.0, 10.0, 10.1, 10.0]

    filtered = hampel_filter(values, window_size=5)

    assert filtered[3] < 20.0


def test_genuine_sustained_climb_is_preserved() -> None:
    samples = [
        ElevationSample(dist_m=float(index * 10), z_raw_m=float(index), z_smooth_m=float(index))
        for index in range(7)
    ]

    smoothed = smooth_elevation_profile(samples)

    assert smoothed[-1].z_smooth_m - smoothed[0].z_smooth_m == pytest.approx(6.0, abs=0.25)
    assert max(sample.rolling_grade_20m or 0.0 for sample in smoothed) > 0.08


def test_very_short_segments_do_not_crash() -> None:
    samples = [
        ElevationSample(dist_m=0.0, z_raw_m=1.0, z_smooth_m=1.0),
        ElevationSample(dist_m=5.0, z_raw_m=1.2, z_smooth_m=1.2),
    ]

    smoothed = smooth_elevation_profile(samples)

    assert len(smoothed) == 2
    assert smoothed[1].grade == pytest.approx(0.04)
