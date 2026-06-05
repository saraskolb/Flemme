from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Protocol

from app.core.grade import aggregate_edge_grade_metrics, with_rolling_grades
from app.core.models import Edge, ElevationSample, Graph, Node


class GraphUnavailable(RuntimeError):
    """Raised when a production graph is not ready for routing."""


class GraphRepository(Protocol):
    def load_graph(self) -> Graph:
        """Load a directed walking graph."""


def _known_dataclass_kwargs(cls: type[Any], data: dict[str, Any]) -> dict[str, Any]:
    valid_names = {field.name for field in fields(cls) if field.init}
    return {key: value for key, value in data.items() if key in valid_names}


def _node_from_dict(data: dict[str, Any]) -> Node:
    return Node(**_known_dataclass_kwargs(Node, data))


def _sample_from_dict(data: dict[str, Any]) -> ElevationSample:
    return ElevationSample(**_known_dataclass_kwargs(ElevationSample, data))


def _edge_from_dict(data: dict[str, Any]) -> Edge:
    edge_data = dict(data)
    raw_samples = edge_data.pop("samples", [])
    samples = with_rolling_grades([_sample_from_dict(sample) for sample in raw_samples])
    if samples:
        metrics = aggregate_edge_grade_metrics(samples)
        for key, value in metrics.items():
            edge_data.setdefault(key, value)
        edge_data.setdefault("length_m", samples[-1].dist_m - samples[0].dist_m)

    if "geometry" in edge_data:
        edge_data["geometry"] = [tuple(point) for point in edge_data["geometry"]]

    edge = Edge(samples=samples, **_known_dataclass_kwargs(Edge, edge_data))
    if edge.base_time_s <= 0:
        edge.base_time_s = edge.length_m / 1.34
    return edge


def graph_from_mapping(data: dict[str, Any]) -> Graph:
    nodes = {
        int(node["node_id"]): _node_from_dict(node)
        for node in data.get("nodes", [])
    }
    edges = {
        int(edge["edge_id"]): _edge_from_dict(edge)
        for edge in data.get("edges", [])
    }
    return Graph(nodes=nodes, edges=edges, version=data.get("version", "dev-synthetic-001"))


class SyntheticGraphRepository:
    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "synthetic_sf_hill_graph.json"
        )

    def load_graph(self) -> Graph:
        with self.fixture_path.open("r", encoding="utf-8") as fixture_file:
            return graph_from_mapping(json.load(fixture_file))


class PostGISGraphRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def load_graph(self) -> Graph:
        raise GraphUnavailable(
            "Production PostGIS graph loading is not implemented yet. "
            "Use /debug/route-on-synthetic-graph for the first vertical slice."
        )
