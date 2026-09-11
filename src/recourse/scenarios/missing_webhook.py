"""Scenario 1 — canonical missing-webhook recovery (happy path)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from ..evidence.collector import collect_evidence
from ..evidence.models import EvidenceLedger
from ..recovery.executor import execute_recovery
from ..recovery.idempotency import IdempotencyStore
from ..verification.verifier import verify_resolution


def run() -> dict:
    world = MockWorld.canonical_missing_webhook()
    orders, payments = OrderAdapter(world), PaymentsAdapter(world)
    crm, webhooks = CRMAdapter(world), WebhookAdapter(world)
    ledger, idem = EvidenceLedger(), IdempotencyStore()

    case = ExceptionCase(id="exc_1842", type="payment_webhook_failed",
                         subject_id="order_1842")
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")

    case.transition_to("INVESTIGATING")
    collect_evidence("exc_1842", "order_1842", "pay_5001", "customer_91",
                     "wh_9231", orders, payments, crm, webhooks, ledger)
    inv = stub_investigate("order_1842", "pay_5001", "customer_91", "wh_9231",
                           "exc_1842", orders, payments, crm, webhooks)
    case.transition_to("RECOVERY_PROPOSED")
    case.transition_to("AUTHORIZED")
    cap = Capability(capability_id="cap_8f31", exception_id="exc_1842",
                     action="replay_webhook", resource="wh_9231",
                     status=CapabilityStatus.ACTIVE.value,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    adapters = {"orders": orders, "payments": payments, "crm": crm,
                "webhooks": webhooks}
    execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    case.transition_to("EXECUTED")
    case.transition_to("VERIFYING")
    vr = verify_resolution(env.required_postconditions, "order_1842", "pay_5001",
                           "customer_91", orders, payments, crm)
    if vr.passed:
        case.transition_to("RESOLVED")
    passed = vr.passed and case.state == "RESOLVED"
    return {"name": "missing_webhook", "passed": passed,
            "state": case.state, "diagnosis": inv.diagnosis,
            "observed": vr.observed, "detail": "webhook replayed; verifier proved postconditions"}
