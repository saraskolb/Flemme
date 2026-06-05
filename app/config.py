from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://flemme:flemme@localhost:5432/flemme"
    )
    graph_version: str = os.getenv("GRAPH_VERSION", "dev-synthetic-001")
    environment: str = os.getenv("ENVIRONMENT", "development")


def get_settings() -> Settings:
    return Settings()
