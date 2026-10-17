from __future__ import annotations

from math import cos, radians

from app.core.models import Graph, Node


def nearest_node(graph: Graph, lat: float, lon: float) -> Node | None:
    if not graph.nodes:
        return None

    lon_scale = cos(radians(lat))
    return min(
        graph.nodes.values(),
        key=lambda node: (node.lat - lat) ** 2 + ((node.lon - lon) * lon_scale) ** 2,
    )


def snap_point_to_graph(graph: Graph, lat: float, lon: float) -> int | None:
    node = nearest_node(graph, lat=lat, lon=lon)
    return node.node_id if node is not None else None
