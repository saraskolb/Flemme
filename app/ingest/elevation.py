from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ElevationProvider(Protocol):
    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        """Return elevations in meters for (lat, lon) points."""


class FlatElevationProvider:
    def __init__(self, z_m: float = 0.0) -> None:
        self.z_m = z_m

    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        return [self.z_m for _ in points]


def parse_usgs_epqs_response(payload: dict[str, Any]) -> float:
    value = payload.get("value")
    if isinstance(value, int | float | str):
        return float(value)

    service = payload.get("USGS_Elevation_Point_Query_Service")
    if isinstance(service, dict):
        query = service.get("Elevation_Query")
        if isinstance(query, dict):
            for key in ("Elevation", "Elevation_Query"):
                value = query.get(key)
                if isinstance(value, int | float | str):
                    return float(value)

    raise ValueError(f"Could not parse USGS EPQS elevation payload: {payload}")


class USGSElevationProvider:
    def __init__(
        self,
        cache_path: Path | None = None,
        endpoint: str = "https://epqs.nationalmap.gov/v1/json",
        timeout_s: float = 15.0,
        retries: int = 2,
    ) -> None:
        self.cache_path = cache_path
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.retries = retries
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, float]:
        if self.cache_path is None or not self.cache_path.exists():
            return {}
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        return {key: float(value) for key, value in payload.items()}

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    @staticmethod
    def _cache_key(lat: float, lon: float) -> str:
        return f"{lat:.7f},{lon:.7f}"

    def _fetch_one(self, lat: float, lon: float) -> float:
        query = urlencode(
            {
                "x": lon,
                "y": lat,
                "units": "Meters",
                "wkid": 4326,
                "includeDate": "false",
            }
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(f"{self.endpoint}?{query}", timeout=self.timeout_s) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return parse_usgs_epqs_response(payload)
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
        if last_error is None:
            raise RuntimeError("USGS EPQS request failed without an exception.")
        raise last_error

    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        values: list[float] = []
        dirty = False
        for lat, lon in points:
            key = self._cache_key(lat, lon)
            if key not in self._cache:
                self._cache[key] = self._fetch_one(lat, lon)
                self._save_cache()
                dirty = True
            values.append(self._cache[key])
        if dirty:
            self._save_cache()
        return values


def parse_open_meteo_elevation_response(payload: dict[str, Any] | list[Any]) -> list[float]:
    if isinstance(payload, dict):
        value = payload.get("elevation")
        if isinstance(value, int | float | str):
            return [float(value)]
        if isinstance(value, list):
            elevation_values: list[float] = []
            for item in value:
                if not isinstance(item, int | float | str):
                    raise ValueError(f"Unexpected Open-Meteo elevation value: {item}")
                elevation_values.append(float(item))
            return elevation_values
    if isinstance(payload, list):
        elevations: list[float] = []
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError(f"Unexpected Open-Meteo elevation item: {item}")
            value = item.get("elevation")
            if not isinstance(value, int | float | str):
                raise ValueError(f"Missing Open-Meteo elevation value: {item}")
            elevations.append(float(value))
        return elevations
    raise ValueError(f"Could not parse Open-Meteo elevation payload: {payload}")


class OpenMeteoElevationProvider:
    def __init__(
        self,
        cache_path: Path | None = None,
        endpoint: str = "https://api.open-meteo.com/v1/elevation",
        timeout_s: float = 30.0,
        batch_size: int = 25,
        retries: int = 4,
        batch_pause_s: float = 0.25,
    ) -> None:
        self.cache_path = cache_path
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.batch_size = batch_size
        self.retries = retries
        self.batch_pause_s = batch_pause_s
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, float]:
        if self.cache_path is None or not self.cache_path.exists():
            return {}
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        return {key: float(value) for key, value in payload.items()}

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    @staticmethod
    def _cache_key(lat: float, lon: float) -> str:
        return f"{lat:.7f},{lon:.7f}"

    def _fetch_batch(self, points: list[tuple[float, float]]) -> list[float]:
        query = urlencode(
            {
                "latitude": ",".join(f"{lat:.7f}" for lat, _ in points),
                "longitude": ",".join(f"{lon:.7f}" for _, lon in points),
            }
        )
        request = Request(
            f"{self.endpoint}?{query}",
            headers={"User-Agent": "Flemme real-graph loader"},
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_s) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                elevations = parse_open_meteo_elevation_response(payload)
                if len(elevations) != len(points):
                    raise ValueError(
                        "Open-Meteo returned a different number of elevations than requested."
                    )
                return elevations
            except HTTPError as exc:
                last_error = exc
                if exc.code != 429 or attempt >= self.retries:
                    break
                retry_after = exc.headers.get("Retry-After")
                pause_s = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                time.sleep(pause_s)
            except Exception as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(1.0 * (attempt + 1))
        if last_error is None:
            raise RuntimeError("Open-Meteo request failed without an exception.")
        raise last_error

    def elevations(self, points: list[tuple[float, float]]) -> list[float]:
        missing: list[tuple[float, float]] = []
        for lat, lon in points:
            key = self._cache_key(lat, lon)
            if key not in self._cache:
                missing.append((lat, lon))

        for start in range(0, len(missing), self.batch_size):
            batch = missing[start : start + self.batch_size]
            elevations = self._fetch_batch(batch)
            for (lat, lon), elevation in zip(batch, elevations, strict=True):
                self._cache[self._cache_key(lat, lon)] = elevation
            self._save_cache()
            time.sleep(self.batch_pause_s)

        return [self._cache[self._cache_key(lat, lon)] for lat, lon in points]
