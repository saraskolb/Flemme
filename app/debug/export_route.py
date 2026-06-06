from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal, cast

from app.api.schemas import PreferencesIn, preferences_to_user_prefs
from app.core.alternatives import generate_route_candidates
from app.core.edge_naming import apply_official_street_names
from app.core.geojson import route_to_geojson
from app.core.models import Graph, RouteOption
from app.core.snapping import snap_point_to_graph
from app.db.repositories import JSONGraphRepository
from app.ingest.datasf_import import load_datasf_street_centerlines

ROUTE_COLORS = {
    "recommended": "#2563eb",
    "fastest": "#dc2626",
    "flattest": "#16a34a",
    "accessible": "#7c3aed",
}

RouteMode = Literal["fastest", "balanced", "avoid_hills", "accessibility", "custom"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a Flemme route debug map.")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--origin-lat", type=float, required=True)
    parser.add_argument("--origin-lon", type=float, required=True)
    parser.add_argument("--destination-lat", type=float, required=True)
    parser.add_argument("--destination-lon", type=float, required=True)
    parser.add_argument(
        "--mode",
        choices=["fastest", "balanced", "avoid_hills", "accessibility", "custom"],
        default="balanced",
    )
    parser.add_argument(
        "--route-label",
        choices=["recommended", "fastest", "flattest", "accessible", "all"],
        default="recommended",
    )
    parser.add_argument("--geojson-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path)
    parser.add_argument("--street-centerlines-geojson", type=Path)
    parser.add_argument("--street-name-match-distance-m", type=float, default=28.0)
    return parser.parse_args()


def _select_routes(routes: list[RouteOption], route_label: str) -> list[RouteOption]:
    if route_label == "all":
        return routes
    selected = [route for route in routes if route.label == route_label]
    if selected:
        return selected
    available_labels = [route.label for route in routes]
    raise ValueError(f"No route with label {route_label!r}. Available: {available_labels}")


def routes_to_geojson(
    graph: Graph,
    routes: list[RouteOption],
    start_node: int,
    goal_node: int,
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for route in routes:
        collection = route_to_geojson(
            graph,
            route,
            start_node=start_node,
            goal_node=goal_node,
            include_edges=True,
        )
        for feature in collection["features"]:
            feature["properties"]["route_label"] = route.label
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "properties": {
            "graph_version": graph.version,
            "route_labels": [route.label for route in routes],
        },
        "features": features,
    }


def _popup_js() -> str:
    return """
function popupHtml(props) {
  const rows = Object.entries(props)
    .filter(([key]) => !["edge_ids", "source_tags"].includes(key))
    .map(([key, value]) => `<tr><th>${key}</th><td>${value ?? ""}</td></tr>`)
    .join("");
  const tags = props.source_tags
    ? `<details><summary>source_tags</summary><pre>${JSON.stringify(
        props.source_tags,
        null,
        2
      )}</pre></details>`
    : "";
  return `<table>${rows}</table>${tags}`;
}
"""


def route_summaries(routes: list[RouteOption]) -> list[dict[str, Any]]:
    return [
        {
            "label": route.label,
            "time_min": round(route.metrics.time_s / 60.0, 1),
            "distance_mi": round(route.metrics.distance_m / 1609.344, 2),
            "gain_m": round(route.metrics.gain_m, 1),
            "max_uphill_grade_pct": round(route.metrics.max_uphill_grade * 100.0, 1),
            "explanation": route.explanation,
            "directions": [step.instruction for step in route.directions],
        }
        for route in routes
    ]


def render_debug_html(geojson: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    geojson_json = json.dumps(geojson)
    summaries_json = json.dumps(summaries)
    colors_json = json.dumps(ROUTE_COLORS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Flemme Route Debug Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body {{ height: 100%; margin: 0; font-family: system-ui, sans-serif; }}
    #map {{ position: absolute; inset: 0 360px 0 0; }}
    #panel {{
      position: absolute; inset: 0 0 0 auto; width: 360px; overflow: auto;
      border-left: 1px solid #ddd; padding: 16px; background: #fff;
    }}
    section + section {{ border-top: 1px solid #eee; padding-top: 16px; }}
    h1 {{ font-size: 18px; margin: 0 0 12px; }}
    h2 {{ font-size: 15px; margin: 18px 0 8px; }}
    ol {{ padding-left: 20px; }}
    li {{ margin: 8px 0; }}
    table {{ border-collapse: collapse; font-size: 12px; }}
    th {{ text-align: left; padding-right: 8px; color: #555; }}
    td {{ max-width: 210px; overflow-wrap: anywhere; }}
    pre {{ white-space: pre-wrap; font-size: 11px; }}
    @media (max-width: 760px) {{
      #map {{ inset: 0 0 45% 0; }}
      #panel {{
        inset: 55% 0 0 0; width: auto; border-left: 0; border-top: 1px solid #ddd;
      }}
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <aside id="panel"></aside>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const routeData = {geojson_json};
    const summaries = {summaries_json};
    const colors = {colors_json};
    {_popup_js()}

    const map = L.map("map");
    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 20,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    const layer = L.geoJSON(routeData, {{
      style: feature => {{
        const props = feature.properties || {{}};
        const color = colors[props.route_label] || "#f97316";
        if (props.feature_type === "route") {{
          return {{ color, weight: 7, opacity: 0.75 }};
        }}
        return {{ color: "#f97316", weight: 3, opacity: 0.85, dashArray: "4 3" }};
      }},
      pointToLayer: (feature, latlng) => {{
        const role = feature.properties?.role || "point";
        return L.circleMarker(latlng, {{
          radius: 7,
          color: role === "origin" ? "#2563eb" : "#16a34a",
          fillOpacity: 0.9
        }});
      }},
      onEachFeature: (feature, featureLayer) => {{
        featureLayer.bindPopup(popupHtml(feature.properties || {{}}), {{ maxWidth: 420 }});
      }}
    }}).addTo(map);
    map.fitBounds(layer.getBounds(), {{ padding: [24, 24] }});

    document.getElementById("panel").innerHTML = summaries.map(summary => `
      <section class="route-summary">
        <h1>${{summary.label}}</h1>
        <p>${{summary.time_min}} min, ${{summary.distance_mi}} mi, gain ${{summary.gain_m}} m,
        max uphill ${{summary.max_uphill_grade_pct}}%</p>
        <p>${{summary.explanation}}</p>
        <h2>Directions</h2>
        <ol>${{summary.directions.map(step => `<li>${{step}}</li>`).join("")}}</ol>
      </section>
    `).join("");
  </script>
</body>
</html>
"""


def export_route_debug_map(
    graph_path: Path,
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    mode: str,
    route_label: str,
    geojson_output: Path,
    html_output: Path | None = None,
    street_centerlines_geojson: Path | None = None,
    street_name_match_distance_m: float = 28.0,
) -> list[RouteOption]:
    graph = JSONGraphRepository(graph_path).load_graph()
    if street_centerlines_geojson is not None:
        apply_official_street_names(
            graph,
            load_datasf_street_centerlines(street_centerlines_geojson),
            max_distance_m=street_name_match_distance_m,
        )
    start_node = snap_point_to_graph(graph, lat=origin_lat, lon=origin_lon)
    goal_node = snap_point_to_graph(graph, lat=destination_lat, lon=destination_lon)
    if start_node is None or goal_node is None:
        raise ValueError("Could not snap origin or destination to graph.")

    prefs = preferences_to_user_prefs(PreferencesIn(mode=cast(RouteMode, mode)))
    routes = generate_route_candidates(graph, start_node, goal_node, prefs)
    selected_routes = _select_routes(routes, route_label)
    geojson = routes_to_geojson(graph, selected_routes, start_node, goal_node)

    geojson_output.parent.mkdir(parents=True, exist_ok=True)
    geojson_output.write_text(json.dumps(geojson, indent=2), encoding="utf-8")

    if html_output is not None:
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(
            render_debug_html(geojson, route_summaries(selected_routes)),
            encoding="utf-8",
        )

    return selected_routes


def main() -> None:
    args = _parse_args()
    routes = export_route_debug_map(
        graph_path=args.graph,
        origin_lat=args.origin_lat,
        origin_lon=args.origin_lon,
        destination_lat=args.destination_lat,
        destination_lon=args.destination_lon,
        mode=args.mode,
        route_label=args.route_label,
        geojson_output=args.geojson_output,
        html_output=args.html_output,
        street_centerlines_geojson=args.street_centerlines_geojson,
        street_name_match_distance_m=args.street_name_match_distance_m,
    )
    for route in routes:
        print(
            f"{route.label}: {route.metrics.time_s / 60.0:.1f} min, "
            f"{route.metrics.distance_m / 1609.344:.2f} mi, "
            f"max uphill {route.metrics.max_uphill_grade * 100.0:.1f}%"
        )


if __name__ == "__main__":
    main()
