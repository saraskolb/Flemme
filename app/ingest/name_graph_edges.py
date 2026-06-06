from __future__ import annotations

import argparse
from pathlib import Path

from app.core.edge_naming import apply_official_street_names
from app.db.repositories import JSONGraphRepository, save_graph_json
from app.ingest.datasf_import import (
    DATASF_STREETS_GEOJSON_URL,
    download_datasf_street_centerlines,
    load_datasf_street_centerlines,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply official DataSF street names to an existing Flemme graph JSON."
    )
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--street-centerlines-geojson",
        type=Path,
        default=Path("data/cache/datasf_streets_active_retired.geojson"),
    )
    parser.add_argument("--download-street-centerlines", action="store_true")
    parser.add_argument("--street-centerlines-url", default=DATASF_STREETS_GEOJSON_URL)
    parser.add_argument("--street-name-match-distance-m", type=float, default=28.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.download_street_centerlines:
        download_datasf_street_centerlines(
            args.street_centerlines_geojson,
            url=args.street_centerlines_url,
        )

    graph = JSONGraphRepository(args.graph).load_graph()
    centerlines = load_datasf_street_centerlines(args.street_centerlines_geojson)
    apply_official_street_names(
        graph,
        centerlines,
        max_distance_m=args.street_name_match_distance_m,
    )

    output = args.output or args.graph
    save_graph_json(graph, output)
    official_count = sum(
        1 for edge in graph.edges.values() if edge.name_source == "datasf_centerline"
    )
    print(
        f"Named {official_count} of {len(graph.edges)} directed edges from DataSF "
        f"and wrote {output}."
    )


if __name__ == "__main__":
    main()
