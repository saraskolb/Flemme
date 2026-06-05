from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="Flemme",
    summary="Hill-aware walking navigation for San Francisco.",
    version="0.1.0",
)
app.include_router(router)
