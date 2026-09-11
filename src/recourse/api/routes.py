"""RECOURSE API routes — thin HTTP layer over the control plane.

All authority decisions live in core/recovery/verification; routes only
record transitions and persist the audit trail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..adapters.crm import CRMAdapter
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.webhooks import WebhookAdapter
from ..adapters.world import MockWorld
from ..agent.agent import stub_investigate
from ..core.capabilities import Capability
from ..core.exceptions import ExceptionCase
from ..core.policies import envelope_for_exception
from ..core.states import CapabilityStatus
from ..evidence.models import EvidenceLedger
from ..evidence.collector import collect_evidence
from ..recovery.executor import AuthorizationError, execute_recovery
from ..recovery.idempotency import IdempotencyStore
from ..storage.database import connect
from ..storage.models import (
    record_escalation,
    record_transition,
    record_verification,
    save_capability,
    save_envelope,
    save_exception,
)
from ..verification.verifier import verify_resolution

router = APIRouter()

# Process-local registries (SQLite persists the audit trail).
WORLD = MockWorld.canonical_missing_webhook()
CASES: dict[str, ExceptionCase] = {}
ENVELOPES: dict[str, object] = {}
CAPS: dict[str, Capability] = {}
IDEM = IdempotencyStore()
LEDGER = EvidenceLedger()


class CreateException(BaseModel):
    type: str = Field(default="payment_webhook_failed")
    subject_id: str = Field(default="order_1842")
    severity: str = Field(default="high")


class Transition(BaseModel):
    to: str
    reason: str = ""


class ExecuteRequest(BaseModel):
    action: str
    resource: str


def _adapters() -> dict:
    return {
        "orders": OrderAdapter(WORLD),
        "payments": PaymentsAdapter(WORLD),
        "crm": CRMAdapter(WORLD),
        "webhooks": WebhookAdapter(WORLD),
    }


def _persist_case(case: ExceptionCase, env=None) -> None:
    try:
        conn = connect()
        save_exception(conn, case)
        if env is not None:
            save_envelope(conn, env)
        conn.close()
    except Exception:
        pass  # API must work even if disk persistence is unavailable


@router.get("/health")
def health() -> dict:
    return {"ok": True, "service": "recourse"}


@router.post("/exceptions")
def create_exception(body: CreateException) -> dict:
    exc_id = f"exc_{uuid.uuid4().hex[:8]}"
    case = ExceptionCase(id=exc_id, type=body.type,
                         subject_id=body.subject_id, severity=body.severity)
    env = envelope_for_exception(exc_id, body.type)
    case.envelope_id = env.id
    CASES[exc_id] = case
    ENVELOPES[exc_id] = env
    _persist_case(case, env)
    return {"exception": case.__dict__, "envelope_id": env.id,
            "allowed": env.allowed_actions, "forbidden": env.forbidden_actions}


@router.get("/exceptions/{exc_id}")
def get_exception(exc_id: str) -> dict:
    case = CASES.get(exc_id)
    if not case:
        raise HTTPException(404, "EXCEPTION_NOT_FOUND")
    env = ENVELOPES.get(exc_id)
    return {"exception": {**case.__dict__, "created_at": str(case.created_at)},
            "envelope": getattr(env, "__dict__", None)}


@router.post("/exceptions/{exc_id}/investigate")
def investigate(exc_id: str) -> dict:
    case = CASES.get(exc_id)
    if not case:
        raise HTTPException(404, "EXCEPTION_NOT_FOUND")
    frm = case.state
    case.transition_to("INVESTIGATING", reason="agent investigation started")
    a = _adapters()
    evs = collect_evidence(exc_id, "order_1842", "pay_5001", "customer_91",
                           "wh_9231", a["orders"], a["payments"], a["crm"],
                           a["webhooks"], LEDGER)
    inv = stub_investigate("order_1842", "pay_5001", "customer_91", "wh_9231",
                           exc_id, a["orders"], a["payments"], a["crm"],
                           a["webhooks"])
    try:
        conn = connect()
        save_exception(conn, case)
        record_transition(conn, exc_id, frm, case.state, "investigate")
        conn.close()
    except Exception:
        pass
    return {"state": case.state, "diagnosis": inv.diagnosis,
            "evidence": [e.__dict__ for e in evs],
            "proposal": {**inv.proposal.__dict__}}


@router.post("/exceptions/{exc_id}/execute")
def execute(exc_id: str, body: ExecuteRequest) -> dict:
    case = CASES.get(exc_id)
    env = ENVELOPES.get(exc_id)
    if not case or env is None:
        raise HTTPException(404, "EXCEPTION_NOT_FOUND")
    # Move through proposal/authorization states deterministically.
    if case.state == "INVESTIGATING":
        frm = case.state
        case.transition_to("RECOVERY_PROPOSED", reason=f"proposed {body.action}")
        _persist_case(case)
    if case.state == "RECOVERY_PROPOSED":
        frm = case.state
        case.transition_to("AUTHORIZED", reason="capability issued")
    cap = Capability(
        capability_id=f"cap_{uuid.uuid4().hex[:8]}",
        exception_id=exc_id, action=body.action, resource=body.resource,
        status=CapabilityStatus.ACTIVE.value,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    CAPS[cap.capability_id] = cap
    try:
        result = execute_recovery(body.action, body.resource, cap, env, IDEM,
                                  _adapters())
    except AuthorizationError as e:
        frm = case.state
        if case.state == "AUTHORIZED":
            case.transition_to("BLOCKED", reason=e.reason)
        _persist_case(case)
        try:
            conn = connect()
            save_capability(conn, cap)
            record_transition(conn, exc_id, frm, case.state, e.reason)
            conn.close()
        except Exception:
            pass
        raise HTTPException(403, e.reason)
    frm = case.state
    case.attempt_count += 1
    case.transition_to("EXECUTED", reason=f"executed {body.action}")
    case.transition_to("VERIFYING", reason="independent verification")
    env_obj = env
    vr = verify_resolution(getattr(env_obj, "required_postconditions", []),
                           "order_1842", "pay_5001", "customer_91",
                           _adapters()["orders"], _adapters()["payments"],
                           _adapters()["crm"])
    if vr.passed:
        case.transition_to("RESOLVED", reason="postconditions proved")
    elif case.attempt_count >= getattr(env_obj, "max_attempts", 3):
        case.transition_to("ESCALATED", reason="attempts exhausted")
    else:
        case.transition_to("RECOVERY_PROPOSED", reason="verification failed; retry")
    _persist_case(case)
    try:
        conn = connect()
        save_capability(conn, cap)
        record_transition(conn, exc_id, frm, "VERIFYING", "executed")
        record_transition(conn, exc_id, "VERIFYING", case.state,
                          "verified" if vr.passed else "verification failed")
        record_verification(conn, f"vr_{uuid.uuid4().hex[:8]}", exc_id,
                            body.action, vr.expected, vr.observed,
                            "PASS" if vr.passed else "FAIL")
        if case.state == "ESCALATED":
            record_escalation(conn, f"esc_{uuid.uuid4().hex[:8]}",
                              exc_id, "verification failed; attempts exhausted")
        conn.close()
    except Exception:
        pass
    return {"state": case.state, "execution": result,
            "verification": {"passed": vr.passed, "observed": vr.observed,
                             "per_predicate": vr.per_predicate,
                             "problems": vr.problems}}


@router.post("/exceptions/{exc_id}/transition")
def transition(exc_id: str, body: Transition) -> dict:
    case = CASES.get(exc_id)
    if not case:
        raise HTTPException(404, "EXCEPTION_NOT_FOUND")
    try:
        frm = case.state
        case.transition_to(body.to, reason=body.reason)
    except Exception as e:
        raise HTTPException(400, str(e))
    _persist_case(case)
    return {"state": case.state, "from": frm}
