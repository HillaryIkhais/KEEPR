"""Rollback log — compensating actions per workflow item.

When a recovery step has changed external (or durable local) state and a
later step fails, the policy chain can ROLLBACK: compensations run LIFO
and the item is restored to PENDING instead of being retried on top of
dirty state.
"""
from __future__ import annotations

from typing import Callable


class RollbackLog:
    def __init__(self):
        self._compensations: dict[str, list[tuple[str, Callable[[], dict]]]] = {}
        self.rolled_back: list[str] = []

    def record(self, item_id: str, description: str,
               compensate: Callable[[], dict]) -> None:
        self._compensations.setdefault(item_id, []).append((description, compensate))

    def pending_for(self, item_id: str) -> list[str]:
        return [d for d, _ in self._compensations.get(item_id, [])]

    def rollback_item(self, item_id: str) -> dict:
        entries = self._compensations.pop(item_id, [])
        undone = []
        errors = []
        for description, compensate in reversed(entries):
            try:
                result = compensate()
                if isinstance(result, dict) and result.get("ok") is False:
                    errors.append(description)
                else:
                    undone.append(description)
            except Exception:
                errors.append(description)
        self.rolled_back.append(item_id)
        return {"ok": not errors, "undone": undone, "errors": errors}
