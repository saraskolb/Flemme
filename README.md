# Flemme

Flemme is a hill-aware walking navigation engine for San Francisco. This first
vertical slice focuses on the custom routing core: directed pedestrian graph
models, grade processing, route scoring, A* search, route alternatives,
explanations, a synthetic San Francisco hill fixture, FastAPI endpoints, and a
PostGIS schema.

The real-data path can now load bounded and city-wide San Francisco walking
graphs from OSM via Overpass, enrich them with local USGS DEM rasters, batch
Open-Meteo elevations, or slower USGS EPQS elevations, match edges to official
DataSF street centerline names, and route against a graph JSON cache. Google
validation adapters are still future work.

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
- Local DEM raster elevation sampling for coarse city-wide and dense
  neighborhood graph builds
- File-backed `/route` via `GRAPH_JSON_PATH`
- DataSF street centerline edge naming, with clean stubs for remaining DataSF
  pedestrian-quality joins and Google validation adapters

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

Run the field-reviewed citywide route diary before tuning the route algorithm:

```bash
pytest tests/test_route_regressions.py
```

Those cases live in `tests/fixtures/route_regression_cases.json`. Add routes
there when field testing finds a known-good recommendation or a route Flemme
should avoid repeating.

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

The FastAPI app also serves a small local route-planner UI at `/`. To run it
against the city-wide San Francisco DEM graph:

```bash
scripts/run_local_sf_ui.sh
```

Then open http://127.0.0.1:8000/ and enter San Francisco start and destination
addresses. The launcher uses `data/graphs/sf_walk_graph_dem_10m.json` when it
exists and falls back to `data/graphs/sf_walk_graph_dem_100m.json` otherwise.
The city-wide JSON cache is large, so the first route request may take around
20 seconds while the graph loads; subsequent route queries reuse the cached
graph in memory.

The UI is installable as a lightweight phone PWA when served over localhost or
HTTPS. It uses web map tiles when the phone has internet access, can follow the
current GPS position while the page is open, and posts route feedback to
`POST /feedback`. Feedback is appended to
`data/feedback/route_feedback.jsonl` by default; set `FEEDBACK_JSONL_PATH` to
write it somewhere else.

For phone testing on the same trusted Wi-Fi network, bind the server to your
Mac's network interface:

```bash
HOST=0.0.0.0 PORT=8002 scripts/run_local_sf_ui.sh
```

Then open `http://<your-mac-ip>:8002/` on the phone. GPS permissions generally
require localhost or HTTPS; use a tunnel such as Cloudflare Tunnel or Tailscale
Serve when you need a true installable HTTPS phone build away from localhost.

For a native iPhone field-testing shell, open
`ios/Flemme/Flemme.xcodeproj` in Xcode. The app is a minimal SwiftUI wrapper
around the local Flemme UI and currently loads
`https://macbook-pro.tail6ab8cd.ts.net/`, which should be served from the Mac:

```bash
HOST=0.0.0.0 PORT=8005 scripts/run_local_sf_ui.sh
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve --bg 8005
```

Keep the Mac awake, keep Tailscale connected on the iPhone, then build and run
the `Flemme` scheme from Xcode on a trusted iPhone. The routing algorithm and
full city graph still run on the Mac backend; the iPhone app provides the
walking UI, map, GPS prompt, and route feedback controls.

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
  --download-street-centerlines \
  --output data/graphs/page_duboce_walk_graph.json
```

Open-Meteo is the fast bootstrap provider and supports batch coordinate
requests. USGS EPQS is available with `--elevation-provider usgs`; it is more
appropriate for high-resolution validation but is slower because it queries one
point at a time. Production city-wide loading should use a local DEM raster.

Download the USGS 1/3 arc-second DEM tile that covers San Francisco:

```bash
mkdir -p data/dem
curl -L \
  https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n38w123/USGS_13_n38w123.tif \
  -o data/dem/USGS_13_n38w123.tif
```

Optionally write the same graph to PostGIS:

```bash
python -m app.ingest.load_sf_graph \
  --preset page-duboce \
  --elevation-provider open-meteo \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
  --database-url "$DATABASE_URL"
