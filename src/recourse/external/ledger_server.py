"""Genuine external system of record — the authoritative ledger HTTP service.

Runs as a real process on localhost:8001.  The AR worker fetches authoritative
records over HTTP, giving the hero path a genuinely external integration.

Attack knobs: POST /ledger/{invoice_id}/attack
  {"mode": "ok"|"stale"|"conflict"|"down"|"inflated"}
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..workloads.invoices import SOURCE_AUTHORITATIVE, ledger_amounts

app = FastAPI(title="Authoritative Ledger")

# ---- in-memory state -----------------------------------------------------------
_records: dict[str, dict] = {}
_faults: dict[str, dict] = {}


def _init_records():
    amounts = ledger_amounts(50)
    for iid, amt in amounts.items():
        _records[iid] = {
            "invoice_id": iid,
            "amount": amt,
            "currency": "USD",
            "status": "PAID",
            "source": SOURCE_AUTHORITATIVE,
        }
    _faults.clear()


_init_records()


# ---- endpoints ------------------------------------------------------------------

class AttackReq(BaseModel):
    mode: str = "ok"                # ok|stale|conflict|down|inflated


@app.get("/ledger/health")
def health():
    return {"ok": True, "records": len(_records)}


@app.get("/ledger/{invoice_id}")
def fetch_record(invoice_id: str):
    if invoice_id not in _records:
        raise HTTPException(404, "INVOICE_NOT_FOUND")
    fault = _faults.get(invoice_id, {})
    mode = fault.get("mode", "ok")
    rec = dict(_records[invoice_id])

    if mode == "down":
        raise HTTPException(503, "SERVICE_UNAVAILABLE")
    if mode == "stale":
        from datetime import datetime, timedelta, timezone
        rec["updated_at"] = (
            datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    if mode == "inflated":
        rec["amount"] = rec["amount"] * 1000
    if mode == "conflict":
        rec["status"] = "REFUNDED"
        rec["conflict_detail"] = "AUTHORITATIVE_SAYS_REFUNDED"

    return rec


@app.post("/ledger/{invoice_id}/attack")
def inject_fault(invoice_id: str, body: AttackReq):
    if invoice_id not in _records:
        raise HTTPException(404, "INVOICE_NOT_FOUND")
    _faults[invoice_id] = {"mode": body.mode}
    return {"ok": True, "invoice_id": invoice_id, "mode": body.mode}


@app.post("/ledger/reset")
def reset():
    _init_records()
    return {"ok": True, "records": len(_records)}


def run_server(host: str = "127.0.0.1", port: int = 8001):
    """Start the ledger server (blocking). Call from a thread or subprocess."""
    uvicorn.run(app, host=host, port=port, log_level="warning")
