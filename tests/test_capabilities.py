"""Capabilities: bounded, expiring, single-use."""
from datetime import datetime, timedelta, timezone

from recourse.core.capabilities import Capability
from recourse.core.states import CapabilityStatus


def _cap(**kw):
    base = dict(capability_id="c1", exception_id="e1", action="replay_webhook",
                resource="wh_9231", status=CapabilityStatus.ACTIVE.value,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    base.update(kw)
    return Capability(**base)


def test_valid_capability_passes():
    ok, reason = _cap().validate("replay_webhook", "wh_9231")
    assert ok and reason == "OK"


def test_wrong_action_or_resource_rejected():
    ok, reason = _cap().validate("refund_payment", "wh_9231")
    assert not ok and reason == "ACTION_MISMATCH"
    ok, reason = _cap().validate("replay_webhook", "wh_OTHER")
    assert not ok and reason == "RESOURCE_MISMATCH"


def test_single_use_consumed():
    cap = _cap(max_attempts=1)
    ok, _ = cap.validate("replay_webhook", "wh_9231")
    assert ok
    cap.consume()
    assert cap.status == CapabilityStatus.CONSUMED.value
    ok, reason = cap.validate("replay_webhook", "wh_9231")
    assert not ok and reason == "CAPABILITY_CONSUMED"


def test_expiry_enforced():
    cap = _cap(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    ok, reason = cap.validate("replay_webhook", "wh_9231")
    assert not ok and reason == "CAPABILITY_EXPIRED"
    assert cap.status == CapabilityStatus.EXPIRED.value


def test_revoked_rejected():
    cap = _cap(status=CapabilityStatus.REVOKED.value)
    ok, reason = cap.validate("replay_webhook", "wh_9231")
    assert not ok and reason == "CAPABILITY_REVOKED"
