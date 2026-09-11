"""In-memory mock world: orders, payments, CRM, webhooks."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockWorld:
    orders: dict = field(default_factory=dict)
    payments: dict = field(default_factory=dict)
    customers: dict = field(default_factory=dict)
    webhooks: dict = field(default_factory=dict)  # webhook_id -> record
    webhook_log: list = field(default_factory=list)  # delivered events

    @classmethod
    def canonical_missing_webhook(cls) -> "MockWorld":
        """Canonical example: $500 paid order, succeeded payment, stale CRM."""
        w = cls()
        w.orders["order_1842"] = {"id": "order_1842", "amount": 500, "status": "paid",
                                  "customer_id": "customer_91"}
        w.payments["pay_5001"] = {"id": "pay_5001", "order_id": "order_1842",
                                  "amount": 500, "status": "succeeded"}
        w.customers["customer_91"] = {"id": "customer_91", "balance": 500,
                                      "status": "unreconciled"}
        w.webhooks["wh_9231"] = {"id": "wh_9231", "order_id": "order_1842",
                                 "payment_id": "pay_5001", "event": "payment.succeeded",
                                 "delivered": False}
        return w

    @classmethod
    def ambiguous_state(cls) -> "MockWorld":
        w = cls.canonical_missing_webhook()
        w.customers["customer_91"] = {"id": "customer_91", "balance": 700,
                                      "status": "unreconciled"}
        w.payments["pay_5001"]["refund"] = {"amount": 200, "metadata": "ambiguous"}
        return w


def deliver_webhook(world: MockWorld, webhook_id: str) -> dict:
    wh = world.webhooks.get(webhook_id)
    if not wh:
        return {"ok": False, "error": "WEBHOOK_NOT_FOUND"}
    if wh.get("delivered"):
        return {"ok": True, "duplicate": True}
    wh["delivered"] = True
    world.webhook_log.append({"webhook_id": webhook_id, "event": wh["event"]})
    # Side effect of a payment.succeeded webhook: reconcile CRM
    order = world.orders.get(wh["order_id"])
    if order:
        cust = world.customers.get(order["customer_id"])
        if cust:
            cust["balance"] = 0
            cust["status"] = "reconciled"
    return {"ok": True, "duplicate": False}
