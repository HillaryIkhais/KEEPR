from __future__ import annotations

from .world import MockWorld


class OrderAdapter:
    def __init__(self, world: MockWorld):
        self.world = world

    def get_order(self, order_id: str) -> dict | None:
        return self.world.orders.get(order_id)


class PaymentAdapter:
    def __init__(self, world: MockWorld):
        self.world = world

    def get_payment(self, payment_id: str) -> dict | None:
        return self.world.payments.get(payment_id)

    def replay_webhook(self, webhook_id: str) -> dict:
        from .world import deliver_webhook
        return deliver_webhook(self.world, webhook_id)
