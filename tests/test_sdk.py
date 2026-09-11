"""SDK: decorator recovery loops and runtime policy derivation."""
import pytest

from recourse.failures.schemas import now_iso
from recourse.sdk import (
    Escalate,
    Freeze,
    RecoveryEscalated,
    RecoveryRuntime,
    Retry,
    Rollback,
    Substitute,
    chains_for,
    recoverable,
)
from recourse.workloads.invoices import (
    SOURCE_PRIMARY,
    AlternateSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
)


def _ok(amount=1137):
    return {"ok": True,
            "data": {"invoice_id": "inv_001", "amount": amount, "currency": "USD",
                     "status": "PAID", "updated_at": now_iso()},
            "meta": {"source": SOURCE_PRIMARY}}


def test_decorator_retries_transient_then_returns_data():
    calls = {"n": 0}

    def flaky(iid):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "error": "HTTP_503", "meta": {}}
        return _ok()

    f = recoverable(schema=True)(flaky)
    assert f("inv_001")["amount"] == 1137
    assert calls["n"] == 2


def test_decorator_substitutes_on_malformed():
    primary = PrimaryAccounting(ledger_amounts(5), faults={"inv_001": "malformed_amount"})
    alternate = AlternateSource(ledger_amounts(5))
    f = recoverable(on_malformed="substitute", alternate=alternate.fetch,
                    alternate_name="fetch_alternate",
                    scope={"fetch_primary", "fetch_alternate"},
                    schema=True)(primary.fetch)
    assert f("inv_001")["amount"] == ledger_amounts(5)["inv_001"]


def test_decorator_blocks_out_of_scope_substitute():
    primary = PrimaryAccounting(ledger_amounts(5), faults={"inv_001": "malformed_amount"})
    alternate = AlternateSource(ledger_amounts(5))
    f = recoverable(on_malformed="substitute", alternate=alternate.fetch,
                    alternate_name="fetch_alternate",
                    scope={"fetch_primary"},  # narrowed: backup forbidden
                    schema=True)(primary.fetch)
    with pytest.raises(RecoveryEscalated) as e:
        f("inv_001")
    assert e.value.reason.startswith("AUTHORITY_WIDENING")
    assert alternate.calls == []


def test_decorator_auth_escalates_after_single_call():
    primary = PrimaryAccounting(ledger_amounts(5), faults={"inv_001": "http_401"})
    f = recoverable()(primary.fetch)
    with pytest.raises(RecoveryEscalated) as e:
        f("inv_001")
    assert "ESCALATE" in e.value.reason
    assert primary.calls.count("inv_001") == 1


def test_decorator_bound_exhaustion():
    calls = {"n": 0}

    def dead(iid):
        calls["n"] += 1
        return {"ok": False, "error": "HTTP_503", "meta": {}}

    f = recoverable(max_attempts=1)(dead)
    with pytest.raises(RecoveryEscalated):
        f("inv_001")
    assert calls["n"] == 1


def test_chains_for_policy_sets():
    full = chains_for([Retry(2), Substitute(), Escalate()])
    assert full["TRANSIENT"] == ["retry", "retry", "substitute", "escalate"]
    assert full["AUTHENTICATION"] == ["escalate"]
    no_retry = chains_for([Substitute(), Escalate()])
    assert "retry" not in no_retry["TRANSIENT"]
    no_sub = chains_for([Retry(2), Escalate()])
    assert no_sub["TRANSIENT"] == ["retry", "retry", "escalate"]
    assert no_sub["MALFORMED_OUTPUT"] == ["reject", "escalate"]
    with_rb = chains_for([Retry(2), Substitute(), Rollback(), Escalate()])
    assert with_rb["TRANSIENT"] == ["retry", "retry", "substitute", "rollback", "escalate"]
    assert with_rb["CONFLICTING_RESULT"] == ["freeze"]  # no rollback for freeze


def test_runtime_freeze_policy():
    ledger = ledger_amounts(5)
    primary = PrimaryAccounting(ledger, faults={"inv_002": "conflict"})
    rt = RecoveryRuntime(scope={"fetch_primary", "fetch_alternate"},
                         policies=[Retry(2), Substitute(), Freeze()])
    run = rt.run_items(invoice_ids(5), fetch_primary=primary.fetch,
                       fetch_alternate=AlternateSource(ledger).fetch,
                       expected=ledger, task="t", run_id="r_fz_sdk")
    assert run.state == "FROZEN"
