from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.core.edge_naming import OfficialStreetName, format_street_name

DATASF_STREETS_DATASET = "datasf_streets_active_retired"
DATASF_STREETS_GEOJSON_URL = (
    "https://data.sfgov.org/resource/3psu-pn9h.geojson?$limit=50000"
)


def download_datasf_street_centerlines(
    output_path: Path,
    url: str = DATASF_STREETS_GEOJSON_URL,
) -> Path:
    """Download official San Francisco street centerlines to a local GeoJSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={"User-Agent": "Flemme/0.1 street-name-conflation"},
    )
    with urlopen(request, timeout=60.0) as response:
        output_path.write_bytes(response.read())
    return output_path


def load_datasf_street_centerlines(path: Path) -> list[OfficialStreetName]:
    """Load DataSF Streets - Active and Retired GeoJSON centerline records."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"Expected GeoJSON FeatureCollection in {path}")

    centerlines: list[OfficialStreetName] = []
    for feature in payload.get("features", []):
        centerlines.extend(_centerlines_from_feature(feature))
    return centerlines


def load_datasf_attributes(data_dir: Path) -> dict[str, Any]:
    """Load San Francisco pedestrian-quality and safety datasets.

    Street naming now has a real DataSF implementation via
    ``load_datasf_street_centerlines``. The remaining sidewalk-quality layers
    are still intentionally stubbed.
    """
    raise NotImplementedError("Sidewalk-quality DataSF ingestion is not implemented yet.")


def _centerlines_from_feature(feature: dict[str, Any]) -> list[OfficialStreetName]:
    geometry = feature.get("geometry") or {}
    properties = feature.get("properties") or {}
    street_name = properties.get("streetname") or properties.get("streetname_gc")
    if not street_name:
        return []

    display_name = format_street_name(str(street_name))
    source_feature_id = str(properties.get("cnn") or "")
    active = _truthy(properties.get("active"))

    if geometry.get("type") == "LineString":
        coordinate_sets = [geometry.get("coordinates", [])]
    elif geometry.get("type") == "MultiLineString":
        coordinate_sets = geometry.get("coordinates", [])
    else:
        return []

    centerlines: list[OfficialStreetName] = []
    for index, coordinates in enumerate(coordinate_sets):
        line = [(float(lon), float(lat)) for lon, lat, *_ in coordinates]
        if len(line) < 2:
            continue
        feature_id = source_feature_id
        if len(coordinate_sets) > 1:
            feature_id = f"{source_feature_id}:{index}"
        centerlines.append(
            OfficialStreetName(
                display_name=display_name,
                source_dataset=DATASF_STREETS_DATASET,
                source_feature_id=feature_id,
                geometry=line,
                active=active,
                properties={str(key): value for key, value in properties.items()},
            )
        )
    return centerlines


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}
