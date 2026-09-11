"""RECOURSE failure gauntlet — 6 security + recovery tests.

Run:  python demo/run_failure_gauntlet.py
Exit code 0 iff 6/6 pass.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")

from recourse.adapters.crm import CRMAdapter
from recourse.adapters.orders import OrderAdapter
from recourse.adapters.payments import PaymentsAdapter
from recourse.adapters.world import MockWorld
from recourse.core.policies import envelope_for_exception
from recourse.scenarios import (
    conflicting_payment,
    expired_capability,
    hallucinated_success,
    missing_webhook,
    replay_attack,
)
from recourse.verification.verifier import verify_resolution


def ambiguous_escalation() -> dict:
    """TEST 06 — ambiguous financial state must escalate, never mutate."""
    world = MockWorld.ambiguous_state()
    orders, payments, crm = (OrderAdapter(world), PaymentsAdapter(world),
                             CRMAdapter(world))
    env = envelope_for_exception("exc_amb", "ambiguous_financial_state")
    mutation_forbidden = all(a in env.forbidden_actions
                             for a in ("sync_crm", "replay_webhook",
                                       "modify_payment_amount", "refund_payment"))
    vr = verify_resolution(["order.status == paid",
                            "payment.status == succeeded",
                            "crm.balance == 0"],
                           "order_1842", "pay_5001", "customer_91",
                           orders, payments, crm)
    # Cannot establish authoritative truth -> quarantine/escalate, CRM untouched.
    passed = (mutation_forbidden and not vr.passed
              and "AMBIGUOUS_REFUND" in vr.problems
              and world.customers["customer_91"]["balance"] == 700)
    return {"name": "ambiguous_financial_state", "passed": passed,
            "state": "QUARANTINED",
            "detail": "truth unestablishable; HUMAN DECISION REQUIRED"}


TESTS = [
    ("TEST 01 — Recover missing webhook", missing_webhook.run),
    ("TEST 02 — Block forbidden financial mutation", conflicting_payment.run),
    ("TEST 03 — Reject false resolution claim", hallucinated_success.run),
    ("TEST 04 — Prevent capability replay", replay_attack.run),
    ("TEST 05 — Reject expired authorization", expired_capability.run),
    ("TEST 06 — Escalate ambiguous financial state", ambiguous_escalation),
]


def main() -> int:
    print("RECOURSE FAILURE GAUNTLET\n")
    passed = 0
    for label, fn in TESTS:
        try:
            r = fn()
            ok = bool(r.get("passed"))
        except Exception as e:  # a crash is a failed test
            r, ok = {"detail": f"EXCEPTION: {e}"}, False
        mark = "✓" if ok else "✗"
        print(f"[{mark}] {label}")
        print(f"    -> {r.get('detail', '')} "
              f"(state={r.get('state', r.get('reason', '?'))})")
        passed += ok
    print(f"\n{passed} / {len(TESTS)} SECURITY + RECOVERY TESTS "
          f"{'PASSED' if passed == len(TESTS) else 'FAILED'}")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
