from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    DebugRouteRequest,
    HealthResponse,
    RouteRequest,
    RouteResponse,
    preferences_to_user_prefs,
    route_option_to_out,
)
from app.config import get_settings
from app.core.alternatives import generate_route_candidates
from app.core.snapping import snap_point_to_graph
from app.db.repositories import GraphUnavailable, PostGISGraphRepository, SyntheticGraphRepository

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        graph_version=settings.graph_version,
        production_graph_loaded=False,
    )


@router.post("/route", response_model=RouteResponse)
def route(request: RouteRequest) -> RouteResponse:
    settings = get_settings()
    repository = PostGISGraphRepository(settings.database_url)
    try:
        graph = repository.load_graph()
    except GraphUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc

    start_node = snap_point_to_graph(
        graph, lat=request.origin.lat, lon=request.origin.lon
    )
    goal_node = snap_point_to_graph(
        graph, lat=request.destination.lat, lon=request.destination.lon
    )
    if start_node is None or goal_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not snap route.")

    prefs = preferences_to_user_prefs(request.preferences)
    routes = generate_route_candidates(graph, start_node, goal_node, prefs)
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found.")
    return RouteResponse(
        routes=[route_option_to_out(option) for option in routes],
        graph_version=graph.version,
    )


@router.post("/debug/route-on-synthetic-graph", response_model=RouteResponse)
def debug_route_on_synthetic_graph(request: DebugRouteRequest) -> RouteResponse:
    graph = SyntheticGraphRepository().load_graph()
    prefs = preferences_to_user_prefs(request.preferences)
    routes = generate_route_candidates(graph, request.start_node, request.goal_node, prefs)
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found.")
    return RouteResponse(
        routes=[route_option_to_out(option) for option in routes],
        graph_version=graph.version,
    )
