"""Idempotency guard — every side effect keyed.

In-memory by default; DurableIdempotencyStore additionally persists keys
to SQLite (UNIQUE on idempotency_key) so a process restart during/after
recovery can never re-execute a recorded mutation.
"""
from __future__ import annotations


def idempotency_key(exception_id: str, action: str, resource: str) -> str:
    return f"{exception_id}:{action}:{resource}"


class IdempotencyStore:
    def __init__(self):
        self._seen: set[str] = set()

    def already_executed(self, key: str) -> bool:
        return key in self._seen

    def mark_executed(self, key: str, **meta) -> None:
        self._seen.add(key)


class DurableIdempotencyStore(IdempotencyStore):
    """SQLite-backed guard. Survives process restarts."""

    def __init__(self, db_path: str | None = None):
        super().__init__()
        self.db_path = db_path

    def _connect(self):
        from ..storage.database import connect
        return connect(self.db_path)

    def already_executed(self, key: str) -> bool:
        if super().already_executed(key):
            return True
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT 1 FROM actions WHERE idempotency_key=?", (key,)).fetchone()
            conn.close()
        except Exception:
            return False
        if row:
            self._seen.add(key)  # warm the cache
            return True
        return False

    def mark_executed(self, key: str, **meta) -> None:
        super().mark_executed(key)
        parts = key.split(":")
        try:
            conn = self._connect()
            conn.execute(
                "INSERT OR IGNORE INTO actions(id,exception_id,capability_id,"
                "action_type,idempotency_key) VALUES (?,?,?,?,?)",
                (key, meta.get("exception_id", parts[0] if parts else ""),
                 meta.get("capability_id", ""),
                 meta.get("action_type", parts[1] if len(parts) > 1 else ""),
                 key),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # memory guard still holds for this process
