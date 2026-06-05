from __future__ import annotations

from dataclasses import replace
from statistics import median

from app.core.grade import with_rolling_grades
from app.core.models import ElevationSample


def hampel_filter(values: list[float], window_size: int, n_sigmas: float = 3.0) -> list[float]:
    if window_size < 1:
        raise ValueError("window_size must be at least 1.")
    if not values:
        return []

    filtered = list(values)
    half_window = window_size // 2
    for index, value in enumerate(values):
        start = max(0, index - half_window)
        end = min(len(values), index + half_window + 1)
        window = values[start:end]
        window_median = median(window)
        deviations = [abs(item - window_median) for item in window]
        mad = median(deviations)
        threshold = n_sigmas * 1.4826 * mad
        if mad == 0:
            if value != window_median:
                filtered[index] = window_median
        elif abs(value - window_median) > threshold:
            filtered[index] = window_median
    return filtered


def _normalized_odd_window(length: int, requested: int, polyorder: int) -> int:
    if length <= polyorder + 1:
        return 0
    window = min(requested, length)
    if window % 2 == 0:
        window -= 1
    minimum = polyorder + 2
    if minimum % 2 == 0:
        minimum += 1
    if window < minimum:
        window = minimum if minimum <= length else 0
    return window


def savgol_smooth(values: list[float], window_length: int, polyorder: int = 2) -> list[float]:
    if not values:
        return []

    window = _normalized_odd_window(len(values), window_length, polyorder)
    if window == 0:
        return list(values)

    try:
        from scipy.signal import savgol_filter  # type: ignore[import-untyped]
    except ImportError:
        half_window = window // 2
        smoothed: list[float] = []
        for index in range(len(values)):
            start = max(0, index - half_window)
            end = min(len(values), index + half_window + 1)
            smoothed.append(sum(values[start:end]) / (end - start))
        return smoothed

    return [float(value) for value in savgol_filter(values, window, polyorder, mode="interp")]


def smooth_elevation_profile(samples: list[ElevationSample]) -> list[ElevationSample]:
    if len(samples) < 3:
        return with_rolling_grades(samples)

    raw_values = [sample.z_raw_m for sample in samples]
    filtered = hampel_filter(raw_values, window_size=min(5, len(samples)))
    smoothed = savgol_smooth(filtered, window_length=min(7, len(samples)), polyorder=2)
    smoothed_samples = [
        replace(sample, z_smooth_m=z_smooth_m)
        for sample, z_smooth_m in zip(samples, smoothed, strict=True)
    ]
    return with_rolling_grades(smoothed_samples)
