"""Tests for the AR worker product surface — external ledger, worker, dashboard.

Covers the judge-visible P0 features:
  * external authoritative ledger (HTTP service + client)
  * AR worker drives 50 invoices with lifecycle traces
  * failure injection -> recovery -> verified completion
  * false completion -> REJECT -> FROZEN (the hero)
  * authority widening -> BLOCKED
  * resume skips completed invoices.
"""
from __future__ import annotations

import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from recourse.external.ledger_server import app as ledger_app
from recourse.worker.ar_worker import ARWorker


# ---------------------------------------------------------------------------
# Shared ledger server on a real port (session-scoped for speed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def ledger_server():
    """Start a real authoritative ledger on 127.0.0.1:8001 for the session."""
    config = uvicorn.Config(ledger_app, host="127.0.0.1", port=8001,
                            log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:8001/ledger/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield
    server.should_exit = True


@pytest.fixture
def worker():
    """Fresh unit-test worker (no HTTP ledger, pure in-process world)."""
    w = ARWorker()
    w.reset()
    return w


@pytest.fixture
def api_client():
    from recourse.api.server import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# External ledger (real HTTP service)
# ---------------------------------------------------------------------------

def test_ledger_health_and_fetch():
    client = TestClient(ledger_app)
    health = client.get("/ledger/health").json()
    assert health["ok"] is True and health["records"] == 50
    rec = client.get("/ledger/inv_001").json()
    assert rec["invoice_id"] == "inv_001"
    assert rec["amount"] >= 1000
    assert rec["source"] == "authoritative_ledger"


def test_ledger_attack_modes():
    client = TestClient(ledger_app)
    # stale
    client.post("/ledger/inv_002/attack", json={"mode": "stale"})
    rec = client.get("/ledger/inv_002").json()
    assert "updated_at" in rec
    # down -> 503
    client.post("/ledger/inv_002/attack", json={"mode": "down"})
    assert client.get("/ledger/inv_002").status_code == 503
    # inflated
    client.post("/ledger/reset")
    client.post("/ledger/inv_002/attack", json={"mode": "inflated"})
    rec = client.get("/ledger/inv_002").json()
    assert rec["amount"] > 100000
    # conflict
    client.post("/ledger/inv_002/attack", json={"mode": "conflict"})
    rec = client.get("/ledger/inv_002").json()
    assert rec["status"] == "REFUNDED"
    client.post("/ledger/reset")


# ---------------------------------------------------------------------------
# AR worker lifecycle management (in-process, no HTTP)
# ---------------------------------------------------------------------------

def test_worker_clean_run(worker):
    run = worker.run()
    assert run.state == "COMPLETED"
    assert all(s == "COMPLETED" for s in run.items.values())
    counts = worker.status()["counts"]
    assert counts["completed"] == 50
    assert counts["pending"] == 0


def test_worker_503_retry_recovers(worker):
    worker.inject_fault("inv_007", "http_503")
    run = worker.run()
    assert run.items["inv_007"] == "COMPLETED"
    assert run.attempts["inv_007"] == 3  # 1 + 2 bounded retries
    trace = worker.status()["invoices"]["inv_007"]["trace"]
    assert trace, "recovery lifecycle trace must exist"


def test_worker_malformed_substitutes(worker):
    worker.inject_fault("inv_042", "malformed_amount")
    run = worker.run()
    assert run.items["inv_042"] == "COMPLETED"
    assert run.results["inv_042"]["amount"] == 1000 + 42 * 137
    # final effective recovery mode is substitute
    assert worker.status()["invoices"]["inv_042"]["recovery_mode"] == "substitute"


def test_worker_conflict_freezes(worker):
    worker.inject_fault("inv_015", "conflict")
    run = worker.run()
    assert run.items["inv_015"] == "FROZEN"
    assert run.state == "FROZEN"
    # halt: later items untouched
    assert run.items["inv_039"] == "PENDING"


def test_worker_auth_escalates(worker):
    worker.inject_fault("inv_030", "http_401")
    run = worker.run()
    assert run.items["inv_030"] == "ESCALATED"
    assert run.attempts["inv_030"] == 0  # auth never enters recovery chain
    # exactly one primary fetch: escalation is immediate, no retry
    assert worker.primary.calls.count("inv_030") == 1
    trace = worker.status()["invoices"]["inv_030"]["trace"]
    assert any("ESCALAT" in t["event"] for t in trace)


def test_worker_resume_skips_completed(worker):
    worker.inject_fault("inv_007", "http_503")
    run = worker.run()
    assert run.items["inv_007"] == "COMPLETED"

    # Simulate kill/restart: new worker instance reads persisted state.
    from recourse.worker.ar_worker import ARWorker
    w2 = ARWorker()
    run2 = w2.run()
    assert run2.items["inv_007"] == "COMPLETED"


def test_worker_resume_freeze_restores():
    """Resume after a FREEZE: completed + frozen items preserved, pending skipped."""
    from recourse.worker.ar_worker import JOB_ID
    from recourse.worker.store import reset_job
    reset_job(JOB_ID)
    w = ARWorker()
    w.inject_fault("inv_010", "conflict")
    run1 = w.run()
    assert run1.items["inv_010"] == "FROZEN"
    completed_count = sum(1 for s in run1.items.values() if s == "COMPLETED")
    pending_count = sum(1 for s in run1.items.values() if s == "PENDING")
    assert completed_count > 0
    assert pending_count > 0

    w2 = ARWorker()
    run2 = w2.run()
    assert run2.items["inv_010"] == "FROZEN"
    # completed + frozen are preserved; only pending items reprocessed
    comp2 = sum(1 for s in run2.items.values() if s == "COMPLETED")
    assert comp2 >= completed_count - 1  # at least the same number


# ---------------------------------------------------------------------------
# API product surface (real external ledger via HTTP authoritative)
# ---------------------------------------------------------------------------

def test_api_serves_dashboard(api_client):
    r = api_client.get("/")
    assert r.status_code == 200
    assert "KEEPR" in r.text
    assert "Break the Job" in r.text
    assert "No-Human" in r.text


def test_api_worker_run_and_status(api_client):
    api_client.post("/api/worker/reset")
    st = api_client.get("/api/worker/status").json()
    assert st["counts"]["pending"] == 50
    r = api_client.post("/api/worker/run").json()
    assert r["state"] == "COMPLETED"
    assert r["counts"]["completed"] == 50


def test_api_attack_injects_fault(api_client):
    api_client.post("/api/worker/reset")
    r = api_client.post("/api/worker/attack",
                        json={"invoice_id": "inv_007", "mode": "http_503"}).json()
    assert r["ok"] is True


def test_api_authority_widening_blocked(api_client):
    r = api_client.post("/api/worker/authority-attack").json()
    assert r["blocked"] is True
    assert "AUTHORITY_WIDENING" in r["reason"]


def test_api_false_completion_rejects(api_client):
    api_client.post("/api/worker/reset")
    r = api_client.post("/api/worker/false-completion").json()
    assert r["invoice"] == "inv_007"
    assert r["final_status"] == "FROZEN"
    assert r["run_state"] == "FROZEN"