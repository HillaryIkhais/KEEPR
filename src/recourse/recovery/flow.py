"""Orchestrated recovery flow used by scenarios, gauntlet, and API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.exceptions import ExceptionCase
from ..core.capabilities import Capability
from ..core.policies import envelope_for_exception
from ..recovery.executor import execute_recovery, AuthorizationError
from ..recovery.idempotency import IdempotencyStore
from ..verification.verifier import verify_resolution


def issue_capability(exception_id: str, action: str, resource: str,
                     ttl_seconds: int = 1800) -> Capability:
    return Capability(
        capability_id=f"cap_{exception_id}_{action}",
        exception_id=exception_id, action=action, resource=resource,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )


def run_canonical_recovery(world, exception_id="exc_1842", order_id="order_1842",
                           payment_id="pay_5001", customer_id="customer_91",
                           webhook_id="wh_9231"):
    """Full happy path: DETECTED -> ... -> RESOLVED. Returns (exc, verification)."""
    from ..adapters.orders import OrderAdapter
    from ..adapters.payments import PaymentsAdapter
    from ..adapters.crm import CRMAdapter
    from ..adapters.webhooks import WebhookAdapter

    orders, payments, crm, webhooks = (
        OrderAdapter(world), PaymentsAdapter(world),
        CRMAdapter(world), WebhookAdapter(world))
    adapters = {"orders": orders, "payments": payments, "crm": crm, "webhooks": webhooks}

    exc = ExceptionCase(id=exception_id, type="payment_webhook_failed",
                        subject_id=order_id)
    envelope = envelope_for_exception(exception_id, exc.type)
    exc.envelope_id = envelope.id
    idem = IdempotencyStore()

    exc.transition_to("INVESTIGATING")
    exc.transition_to("RECOVERY_PROPOSED")
    exc.transition_to("AUTHORIZED")
    cap = issue_capability(exception_id, "replay_webhook", webhook_id)
    execute_recovery("replay_webhook", webhook_id, cap, envelope, idem, adapters)
    exc.attempt_count += 1
    exc.transition_to("EXECUTED")
    exc.transition_to("VERIFYING")
    result = verify_resolution(envelope.required_postconditions, order_id,
                               payment_id, customer_id, orders, payments, crm)
    if result.passed:
        exc.transition_to("RESOLVED")
    elif exc.attempt_count >= envelope.max_attempts:
        exc.transition_to("ESCALATED")
    else:
        exc.transition_to("RECOVERY_PROPOSED")
    return exc, result
