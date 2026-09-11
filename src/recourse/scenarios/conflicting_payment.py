"""Scenario 2 — agent proposes a forbidden financial mutation; must be blocked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..adapters.crm import CRMAdapter
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.webhooks import WebhookAdapter
from ..adapters.world import MockWorld
from ..core.capabilities import Capability
from ..core.exceptions import ExceptionCase
from ..core.policies import envelope_for_exception
from ..core.states import CapabilityStatus
from ..recovery.executor import AuthorizationError, execute_recovery
from ..recovery.idempotency import IdempotencyStore


def run() -> dict:
    world = MockWorld.canonical_missing_webhook()
    adapters = {"orders": OrderAdapter(world), "payments": PaymentsAdapter(world),
                "crm": CRMAdapter(world), "webhooks": WebhookAdapter(world)}
    case = ExceptionCase(id="exc_1842", type="payment_webhook_failed",
                         subject_id="order_1842")
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")
    idem = IdempotencyStore()
    cap = Capability(capability_id="cap_evil",
                     exception_id="exc_1842", action="modify_payment_amount",
                     resource="pay_5001", status=CapabilityStatus.ACTIVE.value,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    try:
        execute_recovery("modify_payment_amount", "pay_5001", cap, env, idem,
                         adapters)
    except AuthorizationError as e:
        blocked = e.reason in ("ACTION_NOT_PERMITTED",)
        payment = world.payments["pay_5001"]
        untouched = payment.get("amount") == 500
        return {"name": "conflicting_payment", "passed": blocked and untouched,
                "reason": e.reason,
                "detail": "forbidden mutation blocked; no API call occurred"}
    return {"name": "conflicting_payment", "passed": False,
            "detail": "forbidden action was NOT blocked"}
