from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    DebugRouteRequest,
    GeocodeRequest,
    GeocodeResponse,
    HealthResponse,
    RouteRequest,
    RouteResponse,
    preferences_to_user_prefs,
    route_option_to_out,
)
from app.config import get_settings
from app.core.alternatives import generate_route_candidates
from app.core.models import Graph
from app.core.snapping import snap_point_to_graph
from app.db.repositories import (
    GraphRepository,
    GraphUnavailable,
    JSONGraphRepository,
    PostGISGraphRepository,
    SyntheticGraphRepository,
)
from app.geocoding import GeocodingLookupError, GeocodingServiceError, geocode_address

router = APIRouter()


@lru_cache(maxsize=4)
def _load_json_graph(graph_json_path: str) -> Graph:
    return JSONGraphRepository(Path(graph_json_path)).load_graph()


def _production_repository() -> GraphRepository:
    settings = get_settings()
    if settings.graph_json_path:
        return JSONGraphRepository(Path(settings.graph_json_path))
    return PostGISGraphRepository(settings.database_url)


def _load_production_graph() -> Graph:
    settings = get_settings()
    if settings.graph_json_path:
        return _load_json_graph(settings.graph_json_path)
    return _production_repository().load_graph()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    production_graph_loaded = (
        Path(settings.graph_json_path).exists() if settings.graph_json_path else False
    )
    return HealthResponse(
        status="ok",
        graph_version=settings.graph_version,
        production_graph_loaded=production_graph_loaded,
    )


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest) -> GeocodeResponse:
    try:
        result = geocode_address(request.address)
    except GeocodingLookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GeocodingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return GeocodeResponse(
        query=result.query,
        lat=result.lat,
        lon=result.lon,
        display_name=result.display_name,
    )


@router.post("/route", response_model=RouteResponse)
def route(request: RouteRequest) -> RouteResponse:
    try:
        graph = _load_production_graph()
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
