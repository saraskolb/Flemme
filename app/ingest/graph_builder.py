from __future__ import annotations

from typing import Any

from app.core.models import Graph


def build_directed_graph(raw_segments: list[dict[str, Any]]) -> Graph:
    """Build a directed graph from preprocessed pedestrian segments."""
    raise NotImplementedError(
        "Graph building from real data is deferred until after the fixture slice."
    )
