from .all import (missing_webhook, conflicting_payment, hallucinated_success,
                      replay_attack, expired_capability)
from ..adapters.world import MockWorld
from ..core.policies import envelope_for_exception
from ..verification.verifier import verify_resolution
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.crm import CRMAdapter


def ambiguous_case():
    """$500 order/payment, $700 CRM, ambiguous $200 refund -> QUARANTINE, no mutation."""
    world = MockWorld.ambiguous_state()
    o, p, c = OrderAdapter(world), PaymentsAdapter(world), CRMAdapter(world)
    env = envelope_for_exception("exc_amb", "ambiguous_financial_state")
    result = verify_resolution(["crm.balance == 0"], "order_1842", "pay_5001",
                               "customer_91", o, p, c)
    balance_untouched = world.customers["customer_91"]["balance"] == 700
    must_escalate = (not result.passed) and "AMBIGUOUS_REFUND" in result.problems
    ok = must_escalate and balance_untouched and "sync_crm" not in env.allowed_actions
    return ok, f"quarantined problems={result.problems}"