```

Apply official street names to an existing graph cache:

```bash
python -m app.ingest.name_graph_edges \
  --graph data/graphs/page_duboce_walk_graph.json \
  --download-street-centerlines
```

Recompute an existing graph cache with denser USGS elevation samples:

```bash
python -m app.ingest.enrich_graph_elevations \
  --graph data/graphs/page_duboce_walk_graph.json \
  --output data/graphs/page_duboce_walk_graph_usgs_10m.json \
  --sample-spacing-m 10 \
  --elevation-provider usgs \
  --elevation-cache data/cache/usgs_epqs.json \
  --graph-version sf-osm-usgs-page-duboce-10m-001
```

Load the tighter Page Street to Saturn Street Steps validation corridor:

```bash
python -m app.ingest.load_sf_graph \
  --south 37.7618 \
  --west -122.4436 \
  --north 37.7728 \
  --east -122.4364 \
  --elevation-provider flat \
  --sample-spacing-m 500 \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
  --output data/graphs/page_saturn_tight_walk_graph_flat.json \
  --graph-version sf-osm-datasf-page-saturn-tight-flat-001
```

Then add a USGS elevation layer for route validation:

```bash
python -m app.ingest.enrich_graph_elevations \
  --graph data/graphs/page_saturn_tight_walk_graph_flat.json \
  --output data/graphs/page_saturn_tight_walk_graph.json \
  --sample-spacing-m 25 \
  --elevation-provider usgs \
  --elevation-cache data/cache/usgs_epqs.json \
  --usgs-max-workers 4 \
  --graph-version sf-osm-usgs-page-saturn-tight-25m-001
```

Load the city-wide SF topology/name graph with flat elevation:

```bash
python -m app.ingest.load_sf_graph \
  --preset sf \
  --elevation-provider flat \
  --sample-spacing-m 500 \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
  --output data/graphs/sf_walk_graph_flat.json \
  --graph-version sf-osm-datasf-flat-001
```

This is a topology and naming milestone, not the final hill-aware city graph.
The current build has 205,389 nodes, 483,700 directed edges, about 4,097 km of
undirected walkable geometry, and a 1.0 GB JSON cache. Elevation is flat, so use
it for coverage, naming, snapping, and direction smoke tests only.

Current city-wide naming baseline:

- Display-name coverage: 100%.
- DataSF official-name rate: 80.3%.
- Generic non-stairs rate: 9.7%.
- Generic unnamed residential/unclassified/road edges: 274 directed edges.
- Long generic connectors remain high because true paths, plazas, and service
  alleys are still represented in the walkable graph.

For city-wide hill-aware routing, prefer loading this graph into PostGIS or a
tiled cache and enriching elevations from a local DEM raster instead of calling
point-elevation APIs for the whole city.

Add a coarse city-wide DEM baseline:

```bash
python -m app.ingest.enrich_graph_elevations \
  --graph data/graphs/sf_walk_graph_flat.json \
  --output data/graphs/sf_walk_graph_dem_100m.json \
  --sample-spacing-m 100 \
  --elevation-provider dem \
  --dem-path data/dem/USGS_13_n38w123.tif \
  --graph-version sf-osm-datasf-dem100m-001
```

The current coarse city graph has 211,934 unique DEM sample points and 980,490
edge elevation samples. It is useful for broad hill signal and route smoke
tests, but it is still too coarse for final sidewalk-grade decisions.

Add the fine-grained city-wide DEM graph used by the local UI when present:

```bash
python -m app.ingest.enrich_graph_elevations \
  --graph data/graphs/sf_walk_graph_flat.json \
  --output data/graphs/sf_walk_graph_dem_10m.json \
  --sample-spacing-m 10 \
  --elevation-provider dem \
  --dem-path data/dem/USGS_13_n38w123.tif \
  --graph-version sf-osm-datasf-dem10m-001 \
  --progress-every 25000
