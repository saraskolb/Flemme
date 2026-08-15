#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Run Flemme's local route-planner UI against the city-wide San Francisco graph.

Usage:
  scripts/run_local_sf_ui.sh

Optional environment variables:
  GRAPH_JSON_PATH  Graph cache to serve. Defaults to data/graphs/sf_walk_graph_dem_100m.json.
  GRAPH_VERSION    Version label shown by /health.
  PORT             Local port. Defaults to 8000.
EOF
  exit 0
fi

GRAPH_JSON_PATH="${GRAPH_JSON_PATH:-data/graphs/sf_walk_graph_dem_100m.json}"
GRAPH_VERSION="${GRAPH_VERSION:-sf-osm-datasf-dem100m-001}"
PORT="${PORT:-8000}"

if [[ ! -f "$GRAPH_JSON_PATH" ]]; then
  echo "Graph JSON not found: $GRAPH_JSON_PATH" >&2
  echo "Build or copy the city-wide graph cache before starting the local UI." >&2
  exit 1
fi

export GRAPH_JSON_PATH
export GRAPH_VERSION

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
