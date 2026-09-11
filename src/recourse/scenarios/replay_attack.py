"""Scenario 4 — capability replay; second use must be rejected."""
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
    cap = Capability(capability_id="cap_8f31", exception_id="exc_1842",
                     action="replay_webhook", resource="wh_9231",
                     status=CapabilityStatus.ACTIVE.value,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    try:
        execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    except AuthorizationError as e:
        ok = e.reason in ("CAPABILITY_CONSUMED", "DUPLICATE_ACTION")
        return {"name": "replay_attack", "passed": ok, "reason": e.reason,
                "detail": "consumed capability rejected on replay"}
    return {"name": "replay_attack", "passed": False,
            "detail": "replay was NOT rejected"}
