from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import create_engine, text

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


def graph_to_mapping(graph: Graph) -> dict[str, Any]:
    return {
        "version": graph.version,
        "nodes": [asdict(node) for node in graph.nodes.values()],
        "edges": [asdict(edge) for edge in graph.edges.values()],
    }


def save_graph_json(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph_to_mapping(graph), indent=2), encoding="utf-8")


class JSONGraphRepository:
    def __init__(self, graph_path: Path) -> None:
        self.graph_path = graph_path

    def load_graph(self) -> Graph:
        if not self.graph_path.exists():
            raise GraphUnavailable(f"Graph JSON does not exist: {self.graph_path}")
        return graph_from_mapping(json.loads(self.graph_path.read_text(encoding="utf-8")))


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
        try:
            engine = create_engine(self.database_url, future=True)
            with engine.connect() as connection:
                node_rows = connection.execute(
                    text(
                        """
                        SELECT
                          node_id,
                          ST_X(geom_wgs) AS lon,
                          ST_Y(geom_wgs) AS lat,
                          ST_X(geom) AS x,
                          ST_Y(geom) AS y,
                          z_m,
                          COALESCE(node_type, 'intersection') AS node_type
                        FROM walk_nodes
                        ORDER BY node_id
                        """
                    )
                ).mappings()
                nodes = {
                    int(row["node_id"]): Node(
                        node_id=int(row["node_id"]),
                        lon=float(row["lon"]),
                        lat=float(row["lat"]),
                        x=float(row["x"]) if row["x"] is not None else None,
                        y=float(row["y"]) if row["y"] is not None else None,
                        z_m=float(row["z_m"]) if row["z_m"] is not None else None,
                        node_type=str(row["node_type"]),
                    )
                    for row in node_rows
                }

                sample_rows = connection.execute(
                    text(
                        """
                        SELECT
                          edge_id, seq, dist_m, z_raw_m, z_smooth_m,
                          grade, rolling_grade_20m, rolling_grade_50m
                        FROM edge_elevation_samples
                        ORDER BY edge_id, seq
                        """
                    )
                ).mappings()
                samples_by_edge: dict[int, list[ElevationSample]] = {}
                for row in sample_rows:
                    samples_by_edge.setdefault(int(row["edge_id"]), []).append(
                        ElevationSample(
                            dist_m=float(row["dist_m"]),
                            z_raw_m=float(row["z_raw_m"]),
                            z_smooth_m=float(row["z_smooth_m"]),
                            grade=float(row["grade"]) if row["grade"] is not None else None,
                            rolling_grade_20m=float(row["rolling_grade_20m"])
                            if row["rolling_grade_20m"] is not None
                            else None,
                            rolling_grade_50m=float(row["rolling_grade_50m"])
                            if row["rolling_grade_50m"] is not None
                            else None,
                        )
                    )

                edge_rows = connection.execute(
                    text(
                        """
                        SELECT
                          edge_id,
                          source_node AS source,
                          target_node AS target,
                          ST_AsGeoJSON(geom_wgs)::json AS geometry_json,
                          street_name,
                          edge_type,
                          length_m,
                          gain_m,
                          loss_m,
                          mean_grade,
                          max_uphill_grade,
                          max_downhill_grade,
                          max_abs_grade,
                          sustained_uphill_grade_20m,
                          sustained_downhill_grade_20m,
                          sustained_uphill_grade_50m,
                          sustained_downhill_grade_50m,
                          length_above_6pct_up_m,
                          length_above_8pct_up_m,
                          length_above_10pct_up_m,
                          length_above_12pct_up_m,
                          sidewalk_availability,
                          sidewalk_width_m,
                          wheelchair_access,
                          stairs,
                          surface,
                          access,
                          base_time_s,
                          slope_time_s,
                          traffic_safety_score,
                          barrier_penalty,
                          uncertainty_penalty
                        FROM walk_edges
                        ORDER BY edge_id
                        """
                    )
                ).mappings()

                edges: dict[int, Edge] = {}
                for row in edge_rows:
                    edge_id = int(row["edge_id"])
                    geometry_json = row["geometry_json"]
                    if isinstance(geometry_json, str):
                        geometry_json = json.loads(geometry_json)
                    geometry = [tuple(point) for point in geometry_json["coordinates"]]
                    edges[edge_id] = Edge(
                        edge_id=edge_id,
                        source=int(row["source"]),
                        target=int(row["target"]),
                        geometry=geometry,
                        length_m=float(row["length_m"]),
                        street_name=row["street_name"],
                        edge_type=str(row["edge_type"] or "sidewalk"),
                        access=str(row["access"] or "unknown"),
                        sidewalk_availability=row["sidewalk_availability"],
                        sidewalk_width_m=float(row["sidewalk_width_m"])
                        if row["sidewalk_width_m"] is not None
                        else None,
                        wheelchair_access=row["wheelchair_access"],
                        stairs=bool(row["stairs"]),
                        surface=row["surface"],
                        samples=samples_by_edge.get(edge_id, []),
                        gain_m=float(row["gain_m"] or 0.0),
                        loss_m=float(row["loss_m"] or 0.0),
                        mean_grade=float(row["mean_grade"] or 0.0),
                        max_uphill_grade=float(row["max_uphill_grade"] or 0.0),
                        max_downhill_grade=float(row["max_downhill_grade"] or 0.0),
                        max_abs_grade=float(row["max_abs_grade"] or 0.0),
                        sustained_uphill_grade_20m=float(
                            row["sustained_uphill_grade_20m"] or 0.0
                        ),
                        sustained_downhill_grade_20m=float(
                            row["sustained_downhill_grade_20m"] or 0.0
                        ),
                        sustained_uphill_grade_50m=float(
                            row["sustained_uphill_grade_50m"] or 0.0
                        ),
                        sustained_downhill_grade_50m=float(
                            row["sustained_downhill_grade_50m"] or 0.0
                        ),
                        length_above_6pct_up_m=float(row["length_above_6pct_up_m"] or 0.0),
                        length_above_8pct_up_m=float(row["length_above_8pct_up_m"] or 0.0),
                        length_above_10pct_up_m=float(row["length_above_10pct_up_m"] or 0.0),
                        length_above_12pct_up_m=float(row["length_above_12pct_up_m"] or 0.0),
                        base_time_s=float(row["base_time_s"]),
                        slope_time_s=float(row["slope_time_s"]),
                        traffic_safety_score=float(row["traffic_safety_score"] or 0.0),
                        barrier_penalty=float(row["barrier_penalty"] or 0.0),
                        uncertainty_penalty=float(row["uncertainty_penalty"] or 0.0),
                    )

                if not nodes or not edges:
                    raise GraphUnavailable("PostGIS graph tables are empty.")
                return Graph(nodes=nodes, edges=edges, version="postgis")
        except GraphUnavailable:
            raise
        except Exception as exc:
            raise GraphUnavailable(
                "Production PostGIS graph loading failed. "
                "Set GRAPH_JSON_PATH to a real graph JSON cache or load PostGIS first."
            ) from exc


