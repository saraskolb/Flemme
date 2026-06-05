from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001_initial_walk_graph"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "app" / "db" / "schema.sql"
    op.execute(schema_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS edge_elevation_samples;")
    op.execute("DROP TABLE IF EXISTS walk_edges;")
    op.execute("DROP TABLE IF EXISTS walk_nodes;")
