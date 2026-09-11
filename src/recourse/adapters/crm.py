from __future__ import annotations

from .world import MockWorld


class CRMAdapter:
    def __init__(self, world: MockWorld):
        self.world = world

    def get_customer(self, customer_id: str) -> dict | None:
        return self.world.customers.get(customer_id)

    def sync_customer(self, customer_id: str) -> dict:
        cust = self.world.customers.get(customer_id)
        if not cust:
            return {"ok": False, "error": "CUSTOMER_NOT_FOUND"}
        # Recompute from ground truth: if the customer's order payment succeeded
        # and its webhook was delivered, balance goes to 0.
        for order in self.world.orders.values():
            if order.get("customer_id") == customer_id and order.get("status") == "paid":
                cust["balance"] = 0
                cust["status"] = "reconciled"
                return {"ok": True}
        return {"ok": False, "error": "NO_PAID_ORDER"}