def _linestring_wkt(geometry: list[tuple[float, float]]) -> str:
    coordinates = ", ".join(f"{lon} {lat}" for lon, lat in geometry)
    return f"LINESTRING({coordinates})"


def save_graph_to_postgis(graph: Graph, database_url: str, truncate: bool = True) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(text(schema_path.read_text(encoding="utf-8")))
        if truncate:
            connection.execute(text("TRUNCATE edge_elevation_samples, walk_edges, walk_nodes;"))

        for node in graph.nodes.values():
            connection.execute(
                text(
                    """
                    INSERT INTO walk_nodes (node_id, geom, geom_wgs, node_type, z_m)
                    VALUES (
                      :node_id,
                      ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26910),
                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                      :node_type,
                      :z_m
                    )
                    ON CONFLICT (node_id) DO UPDATE SET
                      geom = EXCLUDED.geom,
                      geom_wgs = EXCLUDED.geom_wgs,
                      node_type = EXCLUDED.node_type,
                      z_m = EXCLUDED.z_m
                    """
                ),
                {
                    "node_id": node.node_id,
                    "lon": node.lon,
                    "lat": node.lat,
                    "node_type": node.node_type,
                    "z_m": node.z_m,
                },
            )

        for edge in graph.edges.values():
            connection.execute(
                text(
                    """
                    INSERT INTO walk_edges (
                      edge_id, source_node, target_node, geom, geom_wgs, street_name,
                      edge_type, length_m, gain_m, loss_m, mean_grade,
                      max_uphill_grade, max_downhill_grade, max_abs_grade,
                      sustained_uphill_grade_20m, sustained_downhill_grade_20m,
                      sustained_uphill_grade_50m, sustained_downhill_grade_50m,
                      length_above_6pct_up_m, length_above_8pct_up_m,
                      length_above_10pct_up_m, length_above_12pct_up_m,
                      sidewalk_availability, sidewalk_width_m, wheelchair_access,
                      stairs, surface, access, base_time_s, slope_time_s,
                      traffic_safety_score, barrier_penalty, uncertainty_penalty
                    )
                    VALUES (
                      :edge_id, :source, :target,
                      ST_Transform(ST_GeomFromText(:linestring_wkt, 4326), 26910),
                      ST_GeomFromText(:linestring_wkt, 4326),
                      :street_name, :edge_type, :length_m, :gain_m, :loss_m,
                      :mean_grade, :max_uphill_grade, :max_downhill_grade,
                      :max_abs_grade, :sustained_uphill_grade_20m,
                      :sustained_downhill_grade_20m, :sustained_uphill_grade_50m,
                      :sustained_downhill_grade_50m, :length_above_6pct_up_m,
                      :length_above_8pct_up_m, :length_above_10pct_up_m,
                      :length_above_12pct_up_m, :sidewalk_availability,
                      :sidewalk_width_m, :wheelchair_access, :stairs, :surface,
                      :access, :base_time_s, :slope_time_s, :traffic_safety_score,
                      :barrier_penalty, :uncertainty_penalty
                    )
                    ON CONFLICT (edge_id) DO NOTHING
                    """
                ),
                {
                    **asdict(edge),
                    "linestring_wkt": _linestring_wkt(edge.geometry),
                },
            )

            for seq, sample in enumerate(edge.samples):
                connection.execute(
                    text(
                        """
                        INSERT INTO edge_elevation_samples (
                          edge_id, seq, dist_m, z_raw_m, z_smooth_m, grade,
                          rolling_grade_20m, rolling_grade_50m
                        )
                        VALUES (
                          :edge_id, :seq, :dist_m, :z_raw_m, :z_smooth_m, :grade,
                          :rolling_grade_20m, :rolling_grade_50m
                        )
                        ON CONFLICT (edge_id, seq) DO NOTHING
                        """
                    ),
                    {"edge_id": edge.edge_id, "seq": seq, **asdict(sample)},
                )
