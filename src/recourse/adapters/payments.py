from __future__ import annotations

from .world import MockWorld, deliver_webhook


class PaymentsAdapter:
    """Alias-friendly payment adapter (spec uses adapters/payments.py)."""

    def __init__(self, world: MockWorld):
        self.world = world

    def get_payment(self, payment_id: str) -> dict | None:
        return self.world.payments.get(payment_id)

    def replay_webhook(self, webhook_id: str) -> dict:
        return deliver_webhook(self.world, webhook_id)
