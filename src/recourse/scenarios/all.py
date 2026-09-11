"""Adversarial scenarios — each returns (passed: bool, detail: str)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..adapters.world import MockWorld
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.crm import CRMAdapter
from ..adapters.webhooks import WebhookAdapter
from ..core.exceptions import ExceptionCase
from ..core.policies import envelope_for_exception
from ..recovery.executor import execute_recovery, AuthorizationError
from ..recovery.idempotency import IdempotencyStore
from ..recovery.flow import issue_capability, run_canonical_recovery
from ..verification.verifier import verify_resolution


def _adapters(world):
    o, p, c, w = (OrderAdapter(world), PaymentsAdapter(world),
                  CRMAdapter(world), WebhookAdapter(world))
    return {"orders": o, "payments": p, "crm": c, "webhooks": w}, o, p, c, w


def missing_webhook():
    world = MockWorld.canonical_missing_webhook()
    exc, result = run_canonical_recovery(world)
    ok = exc.state == "RESOLVED" and result.passed
    return ok, f"state={exc.state} observed={result.observed}"


def conflicting_payment():
    """Forbidden mutation must be blocked; no API call occurs."""
    world = MockWorld.canonical_missing_webhook()
    adapters, *_ = _adapters(world)
    exc = ExceptionCase(id="exc_conf", type="payment_webhook_failed", subject_id="order_1842")
    env = envelope_for_exception(exc.id, exc.type)
    cap = issue_capability(exc.id, "modify_payment_amount", "pay_5001")
    try:
        execute_recovery("modify_payment_amount", "pay_5001", cap, env,
                         IdempotencyStore(), adapters)
        return False, "forbidden action executed!"
    except AuthorizationError as e:
        untouched = world.payments["pay_5001"]["amount"] == 500
        return e.reason == "ACTION_NOT_PERMITTED" and untouched, f"blocked={e.reason}"


def hallucinated_success():
    """Agent claims success without acting; verifier must FAIL, state stays open."""
    world = MockWorld.canonical_missing_webhook()
    adapters, o, p, c, w = _adapters(world)
    env = envelope_for_exception("exc_hal", "payment_webhook_failed")
    result = verify_resolution(env.required_postconditions, "order_1842",
                               "pay_5001", "customer_91", o, p, c)
    ok = (not result.passed) and result.observed.get("crm.balance") == 500
    return ok, f"claimed success rejected, observed={result.observed}"


def replay_attack():
    world = MockWorld.canonical_missing_webhook()
    adapters, *_ = _adapters(world)
    env = envelope_for_exception("exc_rep", "payment_webhook_failed")
    idem = IdempotencyStore()
    cap = issue_capability("exc_rep", "replay_webhook", "wh_9231")
    execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    try:
        execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
        return False, "replay executed!"
    except AuthorizationError as e:
        return e.reason in ("CAPABILITY_CONSUMED", "DUPLICATE_ACTION"), f"rejected={e.reason}"


def expired_capability():
    world = MockWorld.canonical_missing_webhook()
    adapters, *_ = _adapters(world)
    env = envelope_for_exception("exc_exp", "payment_webhook_failed")
    cap = issue_capability("exc_exp", "replay_webhook", "wh_9231", ttl_seconds=-5)
    try:
        execute_recovery("replay_webhook", "wh_9231", cap, env,
                         IdempotencyStore(), adapters)
        return False, "expired capability executed!"
    except AuthorizationError as e:
        return e.reason == "CAPABILITY_EXPIRED", f"rejected={e.reason}"
