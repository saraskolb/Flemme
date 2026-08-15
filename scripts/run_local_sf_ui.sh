#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Run Flemme's local route-planner UI against the city-wide San Francisco graph.

Usage:
  scripts/run_local_sf_ui.sh

Optional environment variables:
  GRAPH_JSON_PATH  Graph cache to serve. Defaults to the 10 m city-wide DEM graph
                   when present, otherwise the 100 m city-wide DEM graph.
  GRAPH_VERSION    Version label shown by /health.
  HOST             Bind host. Defaults to 127.0.0.1. Use 0.0.0.0 for phone testing
                   on the same trusted network.
  PORT             Local port. Defaults to 8000.
EOF
  exit 0
fi

if [[ -z "${GRAPH_JSON_PATH:-}" ]]; then
  if [[ -f data/graphs/sf_walk_graph_dem_10m.json ]]; then
    GRAPH_JSON_PATH="data/graphs/sf_walk_graph_dem_10m.json"
    GRAPH_VERSION="${GRAPH_VERSION:-sf-osm-datasf-dem10m-001}"
  else
    GRAPH_JSON_PATH="data/graphs/sf_walk_graph_dem_100m.json"
    GRAPH_VERSION="${GRAPH_VERSION:-sf-osm-datasf-dem100m-001}"
  fi
else
  GRAPH_VERSION="${GRAPH_VERSION:-local-graph}"
fi
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [[ ! -f "$GRAPH_JSON_PATH" ]]; then
  echo "Graph JSON not found: $GRAPH_JSON_PATH" >&2
  echo "Build or copy the city-wide graph cache before starting the local UI." >&2
  exit 1
fi

export GRAPH_JSON_PATH
export GRAPH_VERSION

exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
