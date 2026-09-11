"""AR Worker — owns the 50-invoice job through failure, recovery, and resume.

Lifecycle per invoice:
  PENDING → FETCH_PRIMARY → OBSERVE → (FAILURE → CLASSIFY → RECOVER →
  VERIFY → OBSERVE)* → COMPLETED | ESCALATED | FROZEN

State is persisted so killing and restarting the worker resumes from the
last checkpoint without replaying completed invoices.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ..core.authority import AuthorityScope
from ..core.envelopes import RecoveryEnvelope
from ..core.states import CapabilityStatus
from ..failures.classifier import classify
from ..failures.schemas import now_iso
from ..recovery.idempotency import IdempotencyStore
from ..sdk import Escalate, RecoveryRuntime, Retry, Substitute
from ..workflows.run import (
    ITEM_COMPLETED, ITEM_ESCALATED, ITEM_FROZEN, ITEM_PENDING,
    WorkflowRun, new_run, reconcile_all, run_envelope,
)
from ..workloads.invoices import (
    SOURCE_PRIMARY,
    TRUSTED_SOURCES,
    AlternateSource,
    AuthoritativeSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
    make_record,
)
from .store import load_invoices, save_invoice, save_job

JOB_ID = "ar_worker_50"
DEFAULT_LEDGER_URL = "http://127.0.0.1:8001"


class ARWorker:
    """Processes 50 invoices through RecoveryRuntime, collecting lifecycle traces."""

    def __init__(self, fault_overrides: dict[str, str] | None = None,
                 use_http_authoritative: bool = False,
                 authoritative_url: str | None = None):
        self.fault_overrides: dict[str, str] = fault_overrides or {}
        self.use_http_authoritative = use_http_authoritative
        self.authoritative_url = authoritative_url or DEFAULT_LEDGER_URL
        self._build_world()
        self.idem = IdempotencyStore()
        self._lock = threading.Lock()
        self._paused = False
        self._stopped = False
        self._run: WorkflowRun | None = None
        self._traces: dict[str, list[dict]] = {}
        self._status_counts: dict[str, int] = {
            "pending": 50, "processing": 0, "completed": 0,
            "recovered": 0, "escalated": 0, "frozen": 0, "failed": 0,
        }

    def _build_world(self):
        self.ledger = ledger_amounts(50)
        self.ids = invoice_ids(50)
        faults = dict(self.fault_overrides)
        self.primary = PrimaryAccounting(self.ledger, faults=faults)
        self.alternate = AlternateSource(self.ledger)
        self.authoritative = AuthoritativeSource(self.ledger)

    def _scope(self) -> set[str]:
        tools = {"fetch_primary", "fetch_alternate"}
        if self.use_http_authoritative:
            tools.add("fetch_authoritative")
        return tools

    def _adapters(self) -> dict:
        adapters: dict = {"primary": self.primary, "alternate": self.alternate}
        if self.use_http_authoritative:
            from ..external.client import AuthoritativeLedgerClient
            adapters["authoritative"] = AuthoritativeLedgerClient(
                self.authoritative_url)
        else:
            adapters["authoritative"] = self.authoritative
        return adapters

    def _make_run(self) -> WorkflowRun:
        scope = AuthorityScope.of(*self._scope())
        persisted = load_invoices(JOB_ID)
        completed = {i for i, info in persisted.items()
                     if info["status"] == "COMPLETED"}
        run = new_run(JOB_ID, "accounts-receivable-reconciliation",
                      self.ids, scope)
        for iid, info in persisted.items():
            if iid in run.items and info["status"] != ITEM_PENDING:
                run.items[iid] = info["status"]
                run.attempts[iid] = info["attempts"]
            self._traces[iid] = info["lifecycle"]
        run.transition_to("RUNNING", f"start:ar_worker")
        return run

    def _build_envelope(self, run_id: str, scope: AuthorityScope,
                        max_attempts: int = 3) -> RecoveryEnvelope:
        return run_envelope(run_id, scope, max_attempts)

    def _collect_traces(self, run: WorkflowRun) -> None:
        """Collect per-invoice lifecycle trace from run events."""
        self._traces.clear()
        for e in run.events:
            text = f"{e.get('event', '')} {e.get('detail', '')}"
            for iid in self.ids:
                if f":{iid}" in text or iid in text:
                    if iid not in self._traces:
                        self._traces[iid] = []
                    self._traces[iid].append({
                        "seq": e["seq"],
                        "state": e["state"],
                        "event": e["event"],
                        "detail": e.get("detail", ""),
                        "ts": now_iso(),
                    })

    def _update_counts(self, run: WorkflowRun) -> None:
        counts = {"pending": 0, "processing": 0, "completed": 0,
                  "recovered": 0, "escalated": 0, "frozen": 0, "failed": 0}
        for iid, status in run.items.items():
            if status == "COMPLETED":
                if run.attempts.get(iid, 0) > 0:
                    counts["recovered"] += 1
                else:
                    counts["completed"] += 1
            elif status == "ESCALATED":
                counts["escalated"] += 1
            elif status == "FROZEN":
                counts["frozen"] += 1
            elif status == "PENDING":
                counts["pending"] += 1
        self._status_counts = counts

    def _persist_state(self, run: WorkflowRun) -> None:
        save_job(JOB_ID, run.state, len(self.ids))
        for iid, status in run.items.items():
            save_invoice(JOB_ID, iid, status,
                         attempts=run.attempts.get(iid, 0),
                         recovery_mode=self._recovery_mode(iid, run),
                         lifecycle=self._traces.get(iid, []))

    def _recovery_mode(self, iid: str, run: WorkflowRun) -> str | None:
        mode: str | None = None
        for e in run.events:
            text = f"{e.get('event', '')} {e.get('detail', '')}"
            if iid in text and e["event"].startswith("policy:"):
                mode = e["event"].split(":")[1]
        return mode

    def run(self, max_invoices: int | None = None) -> WorkflowRun:
        """Synchronous sweep: process all (or max_invoices) pending invoices."""
        with self._lock:
            self._build_world()
            run = self._make_run()
            envelope = self._build_envelope(run.id, run.scope)
            ids_to_run = run.pending_items()
            if max_invoices is not None:
                ids_to_run = ids_to_run[:max_invoices]
            for iid in ids_to_run:
                if self._paused or self._stopped or run.halted:
                    break
                from ..workflows.run import _reconcile_item
                _reconcile_item(run, iid, self._adapters(), envelope, self.idem,
                                self.ledger, None, 3600.0)
                self._collect_traces(run)
                self._update_counts(run)
                self._persist_state(run)
            if not self._paused and not self._stopped:
                if run.halted:
                    run.transition_to("FROZEN", "halted")
                elif run.pending_items():
                    run.event("INCOMPLETE", f"pending={run.pending_items()}")
                else:
                    n = sum(1 for s in run.items.values() if s == "COMPLETED")
                    run.transition_to("COMPLETED", f"done:{n}")
            self._collect_traces(run)
            self._update_counts(run)
            self._persist_state(run)
            self._run = run
            return run

    def inject_fault(self, invoice_id: str, mode: str) -> None:
        """Inject a fault for a specific invoice into the primary source."""
        with self._lock:
            self.fault_overrides[invoice_id] = mode
            self._build_world()

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def stop(self):
        with self._lock:
            self._stopped = True

    def reset(self):
        with self._lock:
            self._stopped = False
            self._paused = False
            self.fault_overrides.clear()
            self._traces.clear()
            self._status_counts = {
                "pending": 50, "processing": 0, "completed": 0,
                "recovered": 0, "escalated": 0, "frozen": 0, "failed": 0,
            }
            self._run = None
            from .store import reset_job
            reset_job(JOB_ID)

    def status(self) -> dict:
        """Dashboard-ready status snapshot."""
        return {
            "job_id": JOB_ID,
            "counts": dict(self._status_counts),
            "run_state": self._run.state if self._run else None,
            "invoices": {
                iid: {
                    "status": (self._run.items.get(iid, "PENDING")
                               if self._run else "PENDING"),
                    "attempts": (self._run.attempts.get(iid, 0)
                                 if self._run else 0),
                    "recovery_mode": self._recovery_mode(iid, self._run)
                        if self._run else None,
                    "trace": self._traces.get(iid, []),
                }
                for iid in self.ids
            },
        }
