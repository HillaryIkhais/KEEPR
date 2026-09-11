"""Scenario 3 — agent hallucinates success; verifier must reject the claim."""
from __future__ import annotations

from ..adapters.crm import CRMAdapter
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.world import MockWorld
from ..core.policies import envelope_for_exception
from ..verification.verifier import verify_resolution


def run() -> dict:
    # Agent claims "CRM synchronization successful" WITHOUT executing anything.
    world = MockWorld.canonical_missing_webhook()
    orders, payments, crm = (OrderAdapter(world), PaymentsAdapter(world),
                             CRMAdapter(world))
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")
    agent_claim = "CRM synchronization successful."
    vr = verify_resolution(env.required_postconditions, "order_1842", "pay_5001",
                           "customer_91", orders, payments, crm)
    passed = (not vr.passed) and vr.observed.get("crm.balance") == 500
    return {"name": "hallucinated_success", "passed": passed,
            "agent_claim": agent_claim,
            "expected_balance": 0, "actual_balance": vr.observed.get("crm.balance"),
            "state": "OPEN",
            "detail": "resolution claim rejected; state remains OPEN"}
