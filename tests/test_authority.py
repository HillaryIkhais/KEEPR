"""Authority: recovery cannot widen authority; reads retry freely."""
from datetime import datetime, timedelta, timezone

import pytest

from recourse.core.authority import AuthorityScope
from recourse.core.capabilities import Capability
from recourse.core.envelopes import RecoveryEnvelope
from recourse.core.states import CapabilityStatus
from recourse.failures.selector import next_action
from recourse.recovery.executor import AuthorizationError, execute_recovery
from recourse.recovery.idempotency import IdempotencyStore
from recourse.workloads.invoices import AlternateSource, PrimaryAccounting, ledger_amounts


def _envelope(*allowed: str) -> RecoveryEnvelope:
    return RecoveryEnvelope(
        id="env_t", exception_id="t", allowed_actions=list(allowed),
        forbidden_actions=["refund_payment"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))


def _cap(action: str, resource: str) -> Capability:
    return Capability(capability_id=f"c_{action}", exception_id="t",
                      action=action, resource=resource,
                      status=CapabilityStatus.ACTIVE.value,
                      expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))


def test_scope_narrowing():
    original = AuthorityScope.of("fetch_primary", "fetch_alternate")
    ok, _ = original.check_narrowing(AuthorityScope.of("fetch_primary"))
    assert ok
    ok, reason = original.check_narrowing(AuthorityScope.of("fetch_primary", "request_payroll_access"))
    assert not ok and reason.startswith("AUTHORITY_WIDENING")


def test_executor_blocks_out_of_scope_tool():
    ledger = ledger_amounts(5)
    adapters = {"primary": PrimaryAccounting(ledger)}
    scope = AuthorityScope.of("fetch_primary")  # original grant
    env = _envelope("fetch_primary", "request_payroll_access")  # confused policy
    with pytest.raises(AuthorizationError) as e:
        execute_recovery("request_payroll_access", "payroll_db",
                         _cap("request_payroll_access", "payroll_db"),
                         env, IdempotencyStore(), adapters, scope=scope)
    assert e.value.reason.startswith("AUTHORITY_WIDENING")


def test_executor_without_scope_unchanged():
    ledger = ledger_amounts(5)
    adapters = {"primary": PrimaryAccounting(ledger)}
    env = _envelope("fetch_primary")
    out = execute_recovery("fetch_primary", "inv_001", _cap("fetch_primary", "inv_001"),
                           env, IdempotencyStore(), adapters)
    assert out["result"]["ok"] is True


def test_readonly_recovery_retries_never_duplicate():
    ledger = ledger_amounts(5)
    adapters = {"primary": PrimaryAccounting(ledger),
                "alternate": AlternateSource(ledger)}
    env = _envelope("fetch_alternate")
    idem = IdempotencyStore()
    scope = AuthorityScope.of("fetch_alternate")
    for n in range(3):  # retries of a read must never trip idempotency
        out = execute_recovery("fetch_alternate", "inv_001",
                               _cap(f"fetch_alternate", "inv_001"),
                               env, idem, adapters, scope=scope)
        assert out["result"]["ok"] is True


def test_selector_collapses_without_substitute():
    assert next_action("TRANSIENT", 2, substitute_available=False) == "escalate"
    assert next_action("TRANSIENT", 0) == "retry"
