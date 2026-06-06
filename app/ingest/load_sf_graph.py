from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.db.repositories import save_graph_json, save_graph_to_postgis
from app.ingest.elevation import (
    ElevationProvider,
    FlatElevationProvider,
    OpenMeteoElevationProvider,
    USGSElevationProvider,
)
from app.ingest.graph_builder import build_directed_graph
from app.ingest.osm_import import fetch_walkable_osm_segments_for_bbox, load_walkable_osm_segments

BBOX_PRESETS = {
    "page-duboce": {
        "south": 37.7678,
        "west": -122.4412,
        "north": 37.7744,
        "east": -122.4314,
    },
    "sf": {
        "south": 37.7070,
        "west": -122.5155,
        "north": 37.8335,
        "east": -122.3550,
    },
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load a real San Francisco walking graph.")
    parser.add_argument(
        "--preset",
        choices=sorted(BBOX_PRESETS),
        default="page-duboce",
        help="Named bbox preset. Use page-duboce for the first validation route.",
    )
    parser.add_argument("--south", type=float)
    parser.add_argument("--west", type=float)
    parser.add_argument("--north", type=float)
    parser.add_argument("--east", type=float)
    parser.add_argument("--overpass-json", type=Path)
    parser.add_argument("--overpass-endpoint", default="https://overpass-api.de/api/interpreter")
    parser.add_argument(
        "--elevation-provider",
        choices=["open-meteo", "usgs", "flat"],
        default="open-meteo",
        help="Use open-meteo for fast bootstrap, usgs for slower high-resolution sampling.",
    )
    parser.add_argument(
        "--elevation-cache",
        type=Path,
        default=Path("data/cache/usgs_epqs.json"),
    )
    parser.add_argument("--elevation-timeout-s", type=float, default=30.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/graphs/page_duboce_walk_graph.json"),
    )
    parser.add_argument("--graph-version", default="sf-osm-openmeteo-page-duboce-001")
    parser.add_argument("--sample-spacing-m", type=float, default=20.0)
    parser.add_argument("--max-segments", type=int)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Optional PostGIS URL. If set, the graph is written to PostGIS too.",
    )
    return parser.parse_args()


def _bbox(args: argparse.Namespace) -> dict[str, float]:
    bbox = dict(BBOX_PRESETS[args.preset])
    for name in ("south", "west", "north", "east"):
        value = getattr(args, name)
        if value is not None:
            bbox[name] = value
    return bbox


def _elevation_provider(args: argparse.Namespace) -> ElevationProvider:
    if args.elevation_provider == "flat":
        return FlatElevationProvider()
    if args.elevation_provider == "open-meteo":
        return OpenMeteoElevationProvider(
            cache_path=args.elevation_cache.with_name("open_meteo_elevation.json"),
            timeout_s=args.elevation_timeout_s,
        )
    return USGSElevationProvider(
        cache_path=args.elevation_cache,
        timeout_s=args.elevation_timeout_s,
    )


def main() -> None:
    args = _parse_args()
    if args.overpass_json:
        raw_segments = load_walkable_osm_segments(args.overpass_json)
    else:
        bbox = _bbox(args)
        raw_segments = fetch_walkable_osm_segments_for_bbox(
            south=bbox["south"],
            west=bbox["west"],
            north=bbox["north"],
            east=bbox["east"],
            endpoint=args.overpass_endpoint,
        )

    if args.max_segments is not None:
        raw_segments = raw_segments[: args.max_segments]

    graph = build_directed_graph(
        raw_segments,
        elevation_provider=_elevation_provider(args),
        graph_version=args.graph_version,
        sample_spacing_m=args.sample_spacing_m,
    )
    save_graph_json(graph, args.output)

    if args.database_url:
        save_graph_to_postgis(graph, args.database_url)

    print(
        f"Loaded {len(graph.nodes)} nodes and {len(graph.edges)} directed edges "
        f"to {args.output} ({graph.version})."
    )


if __name__ == "__main__":
    main()
