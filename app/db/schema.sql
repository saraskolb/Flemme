CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE walk_nodes (
  node_id BIGINT PRIMARY KEY,
  geom geometry(Point, 26910) NOT NULL,
  geom_wgs geometry(Point, 4326),
  node_type TEXT,
  z_m DOUBLE PRECISION,
  confidence DOUBLE PRECISION DEFAULT 1.0
);

CREATE TABLE walk_edges (
  edge_id BIGINT PRIMARY KEY,
  source_node BIGINT NOT NULL REFERENCES walk_nodes(node_id),
  target_node BIGINT NOT NULL REFERENCES walk_nodes(node_id),
  geom geometry(LineString, 26910) NOT NULL,
  geom_wgs geometry(LineString, 4326),
  street_name TEXT,
  edge_type TEXT,
  length_m DOUBLE PRECISION NOT NULL,
  gain_m DOUBLE PRECISION DEFAULT 0,
  loss_m DOUBLE PRECISION DEFAULT 0,
  mean_grade DOUBLE PRECISION DEFAULT 0,
  max_uphill_grade DOUBLE PRECISION DEFAULT 0,
  max_downhill_grade DOUBLE PRECISION DEFAULT 0,
  max_abs_grade DOUBLE PRECISION DEFAULT 0,
  sustained_uphill_grade_20m DOUBLE PRECISION DEFAULT 0,
  sustained_downhill_grade_20m DOUBLE PRECISION DEFAULT 0,
  sustained_uphill_grade_50m DOUBLE PRECISION DEFAULT 0,
  sustained_downhill_grade_50m DOUBLE PRECISION DEFAULT 0,
  length_above_6pct_up_m DOUBLE PRECISION DEFAULT 0,
  length_above_8pct_up_m DOUBLE PRECISION DEFAULT 0,
  length_above_10pct_up_m DOUBLE PRECISION DEFAULT 0,
  length_above_12pct_up_m DOUBLE PRECISION DEFAULT 0,
  sidewalk_availability TEXT,
  sidewalk_width_m DOUBLE PRECISION,
  wheelchair_access TEXT,
  stairs BOOLEAN DEFAULT FALSE,
  surface TEXT,
  access TEXT DEFAULT 'unknown',
  osm_way_id BIGINT,
  source_tags JSONB DEFAULT '{}'::jsonb,
  base_time_s DOUBLE PRECISION NOT NULL,
  slope_time_s DOUBLE PRECISION NOT NULL,
  traffic_safety_score DOUBLE PRECISION DEFAULT 0,
  barrier_penalty DOUBLE PRECISION DEFAULT 0,
  uncertainty_penalty DOUBLE PRECISION DEFAULT 0,
  cost_fastest DOUBLE PRECISION,
  cost_balanced DOUBLE PRECISION,
  cost_flattest DOUBLE PRECISION,
  cost_accessible DOUBLE PRECISION
);

CREATE TABLE edge_elevation_samples (
  edge_id BIGINT REFERENCES walk_edges(edge_id),
  seq INTEGER NOT NULL,
  dist_m DOUBLE PRECISION NOT NULL,
  z_raw_m DOUBLE PRECISION NOT NULL,
  z_smooth_m DOUBLE PRECISION NOT NULL,
  grade DOUBLE PRECISION,
  rolling_grade_20m DOUBLE PRECISION,
  rolling_grade_50m DOUBLE PRECISION,
  PRIMARY KEY(edge_id, seq)
);

CREATE INDEX walk_nodes_geom_gix ON walk_nodes USING gist (geom);
CREATE INDEX walk_edges_geom_gix ON walk_edges USING gist (geom);
CREATE INDEX walk_edges_source_idx ON walk_edges (source_node);
CREATE INDEX walk_edges_target_idx ON walk_edges (target_node);
