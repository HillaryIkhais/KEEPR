"""Workflow machine: partial failure, resume, rollback, freeze, legality."""
import pytest

from recourse.core.authority import AuthorityScope
from recourse.recovery.idempotency import IdempotencyStore
from recourse.sdk import RecoveryRuntime, Retry, Substitute, Escalate
from recourse.workflows.run import (
    ITEM_COMPLETED,
    ITEM_ESCALATED,
    ITEM_FROZEN,
    IllegalWorkflowTransitionError,
    new_run,
    reconcile_all,
    run_envelope,
)
from recourse.workloads.invoices import (
    AlternateSource,
    AuthoritativeSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
)

SCOPE = AuthorityScope.of("fetch_primary", "fetch_alternate")


def _ctx(n, run_id, scope=SCOPE, **sources):
    ledger = ledger_amounts(n)
    ids = invoice_ids(n)
    primary = sources.get("primary") or PrimaryAccounting(ledger)
    adapters = {"primary": primary}
    if "alternate" in sources:
        adapters["alternate"] = sources["alternate"]
    if "authoritative" in sources:
        adapters["authoritative"] = sources["authoritative"]
    run = new_run(run_id, "test", ids, scope)
    return ledger, ids, adapters, run


def test_illegal_workflow_transition_rejected():
    run = new_run("r", "t", ["a"], SCOPE)
    with pytest.raises(IllegalWorkflowTransitionError):
        run.transition_to("RESOLVED")
    with pytest.raises(IllegalWorkflowTransitionError):
        run.transition_to("COMPLETED")


def test_partial_failure_recovers_only_failed_item():
    ledger, ids, adapters, run = _ctx(
        10, "r_part", primary=PrimaryAccounting(ledger_amounts(10), faults={"inv_005": "http_503"}),
        alternate=AlternateSource(ledger_amounts(10)))
    out = reconcile_all(run, adapters, run_envelope("r_part", SCOPE), ledger_amounts(10))
    assert out.state == "COMPLETED"
    assert all(s == ITEM_COMPLETED for s in out.items.values())
    # TRANSIENT policy is bounded retry (1 + 2) then in-scope substitute...
    assert adapters["primary"].calls.count("inv_005") == 3
    assert adapters["alternate"].calls == ["inv_005"]  # only the failed item
    # ...and every other item was fetched exactly once (no restart).
    for i in ids:
        if i != "inv_005":
            assert adapters["primary"].calls.count(i) == 1


def test_completed_items_never_refetched_on_resume():
    ledger = ledger_amounts(10)
    primary = PrimaryAccounting(ledger)
    adapters = {"primary": primary, "alternate": AlternateSource(ledger)}
    run = new_run("r_res", "t", invoice_ids(10), SCOPE)
    for i in invoice_ids(10)[:7]:  # a previous pass completed 1-7
        run.items[i] = ITEM_COMPLETED
    out = reconcile_all(run, adapters, run_envelope("r_res", SCOPE), ledger)
    assert out.state == "COMPLETED"
    for i in invoice_ids(10)[:7]:
        assert primary.calls.count(i) == 0


def test_rollback_restores_pending_and_undoes():
    ledger = ledger_amounts(10)
    primary = PrimaryAccounting(ledger, faults={"inv_005": "http_503"})
    adapters = {"primary": primary}
    run = new_run("r_rb", "t", invoice_ids(10)[:6], SCOPE)
    undone = []
    run.rollback.record("inv_005", "undo external write",
                        lambda: undone.append("wiped") or {"ok": True})
    chains = {"TRANSIENT": ["rollback", "escalate"]}
    out = reconcile_all(run, adapters, run_envelope("r_rb", SCOPE), ledger,
                        chains=chains)
    assert undone == ["wiped"]
    assert out.items["inv_005"] == "PENDING"  # restored, not retried dirty
    assert any(e["event"] == "ROLLED_BACK" for e in out.events)


def test_conflict_freezes_and_halts():
    ledger = ledger_amounts(10)
    primary = PrimaryAccounting(ledger, faults={"inv_005": "conflict"})
    adapters = {"primary": primary, "alternate": AlternateSource(ledger)}
    run = new_run("r_fz", "t", invoice_ids(10), SCOPE)
    out = reconcile_all(run, adapters, run_envelope("r_fz", SCOPE), ledger)
    assert out.state == "FROZEN" and out.items["inv_005"] == ITEM_FROZEN
    assert out.items["inv_006"] == "PENDING"  # halted before it


def test_auth_failure_escalates_without_retry():
    ledger = ledger_amounts(5)
    primary = PrimaryAccounting(ledger, faults={"inv_003": "http_401"})
    adapters = {"primary": primary, "alternate": AlternateSource(ledger)}
    run = new_run("r_au", "t", invoice_ids(5), SCOPE)
    out = reconcile_all(run, adapters, run_envelope("r_au", SCOPE), ledger)
    assert out.items["inv_003"] == ITEM_ESCALATED
    assert primary.calls.count("inv_003") == 1
    assert sum(1 for s in out.items.values() if s == ITEM_COMPLETED) == 4


def test_runtime_without_substitute_escalates():
    ledger = ledger_amounts(5)
    primary = PrimaryAccounting(ledger, faults={"inv_002": "http_503"})
    rt = RecoveryRuntime(scope={"fetch_primary"},
                         policies=[Retry(2), Escalate()])
    run = rt.run_items(invoice_ids(5), fetch_primary=primary.fetch,
                       expected=ledger, task="t", run_id="r_nosub")
    assert run.items["inv_002"] == ITEM_ESCALATED
    assert primary.calls.count("inv_002") == 3
