# Flemme

Flemme is a hill-aware walking navigation engine for San Francisco. This first
vertical slice focuses on the custom routing core: directed pedestrian graph
models, grade processing, route scoring, A* search, route alternatives,
explanations, a synthetic San Francisco hill fixture, FastAPI endpoints, and a
PostGIS schema.

The production graph ingestion pipeline is intentionally stubbed. Live OSM,
DEM, DataSF, and Google integrations come after the synthetic graph proves the
routing behavior.

## What Works Now

- Directed graph routing with A*
- Nonnegative cost functions for fastest, balanced, avoid-hills, and
  accessibility profiles
- Grade, rolling-grade, gain/loss, and smoothing utilities
- Synthetic A/B route fixture:
  - Route A: 0.6 mi, 10 minutes, includes a 16% hill
  - Route B: 0.7 mi, 11 minutes, avoids the steep hill
- Route candidates and recommended route explanations
- FastAPI health and development synthetic-route endpoints
- PostGIS schema and initial Alembic migration
- Clean stubs for OSM, DataSF, DEM, Google, and PostGIS graph loading

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

`POST /route` is shaped for the future production PostGIS graph path. In this
first slice it returns a clear not-implemented response until real graph loading
is wired. Use `/debug/route-on-synthetic-graph` for the working route demo.

## Architecture Notes

The routing core does not call Google Maps. Google adapters are stubs reserved
for geocoding, basemaps, route display, and later external validation. Flemme's
hill-aware route optimization remains custom.

The core flow is:

1. Load a directed graph.
2. Compute edge costs for profile-specific preferences.
3. Run A* for fastest, balanced, and flattest candidates.
4. Deduplicate and lightly Pareto-prune route options.
5. Detect hill events and generate route explanations.

## Known Limitations

- Production OSM/DEM/DataSF ingestion is stubbed.
- `/route` does not yet load from PostGIS.
- Snapping is a simple nearest-node helper for fixture/development use.
- No contraction hierarchies, live traffic, mobile UI, or full Pareto label
  routing yet.

## Next Steps

1. Build cached OSM pedestrian graph ingestion for San Francisco.
2. Add DEM sampling and confidence metadata.
3. Join DataSF sidewalk, curb-ramp, and safety datasets.
4. Persist graph snapshots to PostGIS and load them behind `/route`.
5. Use Google Maps APIs for geocoding, map display, and validation baselines.
6. Add bounded Pareto route search once fixture and PostGIS tests are stable.