```

This uses the same routing, recommendation, naming, and direction rules as the
neighborhood validation graphs; only the graph extent changes to all of San
Francisco.

Load a dense Panhandle/Cole Valley graph for hill-routing validation:

```bash
python -m app.ingest.load_sf_graph \
  --south 37.7580 \
  --west -122.4635 \
  --north 37.7765 \
  --east -122.4380 \
  --elevation-provider dem \
  --dem-path data/dem/USGS_13_n38w123.tif \
  --sample-spacing-m 10 \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
  --output data/graphs/panhandle_cole_walk_graph_dem_10m.json \
  --graph-version sf-osm-datasf-panhandle-cole-dem10m-001
```

The current dense neighborhood graph has 12,524 nodes, 28,834 directed edges,
88,860 edge elevation samples, and about 223 km of undirected walkable geometry.
Use this graph for near-term hill-route tests before enriching all SF at 10 m.

Load a dense NOPA, Anza Vista, Fillmore, lower Pacific Heights, Cathedral Hill,
and Japantown graph for the Page Street to Post/Webster validation route:

```bash
python -m app.ingest.load_sf_graph \
  --south 37.7685 \
  --west -122.4460 \
  --north 37.7920 \
  --east -122.4200 \
  --elevation-provider dem \
  --dem-path data/dem/USGS_13_n38w123.tif \
  --sample-spacing-m 10 \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
  --output data/graphs/nopa_fillmore_japantown_walk_graph_dem_10m.json \
  --graph-version sf-osm-datasf-nopa-fillmore-japantown-dem10m-002
```

The current build has 12,650 nodes, 31,038 directed edges, 104,684 edge
elevation samples, about 289 km of undirected walkable geometry, and no
route-direction quality issues for the Page Street to Post/Webster route.
Drive-throughs, driveways, and parking aisles are filtered out of the walkable
graph; true pedestrian plazas remain routable as pedestrian areas.

## Debug The Graph On A Map

Export a route as GeoJSON plus a local Leaflet preview:

```bash
python -m app.debug.export_route \
  --graph data/graphs/page_duboce_walk_graph.json \
  --street-centerlines-geojson data/cache/datasf_streets_active_retired.geojson \
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

## Audit Graph Quality

Run the repeatable graph-quality audit for the Page Street to Duboce/Noe
validation route:

```bash
python -m app.debug.audit_graph \
  --graph data/graphs/page_duboce_walk_graph.json \
  --origin-lat 37.7714654 \
  --origin-lon -122.4412496 \
  --destination-lat 37.76919 \
  --destination-lon -122.43357 \
  --mode balanced \
  --fail-on-thresholds
```

The audit checks graph integrity, display-name coverage, DataSF naming coverage,
remaining generic-name rates, long generic connector counts, and route
directions that still contain vague labels or suspicious tiny turn fragments.

## Edge Naming Policy

Flemme keeps raw OSM names and user-facing names separate. `street_name` is the
name OSM actually supplied. `display_name` is the name Flemme shows for an edge.
Production SF graph builds should match every street, sidewalk, and crossing
edge against the official DataSF Streets - Active and Retired centerline layer.
Matched edges store `source_dataset`, `source_feature_id`, `name_confidence`,
and `name_status`, so instructions like `Turn left onto Page Street` trace back
to a civic centerline record.

OSM names and graph-topology inference are fallbacks for edges that cannot be
matched. Generic labels should remain only for true paths, stairs, park walks,
alleys, and genuinely unnamed ways. `name_source` records whether a label came
from DataSF, OSM, adjacency inference, or a generic fallback so suspicious names
can be audited on the debug map.

## Architecture Notes

The routing core does not call Google Maps. Google adapters are reserved for
geocoding, basemaps, route display, and later external validation. Flemme can
build manual Google Maps walking comparison links, but programmatic Google
route baselines require a configured Google Routes API key. Flemme's hill-aware
route optimization remains custom.

The core flow is:

1. Load a directed graph.
2. Compute edge costs for profile-specific preferences.
3. Run A* for fastest, balanced, and flattest candidates.
4. Deduplicate and lightly Pareto-prune route options.
5. Detect hill events and generate route explanations.

## Known Limitations

- DataSF street centerline naming is implemented; sidewalk/safety joins are
  still stubbed.
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
