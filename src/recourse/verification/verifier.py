"""Independent verifier — re-queries reality, never trusts the agent's claim."""
from __future__ import annotations

from dataclasses import dataclass

from .postconditions import evaluate_all
from .consistency import check_consistency


@dataclass
class VerificationResult:
    passed: bool
    expected: dict
    observed: dict
    per_predicate: dict
    problems: list


def verify_resolution(expected_postconditions: list[str], order_id: str,
                      payment_id: str, customer_id: str,
                      orders, payments, crm) -> VerificationResult:
    order = orders.get_order(order_id) or {}
    payment = payments.get_payment(payment_id) or {}
    customer = crm.get_customer(customer_id) or {}
    observed = {
        "order.status": order.get("status"),
        "order.amount": order.get("amount"),
        "payment.status": payment.get("status"),
        "payment.amount": payment.get("amount"),
        "crm.balance": customer.get("balance"),
        "crm.status": customer.get("status"),
    }
    expected = {p: True for p in expected_postconditions}
    per = evaluate_all(expected_postconditions, observed) if expected_postconditions else {}
    problems = check_consistency(order, payment, customer)
    passed = bool(per) and all(per.values())
    # Ambiguous financial state can never verify toward a mutation
    if "AMBIGUOUS_REFUND" in problems:
        passed = False
    return VerificationResult(passed=passed, expected=expected,
                              observed=observed, per_predicate=per,
                              problems=problems)
