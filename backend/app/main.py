"""ReconAgent API entrypoint."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router

_origins = os.getenv("RECONAGENT_CORS_ORIGINS", "*")
_allow_origins = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app = FastAPI(
    title="ReconAgent",
    description="Autonomous three-way reconciliation & settlement-exception agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "ReconAgent", "docs": "/docs"}
