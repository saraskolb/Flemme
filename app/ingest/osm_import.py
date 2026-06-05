from __future__ import annotations

from pathlib import Path
from typing import Any


def load_walkable_osm_segments(osm_extract_path: Path) -> list[dict[str, Any]]:
    """Load walkable raw OSM segments.

    TODO:
    - Parse a local San Francisco OSM extract.
    - Retain pedestrian-usable ways: footway, path, pedestrian, steps,
      walkable residential/service streets, and crossings.
    - Infer access restrictions and one-way pedestrian constraints.
    - Emit raw unsplit segments for preprocessing.
    """
    raise NotImplementedError("OSM ingestion is intentionally stubbed in the first slice.")
