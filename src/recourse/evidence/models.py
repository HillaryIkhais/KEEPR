"""Evidence model + append-only ledger + collector."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Evidence:
    id: str
    exception_id: str
    source: str
    query: str
    value: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceLedger:
    def __init__(self):
        self._items: list[Evidence] = []
        self._counter = 0

    def append(self, exception_id: str, source: str, query: str, value: dict) -> Evidence:
        self._counter += 1
        ev = Evidence(id=f"ev_{self._counter:04d}", exception_id=exception_id,
                      source=source, query=query, value=dict(value))
        self._items.append(ev)
        return ev

    def for_exception(self, exception_id: str) -> list[Evidence]:
        return [e for e in self._items if e.exception_id == exception_id]

    def __len__(self) -> int:
        return len(self._items)
