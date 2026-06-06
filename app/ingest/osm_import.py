from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WALKABLE_HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
    "crossing",
}

BLOCKED_ACCESS_VALUES = {"no", "private", "customers", "permit"}


def is_walkable_way(tags: dict[str, Any]) -> bool:
    highway = tags.get("highway")
    if highway not in WALKABLE_HIGHWAYS:
        return False
    if str(tags.get("access", "")).lower() in BLOCKED_ACCESS_VALUES:
        return False
    if str(tags.get("foot", "")).lower() in BLOCKED_ACCESS_VALUES:
        return False
    return not (str(tags.get("sidewalk", "")).lower() == "no" and highway not in {
        "footway",
        "path",
        "pedestrian",
        "steps",
        "crossing",
    })


def overpass_query_for_bbox(south: float, west: float, north: float, east: float) -> str:
    highway_pattern = "|".join(sorted(WALKABLE_HIGHWAYS))
    return f"""
    [out:json][timeout:120];
    (
      way["highway"~"^({highway_pattern})$"]({south},{west},{north},{east});
    );
    (._;>;);
    out body;
    """


def fetch_overpass_json(
    query: str,
    endpoint: str = "https://overpass-api.de/api/interpreter",
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "Flemme real-graph loader"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Overpass response must be a JSON object.")
    return payload


def segments_from_overpass(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes_by_id: dict[int, dict[str, float]] = {}
    ways: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        if element.get("type") == "node":
            nodes_by_id[int(element["id"])] = {
                "lat": float(element["lat"]),
                "lon": float(element["lon"]),
            }
        elif element.get("type") == "way":
            ways.append(element)

    segments: list[dict[str, Any]] = []
    for way in ways:
        tags = way.get("tags", {})
        if not is_walkable_way(tags):
            continue
        way_nodes = [int(node_id) for node_id in way.get("nodes", [])]
        for source_osm_id, target_osm_id in zip(way_nodes, way_nodes[1:], strict=False):
            source = nodes_by_id.get(source_osm_id)
            target = nodes_by_id.get(target_osm_id)
            if source is None or target is None:
                continue
            if source["lat"] == target["lat"] and source["lon"] == target["lon"]:
                continue
            segments.append(
                {
                    "osm_way_id": int(way["id"]),
                    "source_osm_node_id": source_osm_id,
                    "target_osm_node_id": target_osm_id,
                    "source": source,
                    "target": target,
                    "geometry": [
                        (source["lon"], source["lat"]),
                        (target["lon"], target["lat"]),
                    ],
                    "tags": tags,
                }
            )
    return segments


def fetch_walkable_osm_segments_for_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    endpoint: str = "https://overpass-api.de/api/interpreter",
) -> list[dict[str, Any]]:
    payload = fetch_overpass_json(
        overpass_query_for_bbox(south=south, west=west, north=north, east=east),
        endpoint=endpoint,
    )
    return segments_from_overpass(payload)


def load_walkable_osm_segments(osm_extract_path: Path) -> list[dict[str, Any]]:
    """Load walkable raw OSM segments from a saved Overpass JSON response.

    For live data, use `fetch_walkable_osm_segments_for_bbox`.
    """
    payload = json.loads(osm_extract_path.read_text(encoding="utf-8"))
    return segments_from_overpass(payload)
