"""RECOURSE API server."""
from __future__ import annotations

from fastapi import FastAPI

from .routes import router

app = FastAPI(title="RECOURSE", description="Autonomous recovery control plane.")
app.include_router(router)
