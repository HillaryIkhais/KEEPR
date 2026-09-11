from __future__ import annotations

from .world import MockWorld


class WebhookAdapter:
    def __init__(self, world: MockWorld):
        self.world = world

    def get_webhook(self, webhook_id: str) -> dict | None:
        return self.world.webhooks.get(webhook_id)

    def history_for_order(self, order_id: str) -> list:
        return [e for e in self.world.webhook_log
                if self.world.webhooks.get(e["webhook_id"], {}).get("order_id") == order_id]

    def is_missing(self, order_id: str) -> bool:
        return len(self.history_for_order(order_id)) == 0
