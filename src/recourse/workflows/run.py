"""Workflow run machine — PLAN -> ACTION -> OBSERVE -> (FAILURE ->
CLASSIFY -> RECOVER -> VERIFY)* -> RESUME.

Ownership boundary (no split-brain with the exception machine):
  * THIS machine owns run/item progress (PENDING/COMPLETED/ESCALATED/FROZEN).
  * The exception machine (core/) owns recovery AUTHORIZATION: every
    recovery tool call goes through execute_recovery with a fresh
    capability, the run envelope, and the ORIGINAL authority scope.
  * The classifier/verifier own observation truth: classify() then
    verify_observation(); the runner only moves states.

Note: item-level ESCALATED is non-terminal for the RUN (the run resumes
with the next item and reports DONE_WITH_ESCALATIONS). Only FROZEN halts
the run, matching freeze semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..core.authority import AuthorityScope
from ..core.capabilities import Capability
from ..core.envelopes import RecoveryEnvelope
from ..core.states import CapabilityStatus
from ..failures.classifier import classify
from ..failures.selector import (
    ESCALATE,
    FREEZE,
    REJECT,
    REPLAN,
    RETRY,
    RETRY_REMAINDER,
    ROLLBACK,
    SUBSTITUTE,
    next_action,
)
from ..failures.taxonomy import RECOVERABILITY, Failure, FailureClass
from ..recovery.executor import AuthorizationError, execute_recovery
from ..recovery.idempotency import IdempotencyStore
from ..recovery.rollback import RollbackLog
from ..verification.observations import check_cross_source, verify_observation
from ..workloads.invoices import TRUSTED_SOURCES

WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    "PLANNED": {"RUNNING"},
    "RUNNING": {"ACTION_PENDING", "FROZEN", "ESCALATED", "COMPLETED"},
    "ACTION_PENDING": {"OBSERVING", "FAILURE"},
    "OBSERVING": {"SUCCESS", "FAILURE"},
    "SUCCESS": {"RESUMED"},
    "FAILURE": {"CLASSIFYING"},
    "CLASSIFYING": {"RECOVERY_SELECTED", "ESCALATED", "FROZEN"},
    "RECOVERY_SELECTED": {"VERIFYING", "ESCALATED", "FROZEN"},
    "VERIFYING": {"VERIFIED", "RECOVERY_FAILED"},
    "VERIFIED": {"RESUMED"},
    "RECOVERY_FAILED": {"RECOVERY_SELECTED", "ESCALATED", "FROZEN"},
    "RESUMED": {"ACTION_PENDING", "COMPLETED"},
    "ESCALATED": {"RESUMED"},  # item escalated; run continues with next item
    "FROZEN": set(),
    "COMPLETED": set(),
}

TERMINAL_RUN_STATES = {"COMPLETED", "FROZEN"}

# Recovery substitutes tried in order; the first one inside the original
# scope wins. None in scope -> chain collapses to ESCALATE.
SUBSTITUTE_TOOLS = ("fetch_alternate", "fetch_authoritative")

ITEM_PENDING = "PENDING"
ITEM_COMPLETED = "COMPLETED"
ITEM_ESCALATED = "ESCALATED"
ITEM_FROZEN = "FROZEN"


class IllegalWorkflowTransitionError(ValueError):
    pass


@dataclass
class WorkflowRun:
    id: str
    task: str
    items: dict[str, str] = field(default_factory=dict)  # item -> status
    state: str = "PLANNED"
    attempts: dict[str, int] = field(default_factory=dict)
    results: dict[str, dict] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    scope: AuthorityScope = field(default_factory=AuthorityScope)
    rollback: RollbackLog = field(default_factory=RollbackLog)
    halted: bool = False

    def transition_to(self, to: str, event: str = "") -> None:
        if to == self.state:
            return  # re-entering the current state is a no-op, not a transition
        allowed = WORKFLOW_TRANSITIONS.get(self.state, set())
        if to not in allowed:
            raise IllegalWorkflowTransitionError(
                f"Illegal workflow transition {self.state} -> {to}")
        self.state = to
        if event:
            self.event(event)

    def event(self, event: str, detail: str = "") -> None:
        self.events.append({"seq": len(self.events) + 1, "state": self.state,
                            "event": event, "detail": detail})

    def pending_items(self) -> list[str]:
        return [i for i, s in self.items.items() if s == ITEM_PENDING]


def new_run(run_id: str, task: str, item_ids: list[str],
            scope: AuthorityScope) -> WorkflowRun:
    run = WorkflowRun(id=run_id, task=task, scope=scope)
    for i in item_ids:
        run.items[i] = ITEM_PENDING
        run.attempts[i] = 0
    return run


def run_envelope(run_id: str, scope: AuthorityScope,
                 max_attempts: int = 3) -> RecoveryEnvelope:
    """Policy envelope for a workflow run: allowed == original scope tools."""
    return RecoveryEnvelope(
        id=f"env_{run_id}",
        exception_id=run_id,
        allowed_actions=list(scope.tools),
        forbidden_actions=["refund_payment", "modify_payment",
                           "rewrite_transaction", "modify_payment_amount",
                           "request_payroll_access"],
        max_attempts=max_attempts,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        required_evidence=["record_schema_valid", "record_fresh"],
        required_postconditions=[],
    )


def _verify_problem_class(problems: list[str]) -> str:
    if any(p.startswith("CONFLICT") or p.startswith("AMOUNT_MISMATCH")
           for p in problems):
        return FailureClass.CONFLICTING_RESULT.value
    if any("STALE" in p for p in problems):
        return FailureClass.STALE_DATA.value
    return FailureClass.MALFORMED_OUTPUT.value


def _guarded_call(run: WorkflowRun, tool: str, item_id: str,
                  envelope: RecoveryEnvelope, idem: IdempotencyStore,
                  adapters: dict) -> dict:
    """One authorized recovery tool call. Returns the raw tool outcome."""
    if run.attempts[item_id] + 1 > envelope.max_attempts:
        return {"ok": False, "error": "RECOVERY_BLOCKED:ATTEMPTS_EXHAUSTED",
                "tool": tool, "meta": {"source": "recourse-control-plane"}}
    run.attempts[item_id] += 1
    cap = Capability(
        capability_id=f"cap_{run.id}_{item_id}_{run.attempts[item_id]}",
        exception_id=run.id, action=tool, resource=item_id,
        status=CapabilityStatus.ACTIVE.value,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    try:
        out = execute_recovery(tool, item_id, cap, envelope, idem, adapters,
                               scope=run.scope)
    except AuthorizationError as e:
        return {"ok": False, "error": f"RECOVERY_BLOCKED:{e.reason}",
                "tool": tool, "meta": {"source": "recourse-control-plane"}}
    return out["result"]


def authorized_call(run: WorkflowRun, tool: str, item_id: str,
                    envelope: RecoveryEnvelope, idem: IdempotencyStore,
                    adapters: dict) -> dict:
    """Public single authorized recovery call (agent coordinator entrypoint).

    Same gates as the in-runner path: attempt bound, fresh capability,
    envelope permission, original-scope narrowing, idempotency.
    """
    return _guarded_call(run, tool, item_id, envelope, idem, adapters)


def _pick_substitute(run: WorkflowRun, adapters: dict) -> str | None:
    for tool in SUBSTITUTE_TOOLS:
        key = "alternate" if tool == "fetch_alternate" else "authoritative"
        if run.scope.allows(tool) and key in adapters:
            return tool
    return None


def _persist_failure(failure: Failure) -> None:
    try:
        from ..storage.database import connect
        from ..storage.models import save_failure
        conn = connect()
        save_failure(conn, failure)
        conn.close()
    except Exception:
        pass


def _reconcile_item(run: WorkflowRun, item_id: str, adapters: dict,
                    envelope: RecoveryEnvelope, idem: IdempotencyStore,
                    expected: dict[str, int],
                    chains: dict[str, list[str]] | None,
                    max_age_seconds: float) -> None:
    # RUNNING -> ACTION_PENDING for the first item, RESUMED -> ACTION_PENDING after.
    run.transition_to("ACTION_PENDING", f"action:{item_id}")
    outcome = adapters["primary"].fetch(item_id)  # the agent's action
    run.transition_to("OBSERVING", f"observed:{item_id}")
    failure = classify(outcome, workflow_id=run.id, item_id=item_id,
                       tool="fetch_primary", attempt=1, expected_schema=True,
                       max_age_seconds=max_age_seconds)
    prior_valid: dict | None = None
    if failure is None:
        data, meta = outcome.get("data"), outcome.get("meta") or {}
        verdict = verify_observation(
            data, source=meta.get("source", "?"),
            expected_sources=TRUSTED_SOURCES,
            expected_amount=expected.get(item_id),
            max_age_seconds=max_age_seconds)
        if verdict.passed:
            run.transition_to("SUCCESS", f"verified:{item_id}")
            run.items[item_id] = ITEM_COMPLETED
            run.results[item_id] = data
            run.rollback.record(
                item_id, f"discard reconciled output {item_id}",
                lambda i=item_id: run.results.pop(i, None) or {"ok": True})
            run.transition_to("RESUMED", f"resume:{item_id}")
            return
        klass = _verify_problem_class(verdict.problems)
        failure = Failure(
            id=f"F-{item_id}-verify", workflow_id=run.id, item_id=item_id,
            tool="fetch_primary", attempt=1, error=";".join(verdict.problems),
            failure_class=klass, recoverability=RECOVERABILITY[klass])
    else:
        data = outcome.get("data")
        # Only schema-valid records may anchor a later cross-source check;
        # a malformed payload must never become ground truth.
        if isinstance(data, dict) and \
                failure.failure_class != FailureClass.MALFORMED_OUTPUT.value:
            prior_valid = data

    run.transition_to("FAILURE", f"failure:{failure.failure_class}")
    run.failures.append(failure)
    _persist_failure(failure)
    run.transition_to("CLASSIFYING",
                      f"classified:{failure.failure_class}:{failure.recoverability}")
    _recover(run, item_id, failure, prior_valid, adapters, envelope,
             idem, expected, chains, max_age_seconds)


def _recover(run: WorkflowRun, item_id: str, failure: Failure,
             prior_valid: dict | None, adapters: dict,
             envelope: RecoveryEnvelope, idem: IdempotencyStore,
             expected: dict[str, int], chains: dict[str, list[str]] | None,
             max_age_seconds: float) -> None:
    step = 0
    iterations = 0
    failure_class = failure.failure_class
    while True:
        iterations += 1
        if iterations > 12:
            # Paranoia bound: chains are bounded, but failure-class
            # oscillation must never spin forever.
            run.transition_to("ESCALATED", f"recovery-bound:{item_id}")
            run.items[item_id] = ITEM_ESCALATED
            run.transition_to("RESUMED", f"continue-after-bound:{item_id}")
            return
        substitute = _pick_substitute(run, adapters)
        action = next_action(failure_class, step, chains,
                             substitute_available=substitute is not None)
        if action == ESCALATE:
            run.transition_to("ESCALATED", f"escalate:{item_id}:{failure_class}")
            run.items[item_id] = ITEM_ESCALATED
            run.event("ESCALATED",
                      f"{item_id} needs human decision ({failure_class})")
            run.transition_to("RESUMED", f"continue-after-escalation:{item_id}")
            return
        if action == FREEZE:
            run.transition_to("FROZEN", f"freeze:{item_id}:{failure_class}")
            run.items[item_id] = ITEM_FROZEN
            run.halted = True
            return
        run.transition_to("RECOVERY_SELECTED", f"policy:{action}:{item_id}")
        if action in (REJECT, REPLAN):
            run.event("OBSERVATION_REJECTED" if action == REJECT else "REPLAN",
                      f"{item_id}: {action}")
            step += 1
            run.transition_to("VERIFYING", f"{action}:{item_id}")
            run.transition_to("RECOVERY_FAILED", f"continue-chain:{item_id}")
            continue  # loop head re-enters RECOVERY_SELECTED (no-op safe)
        if action == ROLLBACK:
            res = run.rollback.rollback_item(item_id)
            if res.get("errors"):
                run.event("ROLLBACK_FAILED",
                          f"{item_id} errors={res.get('errors')}")
                step += 1
                run.transition_to("VERIFYING", f"rollback-failed:{item_id}")
                run.transition_to("RECOVERY_FAILED", f"continue-chain:{item_id}")
                continue
            run.items[item_id] = ITEM_PENDING
            run.event("ROLLED_BACK",
                      f"{item_id} undone={res.get('undone')}")
            run.transition_to("VERIFYING", f"rolled-back:{item_id}")
            run.transition_to("VERIFIED", f"restored-pending:{item_id}")
            run.transition_to("RESUMED", f"resume:{item_id}")
            return
        tool = "fetch_primary" if action in (RETRY, RETRY_REMAINDER) else substitute
        assert tool is not None  # selector collapses to ESCALATE otherwise
        new_outcome = _guarded_call(run, tool, item_id, envelope, idem, adapters)
        if str(new_outcome.get("error", "")).startswith("RECOVERY_BLOCKED:"):
            run.transition_to("ESCALATED", f"recovery-blocked:{item_id}")
            run.items[item_id] = ITEM_ESCALATED
            run.transition_to("RESUMED", f"continue-after-block:{item_id}")
            return
        run.transition_to("VERIFYING", f"verify:{tool}:{item_id}")
        attempt = run.attempts[item_id] + 1
        new_failure = classify(new_outcome, workflow_id=run.id, item_id=item_id,
                               tool=tool, attempt=attempt, expected_schema=True,
                               max_age_seconds=max_age_seconds)
        if new_failure is None:
            data, meta = new_outcome.get("data"), new_outcome.get("meta") or {}
            verdict = verify_observation(
                data, source=meta.get("source", "?"),
                expected_sources=TRUSTED_SOURCES,
                expected_amount=expected.get(item_id),
                max_age_seconds=max_age_seconds)
            cross: list[str] = []
            if verdict.passed and prior_valid is not None and isinstance(data, dict):
                cross = check_cross_source(prior_valid, data)
            if verdict.passed and not cross:
                run.transition_to("VERIFIED", f"recovery-verified:{item_id}")
                run.items[item_id] = ITEM_COMPLETED
                run.results[item_id] = data
                run.rollback.record(
                    item_id, f"discard reconciled output {item_id}",
                    lambda i=item_id: run.results.pop(i, None) or {"ok": True})
                run.transition_to("RESUMED", f"resume:{item_id}")
                return
            problems = list(verdict.problems) + cross
            klass = _verify_problem_class(problems)
            new_failure = Failure(
                id=f"F-{item_id}-v{attempt}", workflow_id=run.id, item_id=item_id,
                tool=tool, attempt=attempt, error=";".join(problems),
                failure_class=klass, recoverability=RECOVERABILITY[klass])
        run.failures.append(new_failure)
        _persist_failure(new_failure)
        if isinstance(new_outcome.get("data"), dict) and \
                new_failure.failure_class != FailureClass.MALFORMED_OUTPUT.value:
            prior_valid = new_outcome["data"]
        if new_failure.failure_class != failure_class:
            # New classification -> new chain from step 0 (e.g. verification
            # discovering CONFLICT after a STALE substitute -> FREEZE).
            failure_class = new_failure.failure_class
            step = 0
        else:
            step += 1
        run.transition_to("RECOVERY_FAILED",
                          f"recovery-failed:{tool}:{failure_class}")
        # loop head re-enters RECOVERY_SELECTED (no-op safe)


def reconcile_all(run: WorkflowRun, adapters: dict,
                  envelope: RecoveryEnvelope, expected: dict[str, int],
                  chains: dict[str, list[str]] | None = None,
                  max_age_seconds: float = 3600.0,
                  idem: IdempotencyStore | None = None) -> WorkflowRun:
    """Drive every PENDING item through action->observe->recover->resume.

    Partial failure is the normal case: COMPLETED items are never
    re-fetched; only the FAILED item recovers; PENDING items resume after.
    """
    idem = idem or IdempotencyStore()
    run.transition_to("RUNNING", f"start:{run.task}")
    _persist_run(run)
    for item_id in [i for i in run.items if run.items[i] == ITEM_PENDING]:
        if run.halted:
            break
        _reconcile_item(run, item_id, adapters, envelope, idem, expected,
                        chains, max_age_seconds)
        # _reconcile_item ends at RESUMED (next item transitions to
        # ACTION_PENDING) or FROZEN (halted, loop breaks above).
    if run.halted:
        run.transition_to("FROZEN", "halted")  # no-op if already FROZEN
    elif run.pending_items():
        run.event("INCOMPLETE", f"pending={run.pending_items()}")
    elif any(s == ITEM_ESCALATED for s in run.items.values()):
        n = sum(1 for s in run.items.values() if s == ITEM_COMPLETED)
        run.event("DONE_WITH_ESCALATIONS", f"completed={n}")
    else:
        n = sum(1 for s in run.items.values() if s == ITEM_COMPLETED)
        run.transition_to("COMPLETED", f"done:{n}")  # from RESUMED
    _persist_run(run)
    return run


def _persist_run(run: WorkflowRun) -> None:
    try:
        from ..storage.database import connect
        from ..storage.models import save_workflow_run
        conn = connect()
        save_workflow_run(conn, run)
        conn.close()
    except Exception:
        pass
