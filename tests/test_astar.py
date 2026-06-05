from __future__ import annotations

from dataclasses import replace

from app.core.astar import astar
from app.core.costs import BALANCED, edge_allowed, make_edge_cost
from app.core.models import Edge, Graph, Node


def _edge(
    edge_id: int, source: int, target: int, length: float = 1.0, stairs: bool = False
) -> Edge:
    return Edge(
        edge_id=edge_id,
        source=source,
        target=target,
        geometry=[(float(source), 0.0), (float(target), 0.0)],
        length_m=length,
        base_time_s=length,
        stairs=stairs,
    )


def _graph(edges: list[Edge]) -> Graph:
    nodes = {
        node_id: Node(node_id=node_id, lon=float(node_id), lat=0.0, x=float(node_id), y=0.0)
        for node_id in {edge.source for edge in edges} | {edge.target for edge in edges}
    }
    return Graph(nodes=nodes, edges={edge.edge_id: edge for edge in edges})


def test_astar_returns_directed_edge_ids_in_order() -> None:
    graph = _graph([_edge(1, 1, 2), _edge(2, 2, 3)])

    path = astar(graph, 1, 3, edge_cost=lambda edge: edge.base_time_s, heuristic=lambda *_: 0.0)

    assert path == [1, 2]


def test_astar_handles_no_route_cases() -> None:
    graph = _graph([_edge(1, 1, 2)])

    assert (
        astar(graph, 2, 1, edge_cost=lambda edge: edge.base_time_s, heuristic=lambda *_: 0.0)
        is None
    )


def test_astar_supports_constrained_routes() -> None:
    graph = _graph([
        _edge(1, 1, 3, length=1.0, stairs=True),
        _edge(2, 1, 2, length=2.0),
        _edge(3, 2, 3, length=2.0),
    ])
    prefs = replace(BALANCED, forbid_stairs=True)

    path = astar(
        graph,
        1,
        3,
        edge_cost=make_edge_cost(prefs),
        heuristic=lambda *_: 0.0,
        edge_allowed=lambda edge: edge_allowed(edge, prefs),
    )

    assert path == [2, 3]


def test_astar_is_deterministic_for_ties() -> None:
    graph = _graph([
        _edge(10, 1, 2),
        _edge(11, 1, 3),
        _edge(12, 2, 4),
        _edge(13, 3, 4),
    ])

    first = astar(graph, 1, 4, edge_cost=lambda edge: edge.base_time_s, heuristic=lambda *_: 0.0)
    second = astar(graph, 1, 4, edge_cost=lambda edge: edge.base_time_s, heuristic=lambda *_: 0.0)

    assert first == [10, 12]
    assert second == first
