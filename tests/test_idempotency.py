"""Durable idempotency: a recorded mutation cannot execute twice, even
across process restarts. Answers: 'could recovery charge twice?'"""
from datetime import datetime, timedelta, timezone

import pytest

from recourse.core.capabilities import Capability
from recourse.core.envelopes import RecoveryEnvelope
from recourse.core.states import CapabilityStatus
from recourse.recovery.executor import AuthorizationError, execute_recovery
from recourse.recovery.idempotency import (
    DurableIdempotencyStore,
    IdempotencyStore,
    idempotency_key,
)
from recourse.workloads.invoices import PrimaryAccounting, ledger_amounts


def _env():
    return RecoveryEnvelope(
        id="env_d", exception_id="exc_d", allowed_actions=["replay_webhook"],
        forbidden_actions=[],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))


def _cap(n="a"):
    return Capability(capability_id=f"c_{n}", exception_id="exc_d",
                      action="replay_webhook", resource="wh_1",
                      status=CapabilityStatus.ACTIVE.value,
                      expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))


class _Wh:
    """Minimal webhook-mutation adapter pair (no payment suite needed)."""

    def __init__(self):
        self.replays = 0

    def replay_webhook(self, wid):
        self.replays += 1
        return {"ok": True, "duplicate": self.replays > 1}


def test_memory_store_still_blocks_replay():
    idem = IdempotencyStore()
    key = idempotency_key("e", "a", "r")
    assert not idem.already_executed(key)
    idem.mark_executed(key)
    assert idem.already_executed(key)


def test_restart_cannot_remutate(tmp_path):
    """Simulated process death between two executions of the same mutation."""
    db = str(tmp_path / "idem.db")
    adapters = {"payments": _Wh()}
    execute_recovery("replay_webhook", "wh_1", _cap("1"), _env(),
                     DurableIdempotencyStore(db), adapters)
    assert adapters["payments"].replays == 1
    # --- process restarts: fresh memory, same database, fresh capability ---
    with pytest.raises(AuthorizationError) as e:
        execute_recovery("replay_webhook", "wh_1", _cap("2"), _env(),
                         DurableIdempotencyStore(db), adapters)
    assert e.value.reason == "DUPLICATE_ACTION"
    assert adapters["payments"].replays == 1  # adapter never touched again


def test_same_invoice_recovered_twice_across_runs_blocked(tmp_path):
    db = str(tmp_path / "idem.db")
    adapters = {"payments": _Wh()}
    store = DurableIdempotencyStore(db)
    execute_recovery("replay_webhook", "wh_1", _cap("1"), _env(), store, adapters)
    # A second run (new store object, e.g. resumed workflow) replays nothing.
    assert DurableIdempotencyStore(db).already_executed("exc_d:replay_webhook:wh_1")


def test_durable_store_degrades_to_memory_without_db(tmp_path):
    store = DurableIdempotencyStore(str(tmp_path / "nope" / "x.db"))
    store.mark_executed("k")  # makedirs handles nested path; still fine
    assert store.already_executed("k")
