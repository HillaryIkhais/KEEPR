"""Verifier: independent proof, never the agent's word."""
from recourse.adapters.crm import CRMAdapter
from recourse.adapters.orders import OrderAdapter
from recourse.adapters.payments import PaymentsAdapter
from recourse.adapters.world import MockWorld
from recourse.core.policies import envelope_for_exception
from recourse.verification.verifier import verify_resolution

POST = ["order.status == paid", "payment.status == succeeded",
        "crm.balance == 0"]


def _worlds():
    w = MockWorld.canonical_missing_webhook()
    return (OrderAdapter(w), PaymentsAdapter(w), CRMAdapter(w), w)


def test_verify_fails_before_recovery():
    orders, payments, crm, _ = _worlds()
    vr = verify_resolution(POST, "order_1842", "pay_5001", "customer_91",
                           orders, payments, crm)
    assert not vr.passed
    assert vr.observed["crm.balance"] == 500


def test_verify_passes_after_recovery():
    orders, payments, crm, w = _worlds()
    from recourse.adapters.world import deliver_webhook
    deliver_webhook(w, "wh_9231")
    vr = verify_resolution(POST, "order_1842", "pay_5001", "customer_91",
                           orders, payments, crm)
    assert vr.passed
    assert vr.observed["crm.balance"] == 0


def test_ambiguous_state_never_verifies():
    w = MockWorld.ambiguous_state()
    orders, payments, crm = (OrderAdapter(w), PaymentsAdapter(w), CRMAdapter(w))
    env = envelope_for_exception("e1", "ambiguous_financial_state")
    assert "sync_crm" in env.forbidden_actions  # policy forbids mutation
    vr = verify_resolution(POST, "order_1842", "pay_5001", "customer_91",
                           orders, payments, crm)
    assert not vr.passed
    assert "AMBIGUOUS_REFUND" in vr.problems
