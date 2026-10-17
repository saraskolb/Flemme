from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import (
    DebugRouteRequest,
    GeocodeRequest,
    GeocodeResponse,
    GeocodeSuggestionOut,
    GeocodeSuggestionsResponse,
    HealthResponse,
    RouteFeedbackRequest,
    RouteFeedbackResponse,
    RouteRequest,
    RouteResponse,
    preferences_to_user_prefs,
    route_option_to_out,
)
from app.config import get_settings
from app.core.alternatives import generate_route_candidates
from app.core.models import Graph, RouteOption
from app.core.snapping import snap_point_to_graph
from app.db.repositories import (
    GraphRepository,
    GraphUnavailable,
    JSONGraphRepository,
    PostGISGraphRepository,
    SyntheticGraphRepository,
)
from app.feedback import append_route_feedback
from app.geocoding import (
    GeocodingLookupError,
    GeocodingServiceError,
    geocode_address,
    suggest_addresses,
)

router = APIRouter()
_loaded_graph_paths: set[str] = set()


@lru_cache(maxsize=4)
def _load_json_graph(graph_json_path: str) -> Graph:
    graph = JSONGraphRepository(Path(graph_json_path)).load_graph()
    _loaded_graph_paths.add(graph_json_path)
    return graph


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


def preload_configured_graph() -> None:
    settings = get_settings()
    if settings.graph_json_path and Path(settings.graph_json_path).exists():
        _load_json_graph(settings.graph_json_path)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    graph_exists = Path(settings.graph_json_path).exists() if settings.graph_json_path else False
    graph_status: Literal["unconfigured", "missing", "available", "ready"]
    if not settings.graph_json_path:
        graph_status = "unconfigured"
    elif not graph_exists:
        graph_status = "missing"
    elif settings.graph_json_path in _loaded_graph_paths:
        graph_status = "ready"
    else:
        graph_status = "available"
    return HealthResponse(
        status="ok",
        graph_version=settings.graph_version,
        production_graph_loaded=graph_exists,
        graph_status=graph_status,
        route_ready=graph_status == "ready",
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


@router.get("/geocode/suggest", response_model=GeocodeSuggestionsResponse)
def geocode_suggest(
    q: str = Query(min_length=2, max_length=240),
) -> GeocodeSuggestionsResponse:
    try:
        suggestions = suggest_addresses(q)
    except GeocodingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return GeocodeSuggestionsResponse(
        suggestions=[
            GeocodeSuggestionOut(
                place_id=suggestion.place_id,
                query=suggestion.result.query,
                lat=suggestion.result.lat,
                lon=suggestion.result.lon,
                display_name=suggestion.result.display_name,
            )
            for suggestion in suggestions
        ]
    )


def _route_response(graph: Graph, routes: list[RouteOption]) -> RouteResponse:
    fastest = next(route for route in routes if route.label == "fastest")
    output_routes = [route_option_to_out(route, graph=graph, fastest=fastest) for route in routes]
    preferred = next(
        (route for route in output_routes if route.label in {"recommended", "accessible"}),
        output_routes[0],
    )
    return RouteResponse(
        routes=output_routes,
        graph_version=graph.version,
        recommended_route_id=preferred.route_id,
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

    start_node = snap_point_to_graph(graph, lat=request.origin.lat, lon=request.origin.lon)
    goal_node = snap_point_to_graph(graph, lat=request.destination.lat, lon=request.destination.lon)
    if start_node is None or goal_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not snap route.")

    prefs = preferences_to_user_prefs(request.preferences)
    routes = generate_route_candidates(graph, start_node, goal_node, prefs)
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found.")
    return _route_response(graph, routes)


@router.post(
    "/feedback",
    response_model=RouteFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def feedback(request: RouteFeedbackRequest) -> RouteFeedbackResponse:
    settings = get_settings()
    saved = append_route_feedback(
        request.model_dump(mode="json"),
        Path(settings.feedback_jsonl_path),
    )
    return RouteFeedbackResponse(
        feedback_id=saved.feedback_id,
        saved_at=saved.saved_at,
        path=saved.path,
        duplicate=saved.duplicate,
    )


@router.post("/debug/route-on-synthetic-graph", response_model=RouteResponse)
def debug_route_on_synthetic_graph(request: DebugRouteRequest) -> RouteResponse:
    graph = SyntheticGraphRepository().load_graph()
    prefs = preferences_to_user_prefs(request.preferences)
    routes = generate_route_candidates(graph, request.start_node, request.goal_node, prefs)
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found.")
    return _route_response(graph, routes)
