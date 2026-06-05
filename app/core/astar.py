from __future__ import annotations

from collections.abc import Callable
from heapq import heappop, heappush
from math import asin, cos, inf, radians, sin, sqrt

from app.core.models import Edge, Graph


def straight_line_distance_m(graph: Graph, start_node: int, goal_node: int) -> float:
    start = graph.nodes[start_node]
    goal = graph.nodes[goal_node]
    if start.x is not None and start.y is not None and goal.x is not None and goal.y is not None:
        return sqrt((goal.x - start.x) ** 2 + (goal.y - start.y) ** 2)

    earth_radius_m = 6_371_000.0
    lat1 = radians(start.lat)
    lat2 = radians(goal.lat)
    dlat = radians(goal.lat - start.lat)
    dlon = radians(goal.lon - start.lon)
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * earth_radius_m * asin(sqrt(a))


def walking_time_heuristic(
    graph: Graph, max_walking_speed_mps: float = 1.8
) -> Callable[[int, int], float]:
    return lambda start, goal: straight_line_distance_m(graph, start, goal) / max_walking_speed_mps


def astar(
    graph: Graph,
    start_node: int,
    goal_node: int,
    edge_cost: Callable[[Edge], float],
    heuristic: Callable[[int, int], float],
    edge_allowed: Callable[[Edge], bool] | None = None,
) -> list[int] | None:
    if start_node not in graph.nodes or goal_node not in graph.nodes:
        return None
    if start_node == goal_node:
        return []

    frontier: list[tuple[float, int, int]] = []
    sequence = 0
    heappush(frontier, (0.0, sequence, start_node))
    cost_so_far: dict[int, float] = {start_node: 0.0}
    came_from_edge: dict[int, int] = {}
    came_from_node: dict[int, int] = {}

    while frontier:
        _, _, current_node = heappop(frontier)
        if current_node == goal_node:
            break

        for edge in graph.outgoing_edges(current_node):
            if edge_allowed is not None and not edge_allowed(edge):
                continue
            step_cost = edge_cost(edge)
            if step_cost == inf or step_cost < 0:
                continue
            next_cost = cost_so_far[current_node] + step_cost
            if next_cost < cost_so_far.get(edge.target, inf):
                cost_so_far[edge.target] = next_cost
                came_from_node[edge.target] = current_node
                came_from_edge[edge.target] = edge.edge_id
                sequence += 1
                priority = next_cost + heuristic(edge.target, goal_node)
                heappush(frontier, (priority, sequence, edge.target))

    if goal_node not in came_from_edge:
        return None

    edge_ids: list[int] = []
    current = goal_node
    while current != start_node:
        edge_ids.append(came_from_edge[current])
        current = came_from_node[current]
    edge_ids.reverse()
    return edge_ids
