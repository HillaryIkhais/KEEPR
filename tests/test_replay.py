"""Replay + idempotency: duplicate execution impossible."""
from datetime import datetime, timedelta, timezone

import pytest

from recourse.adapters.crm import CRMAdapter
from recourse.adapters.orders import OrderAdapter
from recourse.adapters.payments import PaymentsAdapter
from recourse.adapters.webhooks import WebhookAdapter
from recourse.adapters.world import MockWorld
from recourse.core.capabilities import Capability
from recourse.core.policies import envelope_for_exception
from recourse.core.states import CapabilityStatus
from recourse.recovery.executor import AuthorizationError, execute_recovery
from recourse.recovery.idempotency import IdempotencyStore, idempotency_key


def _setup():
    world = MockWorld.canonical_missing_webhook()
    adapters = {"orders": OrderAdapter(world), "payments": PaymentsAdapter(world),
                "crm": CRMAdapter(world), "webhooks": WebhookAdapter(world)}
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")
    return world, adapters, env


def _cap(cid="cap_1"):
    return Capability(capability_id=cid, exception_id="exc_1842",
                      action="replay_webhook", resource="wh_9231",
                      status=CapabilityStatus.ACTIVE.value,
                      expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))


def test_first_execution_succeeds():
    _, adapters, env = _setup()
    out = execute_recovery("replay_webhook", "wh_9231", _cap(), env,
                           IdempotencyStore(), adapters)
    assert out["ok"]
    assert out["idempotency_key"] == idempotency_key("exc_1842", "replay_webhook",
                                                     "wh_9231")


def test_replay_consumed_capability_rejected():
    _, adapters, env = _setup()
    idem = IdempotencyStore()
    cap = _cap()
    execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    with pytest.raises(AuthorizationError) as e:
        execute_recovery("replay_webhook", "wh_9231", cap, env, idem, adapters)
    assert e.value.reason in ("CAPABILITY_CONSUMED", "DUPLICATE_ACTION")


def test_replay_fresh_capability_still_blocked_by_idempotency():
    _, adapters, env = _setup()
    idem = IdempotencyStore()
    execute_recovery("replay_webhook", "wh_9231", _cap("a"), env, idem, adapters)
    with pytest.raises(AuthorizationError) as e:
        execute_recovery("replay_webhook", "wh_9231", _cap("b"), env, idem,
                         adapters)
    assert e.value.reason == "DUPLICATE_ACTION"


def test_forbidden_action_never_reaches_adapter():
    world, adapters, env = _setup()
    cap = Capability(capability_id="x", exception_id="exc_1842",
                     action="refund_payment", resource="pay_5001",
                     status=CapabilityStatus.ACTIVE.value,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    with pytest.raises(AuthorizationError) as e:
        execute_recovery("refund_payment", "pay_5001", cap, env,
                         IdempotencyStore(), adapters)
    assert e.value.reason == "ACTION_NOT_PERMITTED"
    assert world.payments["pay_5001"]["amount"] == 500
