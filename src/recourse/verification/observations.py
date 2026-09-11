"""Independent observation verification — the agent never declares recovery.

Checks, in order: schema validity, source identity, freshness, record
completeness (via schema), expected-value match, and cross-source
consistency. Any failure rejects the observation; disagreement between
two otherwise-valid sources is CONFLICT (freeze), not success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..failures.schemas import age_seconds, validate_record


@dataclass
class ObservationVerdict:
    passed: bool
    problems: list[str] = field(default_factory=list)
    observed: dict = field(default_factory=dict)


def verify_observation(record: dict | None, *, source: str,
                       expected_sources: tuple[str, ...] | None = None,
                       expected_amount: int | float | None = None,
                       max_age_seconds: float | None = 3600,
                       now: datetime | None = None) -> ObservationVerdict:
    now = now or datetime.now(timezone.utc)
    observed = {"source": source}
    if not isinstance(record, dict):
        return ObservationVerdict(False, ["OBSERVATION_NOT_AN_OBJECT"], observed)
    schema_problems = validate_record(record)
    if schema_problems:
        return ObservationVerdict(False,
                                  [f"SCHEMA_INVALID:{p}" for p in schema_problems],
                                  observed)
    observed.update({"invoice_id": record["invoice_id"],
                     "amount": record["amount"], "status": record["status"]})
    problems: list[str] = []
    if expected_sources is not None and source not in expected_sources:
        problems.append(f"UNTRUSTED_SOURCE:{source}")
    age = age_seconds(record["updated_at"], now)
    if age is None:
        problems.append("UNPARSEABLE_TIMESTAMP")
    else:
        observed["age_seconds"] = round(age, 1)
        if max_age_seconds is not None and age > max_age_seconds:
            problems.append(f"STALE_DATA:age={age:.0f}s")
    if expected_amount is not None and record["amount"] != expected_amount:
        problems.append(f"AMOUNT_MISMATCH:expected={expected_amount}"
                        f" actual={record['amount']}")
    return ObservationVerdict(not problems, problems, observed)


def check_cross_source(first: dict, second: dict) -> list[str]:
    """Two schema-valid records for the same invoice must agree."""
    problems: list[str] = []
    if first.get("invoice_id") != second.get("invoice_id"):
        problems.append("IDENTITY_MISMATCH")
        return problems
    if first.get("amount") != second.get("amount"):
        problems.append(f"CONFLICT:amount {first.get('amount')} != {second.get('amount')}")
    if first.get("status") != second.get("status"):
        problems.append(f"CONFLICT:status {first.get('status')} != {second.get('status')}")
    return problems
