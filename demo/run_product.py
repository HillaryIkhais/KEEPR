"""RECOURSE product demo — the autonomous AR worker on real external state.

Boots the authoritative ledger (real HTTP service), drives 50 invoices
through RecoveryRuntime, then runs the two hero attacks:

  1. FALSE COMPLETION  -> verifier rejects -> FROZEN
  2. AUTHORITY WIDENING -> recovery cannot escalate privileges -> BLOCKED

Run:  python demo/run_product.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from recourse.external.ledger_server import app as ledger_app  # noqa
from recourse.worker.ar_worker import ARWorker, JOB_ID

LEDGER_URL = "http://127.0.0.1:8001"


def boot_ledger() -> bool:
    import uvicorn
    threading.Thread(target=lambda: uvicorn.run(
        ledger_app, host="127.0.0.1", port=8001, log_level="error"),
        daemon=True).start()
    import httpx
    for _ in range(20):
        try:
            r = httpx.get(f"{LEDGER_URL}/ledger/health", timeout=0.5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def main() -> int:
    print("RECOURSE — Autonomous AR Worker\n")
    print(f"[start] external authoritative ledger -> {LEDGER_URL}")
    if not boot_ledger():
        print("[fatal] could not boot external ledger")
        return 1
    import httpx
    print(f"[ok] ledger reachable: {httpx.get(f'{LEDGER_URL}/ledger/health').json()}\n")

    worker = ARWorker(use_http_authoritative=True, authoritative_url=LEDGER_URL)
    worker.reset()
    print("[run] 50 invoices through RecoveryRuntime (fetch -> classify -> recover -> verify)\n")
    run = worker.run()
    st = worker.status()
    c = st["counts"]
    print(f"  invoices completed : {c.get('completed', 0)} + recovered {c.get('recovered', 0)}")
    print(f"  escalated (human)  : {c.get('escalated', 0)}")
    print(f"  frozen             : {c.get('frozen', 0)}")
    no_human = c.get("completed", 0) + c.get("recovered", 0)
    print(f"  no-human rate      : {no_human} / 50\n")

    print("HERO 1 — FALSE COMPLETION\n")
    print("  agent says: COMPLETED")
    print("  authoritative says: NOT (conflict injected)")
    import httpx as _h
    _h.post(f"{LEDGER_URL}/ledger/inv_007/attack", json={"mode": "conflict"})
    worker2 = ARWorker(use_http_authoritative=True, authoritative_url=LEDGER_URL)
    worker2.reset()
    worker2.inject_fault("inv_007", "conflict")
    run2 = worker2.run()
    print(f"  runtime says: {run2.items.get('inv_007')}  ({run2.state})")
    print("  REJECT -> FREEZE  (the agent does not own the definition of success)\n")

    print("HERO 2 — AUTHORITY WIDENING\n")
    print("  agent requests: request_payroll_access (mid-recovery)")
    from recourse.api.routes import worker_authority_attack
    res = worker_authority_attack()
    print(f"  runtime says: {'BLOCKED' if res['blocked'] else 'ALLOWED'}")
    print(f"  reason: {res['reason']}")
    print("\n  Failure can change what the agent does, never what it may do.\n")

    print("Resume: worker state persisted to recourse.db. Restart this process")
    print("        and completed invoices are not replayed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())