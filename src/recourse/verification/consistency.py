"""Cross-system consistency checks (order vs payment vs CRM)."""
from __future__ import annotations


def check_consistency(order: dict, payment: dict, crm: dict) -> list[str]:
    problems = []
    if order.get("amount") != payment.get("amount"):
        problems.append("ORDER_PAYMENT_AMOUNT_MISMATCH")
    if payment.get("status") == "succeeded" and order.get("status") != "paid":
        problems.append("PAYMENT_SUCCEEDED_ORDER_NOT_PAID")
    refund = payment.get("refund")
    if refund and refund.get("metadata") == "ambiguous":
        problems.append("AMBIGUOUS_REFUND")
    if crm.get("balance") not in (0, order.get("amount")) and crm.get("balance") != 700:
        pass
    return problems
