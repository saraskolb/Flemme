# Flemme

Flemme is a hill-aware walking navigation engine for San Francisco. This first
vertical slice focuses on the custom routing core: directed pedestrian graph
models, grade processing, route scoring, A* search, route alternatives,
explanations, a synthetic San Francisco hill fixture, FastAPI endpoints, and a
PostGIS schema.

The real-data path can now load a bounded San Francisco walking graph from OSM
via Overpass, enrich it with batch Open-Meteo elevations or slower USGS EPQS
elevations, and route against a graph JSON cache. DataSF joins, local DEM raster
processing, and Google validation adapters are still future work.

## What Works Now

- Directed graph routing with A*
- Nonnegative cost functions for fastest, balanced, avoid-hills, and
  accessibility profiles
- Downhill grades are reported in metrics but do not affect hill avoidance
- Grade, rolling-grade, gain/loss, and smoothing utilities
- Synthetic A/B route fixture:
  - Route A: 0.6 mi, 10 minutes, includes a 16% hill
  - Route B: 0.7 mi, 11 minutes, avoids the steep hill
- Route candidates and recommended route explanations
- FastAPI health and development synthetic-route endpoints
- PostGIS schema and initial Alembic migration
- Real OSM/Overpass graph loading to JSON, plus optional PostGIS writes
- File-backed `/route` via `GRAPH_JSON_PATH`
- Clean stubs for DataSF and Google validation adapters

## Project Layout

```text
app/
  main.py
  api/
  core/
  db/
  ingest/
  google/
tests/
  fixtures/synthetic_sf_hill_graph.json
migrations/
```

## Setup

Use Python 3.12 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run Tests

```bash
pytest
```

## Run the API

Start PostGIS and the API service:

```bash
docker-compose up --build
```

Or run the API locally after installing dependencies:

```bash
uvicorn app.main:app --reload
```

To route against a loaded real graph JSON:

```bash
GRAPH_JSON_PATH=data/graphs/page_duboce_walk_graph.json uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Synthetic graph route:

```bash
curl -X POST http://localhost:8000/debug/route-on-synthetic-graph \
  -H "Content-Type: application/json" \
  -d '{"preferences":{"mode":"balanced"}}'
```

`POST /route` uses `GRAPH_JSON_PATH` when set. Without a graph JSON cache it
tries the PostGIS graph repository and returns a clear 501 if PostGIS is not
loaded yet.

## Load Real SF Data

Load the Page Street to Duboce/Noe validation corridor:

```bash
python -m app.ingest.load_sf_graph \
  --south 37.7687 \
  --west -122.4422 \
  --north 37.7732 \
  --east -122.4326 \
  --elevation-provider open-meteo \
  --sample-spacing-m 500 \
  --output data/graphs/page_duboce_walk_graph.json
```

Open-Meteo is the fast bootstrap provider and supports batch coordinate
requests. USGS EPQS is available with `--elevation-provider usgs`; it is more
appropriate for high-resolution validation but is slower because it queries one
point at a time. Production city-wide loading should use a local DEM raster.

Optionally write the same graph to PostGIS:

```bash
python -m app.ingest.load_sf_graph \
  --preset page-duboce \
  --elevation-provider open-meteo \
  --database-url "$DATABASE_URL"
```

## Debug The Graph On A Map

Export a route as GeoJSON plus a local Leaflet preview:

```bash
python -m app.debug.export_route \
  --graph data/graphs/page_duboce_walk_graph.json \
  --origin-lat 37.7714654 \
  --origin-lon -122.4412496 \
  --destination-lat 37.76919 \
  --destination-lon -122.43357 \
  --mode balanced \
  --route-label all \
  --geojson-output data/debug/page_duboce_routes.geojson \
  --html-output data/debug/page_duboce_routes.html
```

Open `data/debug/page_duboce_routes.html` in a browser. Every route segment is
clickable and shows edge ID, OSM way ID when available, street/path type,
source tags, grade, and distance. This is the first tool to use when a route
looks geographically suspicious.

## Architecture Notes

The routing core does not call Google Maps. Google adapters are reserved for
geocoding, basemaps, route display, and later external validation. Flemme's
hill-aware route optimization remains custom.

The core flow is:

1. Load a directed graph.
2. Compute edge costs for profile-specific preferences.
3. Run A* for fastest, balanced, and flattest candidates.
4. Deduplicate and lightly Pareto-prune route options.
5. Detect hill events and generate route explanations.

## Known Limitations

- DataSF sidewalk/safety joins are stubbed.
- `/route` can load graph JSON; PostGIS loading is implemented but unverified
  locally because Docker/PostGIS is not available in this environment.
- Open-Meteo elevation is coarse for sidewalk-grade decisions; use USGS EPQS or
  local DEM raster sampling for higher-resolution validation.
- Snapping is a simple nearest-node helper for fixture/development use.
- No contraction hierarchies, live traffic, mobile UI, or full Pareto label
  routing yet.

## Next Steps

1. Replace bootstrap Open-Meteo elevations with local DEM raster sampling.
2. Add address geocoding and a Google Maps validation harness.
3. Join DataSF sidewalk, curb-ramp, and safety datasets.
4. Verify PostGIS loading with Docker/PostGIS.
5. Expand from route-corridor loads to full San Francisco graph snapshots.
6. Add bounded Pareto route search once real-data tests are stable.
