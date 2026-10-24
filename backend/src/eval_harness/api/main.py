from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eval_harness import __version__
from eval_harness.api.routers import (
    annotations,
    catalog,
    chat,
    compare,
    data_sources,
    datasets,
    experiments,
    integrations,
)
from eval_harness.core.settings import get_settings

app = FastAPI(title="Eval Engineering Lab", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])

for r in (catalog, chat, datasets, experiments, annotations, compare, data_sources, integrations):
    app.include_router(r.router, prefix="/api")


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
