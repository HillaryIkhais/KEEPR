"""Invoice reconciliation workload — the real agent task.

50 invoices reconciled against accounting records. Sources are injectable:
primary can 503/401/go malformed/stale/partial; the alternate can be
poisoned; the authoritative ledger is fresh ground truth. All fault
injection is deterministic so the attack lab is reproducible.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..failures.schemas import now_iso
from ..recovery.tools import register_tool

SOURCE_PRIMARY = "accounting_primary"
SOURCE_ALTERNATE = "accounting_alternate"
SOURCE_AUTHORITATIVE = "authoritative_ledger"
TRUSTED_SOURCES = (SOURCE_PRIMARY, SOURCE_ALTERNATE, SOURCE_AUTHORITATIVE)


def ledger_amounts(n: int = 50) -> dict[str, int]:
    return {f"inv_{i:03d}": 1000 + i * 137 for i in range(1, n + 1)}


def invoice_ids(n: int = 50) -> list[str]:
    return [f"inv_{i:03d}" for i in range(1, n + 1)]


def make_record(invoice_id: str, amount, status: str,
                updated_at: str | None = None) -> dict:
    return {"invoice_id": invoice_id, "amount": amount, "currency": "USD",
            "status": status, "updated_at": updated_at or now_iso()}


def _meta(source: str, **extra) -> dict:
    return {"source": source, "observed_at": now_iso(), **extra}


class PrimaryAccounting:
    """The main accounting API. Faults: invoice_id -> mode."""

    MODES = ("ok", "http_503", "http_401", "malformed_amount", "stale",
             "conflict")

    def __init__(self, ledger: dict[str, int], faults: dict[str, str] | None = None,
                 fail_from: str | None = None, truth: dict[str, str] | None = None):
        self.ledger = ledger
        self.faults = faults or {}
        self.fail_from = fail_from  # e.g. "inv_038": 503 from here on
        self.truth = truth or {}
        self.calls: list[str] = []

    def _mode(self, invoice_id: str) -> str:
        if invoice_id in self.faults:
            return self.faults[invoice_id]
        if self.fail_from is not None and invoice_id >= self.fail_from:
            return "http_503"
        return "ok"

    def fetch(self, invoice_id: str) -> dict:
        self.calls.append(invoice_id)
        mode = self._mode(invoice_id)
        status = self.truth.get(invoice_id, "PAID")
        if mode == "ok":
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id], status),
                    "meta": _meta(SOURCE_PRIMARY)}
        if mode == "http_503":
            return {"ok": False, "error": "HTTP_503 SERVICE_UNAVAILABLE",
                    "tool": SOURCE_PRIMARY, "meta": _meta(SOURCE_PRIMARY)}
        if mode == "http_401":
            return {"ok": False, "error": "HTTP_401 EXPIRED_CREDENTIALS",
                    "tool": SOURCE_PRIMARY, "meta": _meta(SOURCE_PRIMARY)}
        if mode == "malformed_amount":
            return {"ok": True, "data": make_record(invoice_id, "$4,500", status),
                    "meta": _meta(SOURCE_PRIMARY)}
        if mode == "stale":
            old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id], "PAID", old),
                    "meta": _meta(SOURCE_PRIMARY)}
        if mode == "conflict":
            # Source reports its own disagreement (e.g. version mismatch
            # against the ledger): schema-valid but unresolvable locally.
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id], "PAID"),
                    "meta": _meta(SOURCE_PRIMARY, conflict=True,
                                  conflict_detail="AUTHORITATIVE_SAYS_REFUNDED")}
        raise ValueError(f"unknown primary mode: {mode}")

    def fetch_batch(self, ids: list[str],
                    partial_after: int | None = None) -> dict:
        """Batch fetch; partial_after=N returns first N + partial marker."""
        self.calls.extend(ids)
        records = [make_record(i, self.ledger[i], self.truth.get(i, "PAID")) for i in ids]
        if partial_after is not None and partial_after < len(records):
            return {"ok": True, "data": records[:partial_after],
                    "meta": _meta(SOURCE_PRIMARY, partial=True,
                                  missing=ids[partial_after:])}
        return {"ok": True, "data": records, "meta": _meta(SOURCE_PRIMARY)}


class AlternateSource:
    """Backup records API. Poisonable for the attack lab."""

    MODES = ("ok", "malformed", "inflated", "stale", "down")

    def __init__(self, ledger: dict[str, int], faults: dict[str, str] | None = None):
        self.ledger = ledger
        self.faults = faults or {}
        self.calls: list[str] = []

    def fetch(self, invoice_id: str) -> dict:
        self.calls.append(invoice_id)
        mode = self.faults.get(invoice_id, "ok")
        if mode == "ok":
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id], "PAID"),
                    "meta": _meta(SOURCE_ALTERNATE)}
        if mode == "malformed":
            return {"ok": True, "data": make_record(invoice_id, "$4,500", "PAID"),
                    "meta": _meta(SOURCE_ALTERNATE)}
        if mode == "inflated":
            # Schema-valid but wrong: caught by expected-amount verification.
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id] * 1000, "PAID"),
                    "meta": _meta(SOURCE_ALTERNATE)}
        if mode == "stale":
            old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            return {"ok": True, "data": make_record(invoice_id, self.ledger[invoice_id], "PAID", old),
                    "meta": _meta(SOURCE_ALTERNATE)}
        if mode == "down":
            return {"ok": False, "error": "CONNECTION_REFUSED",
                    "tool": SOURCE_ALTERNATE, "meta": _meta(SOURCE_ALTERNATE)}
        raise ValueError(f"unknown alternate mode: {mode}")


class AuthoritativeSource:
    """Fresh ground truth (e.g. bank ledger). Overrides set final status."""

    def __init__(self, ledger: dict[str, int], truth: dict[str, str] | None = None):
        self.ledger = ledger
        self.truth = truth or {}
        self.calls: list[str] = []

    def fetch(self, invoice_id: str) -> dict:
        self.calls.append(invoice_id)
        return {"ok": True,
                "data": make_record(invoice_id, self.ledger[invoice_id],
                                    self.truth.get(invoice_id, "PAID")),
                "meta": _meta(SOURCE_AUTHORITATIVE)}


def _fetch_primary(resource: str, adapters: dict) -> dict:
    return adapters["primary"].fetch(resource)


def _fetch_alternate(resource: str, adapters: dict) -> dict:
    return adapters["alternate"].fetch(resource)


def _fetch_authoritative(resource: str, adapters: dict) -> dict:
    return adapters["authoritative"].fetch(resource)


register_tool("fetch_primary", _fetch_primary, mutating=False)
register_tool("fetch_alternate", _fetch_alternate, mutating=False)
register_tool("fetch_authoritative", _fetch_authoritative, mutating=False)
