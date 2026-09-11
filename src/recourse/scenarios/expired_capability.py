"""Scenario 5 — expired capability; action must be rejected."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..adapters.crm import CRMAdapter
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.webhooks import WebhookAdapter
from ..adapters.world import MockWorld
from ..core.capabilities import Capability
from ..core.policies import envelope_for_exception
from ..core.states import CapabilityStatus
from ..recovery.executor import AuthorizationError, execute_recovery
from ..recovery.idempotency import IdempotencyStore


def run() -> dict:
    world = MockWorld.canonical_missing_webhook()
    adapters = {"orders": OrderAdapter(world), "payments": PaymentsAdapter(world),
                "crm": CRMAdapter(world), "webhooks": WebhookAdapter(world)}
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")
    idem = IdempotencyStore()
    cap = Capability(
        capability_id="cap_exp", exception_id="exc_1842",
        action="replay_webhook", resource="wh_9231",
        status=CapabilityStatus.ACTIVE.value,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    # Simulate time passing: validate 60s in the future.
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    try:
        execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters,
                         now=future)
    except AuthorizationError as e:
        crm_balance = world.customers["customer_91"]["balance"]
        return {"name": "expired_capability",
                "passed": e.reason == "CAPABILITY_EXPIRED" and crm_balance == 500,
                "reason": e.reason,
                "detail": "temporal authority enforced; no side effect"}
    return {"name": "expired_capability", "passed": False,
            "detail": "expired capability was NOT rejected"}
