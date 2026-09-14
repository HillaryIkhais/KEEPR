"""RECOURSE API server.

Boots the authoritative ledger (real external system) on a background thread
when started via `uvicorn recourse.api.server:app`.  This ensures the hero
path genuinely touches external state without requiring manual multi-process
orchestration.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router

_ledger_started = False
_STATIC_DIR = Path(__file__).parent / "static"


def _start_ledger_background():
    global _ledger_started
    if _ledger_started:
        return
    _ledger_started = True
    try:
        from ..external.ledger_server import app as ledger_app
        import uvicorn

        def _run():
            uvicorn.run(ledger_app, host="127.0.0.1", port=8001,
                        log_level="error")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        import time
        time.sleep(0.2)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    _start_ledger_background()
    yield


app = FastAPI(title="KEEPR",
              description="Autonomous recovery control plane.",
              lifespan=lifespan)

app.include_router(router)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
