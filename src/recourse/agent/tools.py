"""Real Strands tools — the agent's only hands.

Tools are read-only inspects plus propose/execute. Mutation exists ONLY
inside execute_authorized_recovery, which delegates to the coordinator
(capability + scope + idempotency enforced there AND by the hook).
Tools are bound to one coordinator at a time via bind_coordinator().
"""
from __future__ import annotations

from .coordinator import AgentCoordinator

_CTX: AgentCoordinator | None = None


def bind_coordinator(coordinator: AgentCoordinator) -> None:
    global _CTX
    _CTX = coordinator


def unbind_coordinator() -> None:
    global _CTX
    _CTX = None


def current() -> AgentCoordinator:
    if _CTX is None:
        raise RuntimeError("NO_COORDINATOR: bind_coordinator() first")
    return _CTX


def _require_source(outcome: dict) -> dict:
    if not isinstance(outcome, dict) or outcome.get("ok") is not True:
        return {"ok": False, "error": outcome.get("error", "SOURCE_ERROR") if isinstance(outcome, dict) else "SOURCE_ERROR"}
    return {"ok": True, "record": outcome.get("data"),
            "source": (outcome.get("meta") or {}).get("source")}


try:
    from strands import tool as _strands_tool
except Exception:  # strands not installed: tools still importable/testable
    def _strands_tool(fn=None, **kwargs):
        if fn is None:
            return lambda f: f
        return fn
else:
    pass


@_strands_tool
def inspect_invoice(invoice_id: str) -> dict:
    """Read the primary accounting record for an invoice (read-only)."""
    ctx = current()
    return _require_source(ctx.adapters["primary"].fetch(invoice_id))


@_strands_tool
def fetch_backup_record(invoice_id: str) -> dict:
    """Read the backup records source for an invoice (read-only)."""
    ctx = current()
    if "alternate" not in ctx.adapters:
        return {"ok": False, "error": "NO_BACKUP_SOURCE"}
    return _require_source(ctx.adapters["alternate"].fetch(invoice_id))


@_strands_tool
def fetch_authoritative_record(invoice_id: str) -> dict:
    """Read the authoritative ledger for an invoice (read-only)."""
    ctx = current()
    if "authoritative" not in ctx.adapters:
        return {"ok": False, "error": "NO_AUTHORITATIVE_SOURCE"}
    return _require_source(ctx.adapters["authoritative"].fetch(invoice_id))


@_strands_tool
def propose_recovery(item_id: str, action: str, rationale: str) -> dict:
    """Propose a recovery action. Accepted proposals still need
    execute_authorized_recovery; out-of-scope actions are rejected here."""
    return current().propose(item_id, action, rationale)


@_strands_tool
def execute_authorized_recovery(item_id: str, action: str) -> dict:
    """Execute a previously ACCEPTED recovery proposal through the control
    plane (scope + capability + idempotency + verification). Mutating path."""
    return current().recover(item_id, action)


@_strands_tool
def get_workflow_status() -> dict:
    """Read current workflow progress (read-only)."""
    ctx = current()
    run = ctx.run
    items = getattr(run, "items", {})
    return {"state": getattr(run, "state", "?"),
            "completed": sum(1 for s in items.values() if s == "COMPLETED"),
            "escalated": sum(1 for s in items.values() if s == "ESCALATED"),
            "frozen": sum(1 for s in items.values() if s == "FROZEN"),
            "pending": sum(1 for s in items.values() if s == "PENDING"),
            "total": len(items)}


AGENT_TOOLS = [inspect_invoice, fetch_backup_record,
               fetch_authoritative_record, propose_recovery,
               execute_authorized_recovery, get_workflow_status]
