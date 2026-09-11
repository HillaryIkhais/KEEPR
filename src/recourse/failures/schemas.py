"""Schema-first validation for untrusted tool output.

Rule: a record's SHAPE is checked before any of its content (including any
embedded error/message string) is trusted. A payload that fails schema
validation is MALFORMED_OUTPUT even if it claims to be a benign error.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "invoice_id": (str,),
    "amount": (int, float),  # numeric only: "$4,500" is malformed, not money
    "currency": (str,),
    "status": (str,),
    "updated_at": (str,),
}

REQUIRED_FIELDS = ("invoice_id", "amount", "currency", "status", "updated_at")
STATUS_ENUM = ("PAID", "REFUNDED", "PENDING")


def validate_record(record: Any) -> list[str]:
    """Return a list of schema problems (empty == valid)."""
    problems: list[str] = []
    if not isinstance(record, dict):
        return ["NOT_AN_OBJECT"]
    for f in REQUIRED_FIELDS:
        if f not in record:
            problems.append(f"MISSING_FIELD:{f}")
    for f, types in FIELD_TYPES.items():
        if f in record and not isinstance(record[f], types):
            problems.append(f"WRONG_TYPE:{f}")
    # bool is a subclass of int — never a valid amount.
    if isinstance(record.get("amount"), bool):
        problems.append("WRONG_TYPE:amount")
    if isinstance(record.get("currency"), str) and len(record["currency"]) != 3:
        problems.append("BAD_VALUE:currency")
    if "status" in record and record["status"] not in STATUS_ENUM:
        problems.append("BAD_VALUE:status")
    if isinstance(record.get("updated_at"), str):
        try:
            datetime.fromisoformat(record["updated_at"])
        except ValueError:
            problems.append("BAD_VALUE:updated_at")
    return problems


def parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def age_seconds(updated_at: str, now: datetime | None = None) -> float | None:
    dt = parse_time(updated_at)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - dt).total_seconds()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
