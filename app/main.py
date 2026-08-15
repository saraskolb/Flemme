from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

STATIC_DIR = Path(__file__).with_name("static")

app = FastAPI(
    title="Flemme",
    summary="Hill-aware walking navigation for San Francisco.",
    version="0.1.0",
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
