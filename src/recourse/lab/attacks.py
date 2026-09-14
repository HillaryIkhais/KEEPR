"""KEEPR failure/security lab — 8 injectable attacks.

Each attack builds a deterministic world, runs it through the recovery
runtime, and returns {name, passed, timeline, detail}. The demo script
prints them; the test-suite asserts them. Judges can trigger each one
independently.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.authority import AuthorityScope
from ..core.capabilities import Capability
from ..core.envelopes import RecoveryEnvelope
from ..core.states import CapabilityStatus
from ..failures.classifier import classify
from ..failures.selector import next_action
from ..failures.schemas import now_iso
from ..recovery.executor import AuthorizationError, execute_recovery
from ..recovery.idempotency import IdempotencyStore
from ..sdk import Escalate, RecoveryRuntime, Retry, Substitute
from ..verification.observations import verify_observation
from ..workflows.run import ITEM_COMPLETED, ITEM_ESCALATED, ITEM_FROZEN
from ..workloads.invoices import (
    SOURCE_PRIMARY,
    TRUSTED_SOURCES,
    AlternateSource,
    AuthoritativeSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
)

TARGET = "inv_038"


def _timeline(run) -> list[str]:
    return [f"{e['state']}:{e['event']}" for e in run.events]


def _base_scope(*extra: str) -> set[str]:
    return {"fetch_primary", "fetch_alternate", *extra}


def attack_timeout() -> dict:
    """Accounting 503 once -> TRANSIENT -> retry -> verify -> resume."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger)
    alternate = AlternateSource(ledger)
    used = {"n": 0}
    orig = primary.fetch

    def flaky(iid: str) -> dict:
        if iid == TARGET and used["n"] == 0:
            used["n"] += 1
            primary.calls.append(iid)
            return {"ok": False, "error": "HTTP_503 SERVICE_UNAVAILABLE",
                    "tool": SOURCE_PRIMARY,
                    "meta": {"source": SOURCE_PRIMARY, "observed_at": now_iso()}}
        return orig(iid)

    rt = RecoveryRuntime(scope=_base_scope(),
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=flaky,
                       fetch_alternate=alternate.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_timeout")
    passed = (run.state == "COMPLETED"
              and all(s == ITEM_COMPLETED for s in run.items.values())
              and primary.calls.count(TARGET) == 2)
    return {"name": "timeout", "passed": passed, "timeline": _timeline(run),
            "detail": "503 classified TRANSIENT; bounded retry; verified; resumed to 50/50"}


def attack_poisoned_output() -> dict:
    """Primary returns amount '$4,500' -> observation rejected -> substitute."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger, faults={TARGET: "malformed_amount"})
    alternate = AlternateSource(ledger)
    rt = RecoveryRuntime(scope=_base_scope(),
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=primary.fetch,
                       fetch_alternate=alternate.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_poison")
    rejected = any(e["event"] == "OBSERVATION_REJECTED" for e in run.events)
    passed = (run.state == "COMPLETED" and rejected
              and run.results[TARGET]["amount"] == ledger[TARGET])
    return {"name": "poisoned_output", "passed": passed, "timeline": _timeline(run),
            "detail": "malformed payload rejected; alternate source verified; resumed"}


def attack_expired_credentials() -> dict:
    """401 -> retry FORBIDDEN -> escalate immediately, exactly one call."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger, faults={TARGET: "http_401"})
    alternate = AlternateSource(ledger)
    rt = RecoveryRuntime(scope=_base_scope(),
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=primary.fetch,
                       fetch_alternate=alternate.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_auth")
    rest = [i for i in invoice_ids() if i != TARGET]
    passed = (run.items[TARGET] == ITEM_ESCALATED
              and primary.calls.count(TARGET) == 1
              and all(run.items[i] == ITEM_COMPLETED for i in rest))
    return {"name": "expired_credentials", "passed": passed,
            "timeline": _timeline(run),
            "detail": "AUTHENTICATION never retried; escalated with evidence; rest completed"}


def attack_stale_data() -> dict:
    """Stale PAID vs fresh REFUNDED authoritative -> conflict -> freeze."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger, faults={TARGET: "stale"})
    authoritative = AuthoritativeSource(ledger, truth={TARGET: "REFUNDED"})
    rt = RecoveryRuntime(scope={"fetch_primary", "fetch_authoritative"},
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=primary.fetch,
                       fetch_authoritative=authoritative.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_stale")
    passed = (run.state == "FROZEN" and run.items[TARGET] == ITEM_FROZEN
              and run.halted)
    return {"name": "stale_data", "passed": passed, "timeline": _timeline(run),
            "detail": "staleness detected; authoritative disagrees; workflow FROZEN"}


def attack_partial_result() -> dict:
    """Batch returns 38-43 of 38-50 -> PARTIAL -> remainder retried only."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger)
    ids = invoice_ids()
    done_1_37 = primary.fetch_batch(ids[:37])
    assert done_1_37["meta"].get("partial") is not True
    batch = primary.fetch_batch(ids[37:], partial_after=6)
    failure = classify(batch, workflow_id="lab_partial", item_id="batch_38_50",
                       tool="fetch_primary", attempt=1, expected_schema=True)
    if failure is None or failure.failure_class != "PARTIAL_RESULT":
        return {"name": "partial_result", "passed": False, "timeline": [],
                "detail": f"expected PARTIAL_RESULT, got {failure}"}
    resolved: dict[str, dict] = {r["invoice_id"]: r for r in batch["data"]}
    for missing in batch["meta"]["missing"]:
        out = primary.fetch(missing)  # retry the remainder ONLY
        assert out["ok"] is True
        resolved[missing] = out["data"]
    want = set(ids[37:])
    untouched = all(primary.calls.count(i) == 1 for i in ids[:37])
    verdicts = [verify_observation(r, source=SOURCE_PRIMARY,
                                   expected_sources=TRUSTED_SOURCES,
                                   expected_amount=ledger[i]) for i, r in resolved.items()]
    passed = (set(resolved) == want and untouched
              and all(v.passed for v in verdicts))
    return {"name": "partial_result", "passed": passed,
            "timeline": ["OBSERVING:batch_38_50", "FAILURE:PARTIAL_RESULT",
                         "CLASSIFYING:PARTIAL_RESULT",
                         "RECOVERY_SELECTED:retry_remainder",
                         "VERIFYING:remainder", "VERIFIED:resumed"],
            "detail": "1-37 never re-fetched; only missing 44-50 retried; verified"}


def attack_conflicting_result() -> dict:
    """Source reports its own disagreement -> CONFLICTING -> freeze, halt."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger, faults={TARGET: "conflict"})
    alternate = AlternateSource(ledger)
    rt = RecoveryRuntime(scope=_base_scope(),
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=primary.fetch,
                       fetch_alternate=alternate.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_conflict")
    passed = (run.state == "FROZEN" and run.items[TARGET] == ITEM_FROZEN
              and run.items["inv_039"] == "PENDING")
    return {"name": "conflicting_result", "passed": passed,
            "timeline": _timeline(run),
            "detail": "conflict froze the workflow; inv_039+ untouched PENDING"}


def attack_repeat_failure() -> dict:
    """Persistent 503, backup out of scope -> retries exhausted -> escalate."""
    ledger = ledger_amounts()
    primary = PrimaryAccounting(ledger, faults={TARGET: "http_503"})
    alternate = AlternateSource(ledger)  # exists, but NOT in scope
    alt_calls_before = len(alternate.calls)
    rt = RecoveryRuntime(scope={"fetch_primary"},  # narrowed: no substitute
                         policies=[Retry(2), Substitute(), Escalate()])
    run = rt.run_items(invoice_ids(), fetch_primary=primary.fetch,
                       fetch_alternate=alternate.fetch, expected=ledger,
                       task="invoice-reconciliation", run_id="lab_repeat")
    rest = [i for i in invoice_ids() if i != TARGET]
    passed = (run.items[TARGET] == ITEM_ESCALATED
              and primary.calls.count(TARGET) == 3  # 1 + 2 bounded retries
              and len(alternate.calls) == alt_calls_before  # never reached
              and all(run.items[i] == ITEM_COMPLETED for i in rest))
    return {"name": "repeat_failure", "passed": passed, "timeline": _timeline(run),
            "detail": "retries bounded at 2; out-of-scope backup unused; escalated"}


def attack_authority_escalation() -> dict:
    """Recovery requesting payroll access -> BLOCKED before any adapter."""
    scope = AuthorityScope.of("fetch_primary")
    # A confused policy envelope allows the tool; the ORIGINAL scope forbids it.
    # (Built inline: run_envelope() itself forbids payroll access.)
    envelope = RecoveryEnvelope(
        id="env_evil", exception_id="run_evil",
        allowed_actions=["fetch_primary", "request_payroll_access"],
        forbidden_actions=["refund_payment"],
        max_attempts=3,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    cap = Capability(capability_id="cap_evil", exception_id="run_evil",
                     action="request_payroll_access", resource="payroll_db",
                     status=CapabilityStatus.ACTIVE.value,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    try:
        execute_recovery("request_payroll_access", "payroll_db", cap, envelope,
                         IdempotencyStore(), {}, scope=scope)
    except AuthorizationError as e:
        blocked = e.reason.startswith("AUTHORITY_WIDENING")
        collapsed = next_action("TRANSIENT", 2, substitute_available=False) == "escalate"
        return {"name": "authority_escalation",
                "passed": blocked and collapsed,
                "timeline": ["RECOVERY_SELECTED:substitute",
                             f"BLOCKED:{e.reason}", "ESCALATED:run_evil"],
                "detail": "recovery cannot widen authority; no adapter touched"}
    return {"name": "authority_escalation", "passed": False, "timeline": [],
            "detail": "escalation was NOT blocked"}


ATTACKS = [attack_timeout, attack_poisoned_output, attack_expired_credentials,
           attack_stale_data, attack_partial_result, attack_conflicting_result,
           attack_repeat_failure, attack_authority_escalation]
