from __future__ import annotations

import argparse
from pathlib import Path

from app.db.repositories import JSONGraphRepository, save_graph_json
from app.ingest.elevation import (
    ElevationProvider,
    FlatElevationProvider,
    OpenMeteoElevationProvider,
    RasterElevationProvider,
    USGSElevationProvider,
)
from app.ingest.elevation_enrichment import (
    prefetch_graph_elevations,
    samples_for_geometry,
    update_edge_elevation_metrics,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute edge elevation samples and grade metrics for a graph JSON cache."
    )
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-spacing-m", type=float, default=10.0)
    parser.add_argument(
        "--elevation-provider",
        choices=["dem", "usgs", "open-meteo", "flat"],
        default="usgs",
    )
    parser.add_argument("--dem-path", type=Path)
    parser.add_argument(
        "--elevation-cache",
        type=Path,
        default=Path("data/cache/usgs_epqs.json"),
    )
    parser.add_argument("--elevation-timeout-s", type=float, default=15.0)
    parser.add_argument("--open-meteo-batch-size", type=int, default=100)
    parser.add_argument("--open-meteo-batch-pause-s", type=float, default=0.05)
    parser.add_argument("--usgs-max-workers", type=int, default=1)
    parser.add_argument("--graph-version")
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


def _elevation_provider(args: argparse.Namespace) -> ElevationProvider:
    if args.elevation_provider == "flat":
        return FlatElevationProvider()
    if args.elevation_provider == "dem":
        if args.dem_path is None:
            raise ValueError("--dem-path is required when --elevation-provider dem.")
        return RasterElevationProvider(args.dem_path)
    if args.elevation_provider == "open-meteo":
        return OpenMeteoElevationProvider(
            cache_path=args.elevation_cache.with_name("open_meteo_elevation.json"),
            timeout_s=args.elevation_timeout_s,
            batch_size=args.open_meteo_batch_size,
            batch_pause_s=args.open_meteo_batch_pause_s,
        )
    return USGSElevationProvider(
        cache_path=args.elevation_cache,
        timeout_s=args.elevation_timeout_s,
        max_workers=args.usgs_max_workers,
    )


def main() -> None:
    args = _parse_args()
    if args.sample_spacing_m <= 0:
        raise ValueError("--sample-spacing-m must be positive.")

    graph = JSONGraphRepository(args.graph).load_graph()
    total_edges = len(graph.edges)
    provider = _elevation_provider(args)
    unique_points = prefetch_graph_elevations(
        graph,
        elevation_provider=provider,
        sample_spacing_m=args.sample_spacing_m,
    )
    print(
        f"Prefetched {unique_points} unique elevation points for {total_edges} directed edges.",
        flush=True,
    )
    node_elevations: dict[int, list[float]] = {}
    for index, edge in enumerate(graph.edges.values(), start=1):
        samples = samples_for_geometry(
            edge.geometry,
            elevation_provider=provider,
            sample_spacing_m=args.sample_spacing_m,
        )
        update_edge_elevation_metrics(edge, samples)
        if samples:
            node_elevations.setdefault(edge.source, []).append(samples[0].z_smooth_m)
            node_elevations.setdefault(edge.target, []).append(samples[-1].z_smooth_m)
        if args.progress_every > 0 and index % args.progress_every == 0:
            print(f"Enriched {index}/{total_edges} directed edges...", flush=True)

    for node_id, elevations in node_elevations.items():
        if node_id in graph.nodes and elevations:
            graph.nodes[node_id].z_m = sum(elevations) / len(elevations)

    if args.graph_version:
        graph.version = args.graph_version
    else:
        spacing = f"{args.sample_spacing_m:g}".replace(".", "p")
        if f"-elev{spacing}m" not in graph.version:
            graph.version = f"{graph.version}-elev{spacing}m"

    output = args.output or args.graph
    save_graph_json(graph, output)
    print(
        f"Enriched {total_edges} directed edges at {args.sample_spacing_m:g} m spacing "
        f"and wrote {output} ({graph.version})."
    )


if __name__ == "__main__":
    main()
