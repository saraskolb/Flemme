from __future__ import annotations

from app.ingest.osm_import import is_walkable_way, segments_from_overpass


def test_walkable_way_filter_accepts_pedestrian_usable_roads() -> None:
    assert is_walkable_way({"highway": "footway"})
    assert is_walkable_way({"highway": "residential"})
    assert not is_walkable_way({"highway": "motorway"})
    assert not is_walkable_way({"highway": "residential", "foot": "no"})
    assert not is_walkable_way({"highway": "residential", "sidewalk": "no"})


def test_segments_from_overpass_emits_node_pair_segments() -> None:
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": 37.0, "lon": -122.0},
            {"type": "node", "id": 2, "lat": 37.0, "lon": -122.001},
            {"type": "node", "id": 3, "lat": 37.0, "lon": -122.002},
            {
                "type": "way",
                "id": 10,
                "nodes": [1, 2, 3],
                "tags": {"highway": "residential", "name": "Page Street"},
            },
        ]
    }

    segments = segments_from_overpass(payload)

    assert len(segments) == 2
    assert segments[0]["source_osm_node_id"] == 1
    assert segments[0]["target_osm_node_id"] == 2
    assert segments[0]["tags"]["name"] == "Page Street"
