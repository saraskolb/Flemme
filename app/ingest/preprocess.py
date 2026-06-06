from __future__ import annotations

from typing import Any

from app.core.models import Graph
from app.ingest.elevation import ElevationProvider
from app.ingest.graph_builder import build_directed_graph


def preprocess_raw_segments(
    raw_segments: list[dict[str, Any]],
    elevation_provider: ElevationProvider | None = None,
    graph_version: str = "sf-osm-dev",
) -> Graph:
    """Prepare raw pedestrian segments for routing.

    This first real-data slice turns OSM node-pair segments into directed edges
    and computes elevation/grade metrics. Full sidewalk and safety joins come
    in the DataSF slice.
    """
    return build_directed_graph(
        raw_segments,
        elevation_provider=elevation_provider,
        graph_version=graph_version,
    )
