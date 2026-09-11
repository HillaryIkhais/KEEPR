"""Adversarial extras: oscillation bound, rollback failure, terminal integrity."""
from recourse.core.transitions import ALLOWED_TRANSITIONS, can_transition
from recourse.workflows.run import (
    WORKFLOW_TRANSITIONS,
    IllegalWorkflowTransitionError,
    new_run,
    reconcile_all,
    run_envelope,
)
from recourse.core.authority import AuthorityScope
from recourse.workloads.invoices import (
    AlternateSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
)

SCOPE = AuthorityScope.of("fetch_primary", "fetch_alternate")


def test_recovery_oscillation_is_bounded():
    """503 primary vs malformed alternate: classes flip forever -> must stop."""
    ledger = ledger_amounts(5)
    primary = PrimaryAccounting(ledger, faults={"inv_003": "http_503"})
    alternate = AlternateSource(ledger, faults={"inv_003": "malformed"})
    adapters = {"primary": primary, "alternate": alternate}
    run = new_run("r_osc", "t", invoice_ids(5), SCOPE)
    out = reconcile_all(run, adapters, run_envelope("r_osc", SCOPE), ledger)
    assert out.items["inv_003"] == "ESCALATED"  # stopped, handed to human
    total_calls = (primary.calls.count("inv_003") + alternate.calls.count("inv_003"))
    assert total_calls <= 13  # bounded: chains + 12-iteration paranoia bound
    rest = [i for i in invoice_ids(5) if i != "inv_003"]
    assert all(out.items[i] == "COMPLETED" for i in rest)


def test_failed_compensation_continues_chain_safely():
    """Rollback itself fails -> chain continues to escalate, never stranded."""
    ledger = ledger_amounts(5)
    primary = PrimaryAccounting(ledger, faults={"inv_002": "http_503"})
    adapters = {"primary": primary}
    run = new_run("r_rbf", "t", invoice_ids(5)[:3], SCOPE)

    def bad_compensate():
        raise RuntimeError("compensation crashed")

    run.rollback.record("inv_002", "undo external write", bad_compensate)
    chains = {"TRANSIENT": ["rollback", "escalate"]}
    out = reconcile_all(run, adapters, run_envelope("r_rbf", SCOPE), ledger,
                        chains=chains)
    assert out.items["inv_002"] == "ESCALATED"
    assert any(e["event"] == "ROLLBACK_FAILED" for e in out.events)


def test_terminal_states_cannot_execute_again():
    # Exception machine: terminals have no outgoing edges at all.
    for terminal in ("RESOLVED", "ESCALATED", "QUARANTINED"):
        for target in ("DETECTED", "INVESTIGATING", "RECOVERY_PROPOSED",
                       "AUTHORIZED", "EXECUTED", "VERIFYING", "RESOLVED"):
            assert not can_transition(terminal, target), (terminal, target)
    assert "RESOLVED" not in ALLOWED_TRANSITIONS
    # Workflow machine: COMPLETED/FROZEN are dead ends; the documented
    # exception is item-level ESCALATED -> RESUMED (run continues).
    assert WORKFLOW_TRANSITIONS["COMPLETED"] == set()
    assert WORKFLOW_TRANSITIONS["FROZEN"] == set()
    assert WORKFLOW_TRANSITIONS["ESCALATED"] == {"RESUMED"}
    run = new_run("r_term", "t", ["a"], SCOPE)
    run.state = "COMPLETED"
    try:
        run.transition_to("ACTION_PENDING")
        raise AssertionError("COMPLETED must not transition")
    except IllegalWorkflowTransitionError:
        pass
    run.state = "FROZEN"
    try:
        run.transition_to("RUNNING")
        raise AssertionError("FROZEN must not transition")
    except IllegalWorkflowTransitionError:
        pass
    # Illegal skips are rejected even mid-run. (RUNNING -> COMPLETED is the
    # legitimate empty-run edge, so it is not in the illegal list.)
    run2 = new_run("r_term2", "t", ["a"], SCOPE)
    run2.transition_to("RUNNING")
    for bad in ("VERIFYING", "RESUMED", "OBSERVING"):
        try:
            run2.transition_to(bad)
            raise AssertionError(f"RUNNING -> {bad} must be illegal")
        except IllegalWorkflowTransitionError:
            pass
    empty = new_run("r_empty", "t", [], SCOPE)
    empty.transition_to("RUNNING")
    empty.transition_to("COMPLETED")  # vacuous completion is legal
