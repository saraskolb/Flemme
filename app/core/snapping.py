from __future__ import annotations

from app.core.astar import straight_line_distance_m
from app.core.models import Graph, Node


def nearest_node(graph: Graph, lat: float, lon: float) -> Node | None:
    if not graph.nodes:
        return None

    temporary_id = min(graph.nodes) - 1
    temporary_graph = Graph(
        nodes={
            **graph.nodes,
            temporary_id: Node(node_id=temporary_id, lat=lat, lon=lon),
        },
        edges=graph.edges,
        version=graph.version,
    )
    return min(
        graph.nodes.values(),
        key=lambda node: straight_line_distance_m(temporary_graph, temporary_id, node.node_id),
    )


def snap_point_to_graph(graph: Graph, lat: float, lon: float) -> int | None:
    node = nearest_node(graph, lat=lat, lon=lon)
    return node.node_id if node is not None else None
