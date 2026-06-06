from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    graph_json_path: str | None
    graph_version: str
    environment: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://flemme:flemme@localhost:5432/flemme"
        ),
        graph_json_path=os.getenv("GRAPH_JSON_PATH"),
        graph_version=os.getenv("GRAPH_VERSION", "dev-synthetic-001"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )
