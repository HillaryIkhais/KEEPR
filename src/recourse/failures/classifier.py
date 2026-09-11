"""Failure classifier — maps untrusted tool outcomes to FailureClass.

Trust order (this is the load-bearing design decision):
  1. Outcome envelope shape (must be a dict with an `ok` flag).
  2. Attached data shape (schema validation) — BEFORE any error string.
  3. Machine error codes (HTTP/status tokens), never free-text messages.
  4. Freshness / partial / conflict markers in `meta`.

Returns None when there is no failure. Returns a Failure otherwise.
Classification never authorizes anything; see selector.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .schemas import age_seconds, validate_record
from .taxonomy import RECOVERABILITY, Failure, FailureClass

# Error-code tokens only. Free-text messages are ignored for classification.
_CODE_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    (FailureClass.AUTHENTICATION.value, ("401", "UNAUTHENTICATED", "EXPIRED_CREDENTIALS", "INVALID_TOKEN")),
    (FailureClass.AUTHORIZATION.value, ("403", "FORBIDDEN", "ACCESS_DENIED")),
    (FailureClass.INVALID_INPUT.value, ("400", "422", "INVALID_INPUT", "VALIDATION_ERROR", "NOT_FOUND", "404")),
    (FailureClass.CONFLICTING_RESULT.value, ("409", "CONFLICT", "VERSION_MISMATCH")),
    (FailureClass.TRANSIENT.value, ("503", "504", "429", "TIMEOUT", "TIMED OUT", "TEMPORARY", "SERVICE_UNAVAILABLE", "HTTP_503")),
    (FailureClass.TOOL_UNAVAILABLE.value, ("CONNECTION_REFUSED", "DNS_ERROR", "UNREACHABLE", "TOOL_UNAVAILABLE")),
    (FailureClass.STALE_DATA.value, ("STALE",)),
    (FailureClass.PARTIAL_RESULT.value, ("PARTIAL",)),
)


def _code_of(error: str) -> str | None:
    upper = (error or "").upper()
    for klass, tokens in _CODE_MAP:
        if any(t in upper for t in tokens):
            return klass
    return None


def classify(outcome: object, *, workflow_id: str = "", item_id: str = "",
             tool: str = "", attempt: int = 1,
             expected_schema: bool = False,
             max_age_seconds: float | None = None,
             now: datetime | None = None) -> Failure | None:
    """Classify one tool outcome. None == no failure detected."""
    now = now or datetime.now(timezone.utc)
    counter = classify._counter = getattr(classify, "_counter", 0) + 1

    def make(klass: str, error: str) -> Failure:
        return Failure(
            id=f"F-{counter}", workflow_id=workflow_id, item_id=item_id,
            tool=tool or "unknown", attempt=attempt, error=error,
            failure_class=klass, recoverability=RECOVERABILITY[klass],
            observed_at=now,
        )

    # 1. Envelope shape — untrusted until proven otherwise.
    if not isinstance(outcome, dict) or "ok" not in outcome:
        return make(FailureClass.MALFORMED_OUTPUT.value,
                    "OUTCOME_ENVELOPE_INVALID")
    data = outcome.get("data")
    meta = outcome.get("meta") or {}
    if not isinstance(meta, dict):
        return make(FailureClass.MALFORMED_OUTPUT.value, "META_NOT_AN_OBJECT")

    # 2. Attached data shape beats any embedded error/message string.
    if data is not None and expected_schema:
        records = data if isinstance(data, list) else [data]
        for rec in records:
            problems = validate_record(rec)
            if problems:
                return make(FailureClass.MALFORMED_OUTPUT.value,
                            f"SCHEMA_INVALID:{';'.join(problems)}")

    if outcome.get("ok") is True:
        # 3. Explicit conflict markers from the source itself.
        if meta.get("conflict") is True:
            return make(FailureClass.CONFLICTING_RESULT.value,
                        str(meta.get("conflict_detail", "SOURCES_DISAGREE")))
        # 4. Partial results short-circuit before freshness.
        if meta.get("partial") is True:
            return make(FailureClass.PARTIAL_RESULT.value,
                        f"PARTIAL_RESULT:missing={meta.get('missing', [])}")
        # 5. Freshness on each record (schema already proven above).
        if max_age_seconds is not None and expected_schema and data is not None:
            records = data if isinstance(data, list) else [data]
            for rec in records:
                age = age_seconds(rec["updated_at"], now)
                if age is None:
                    return make(FailureClass.MALFORMED_OUTPUT.value,
                                "UNPARSEABLE_TIMESTAMP")
                if age > max_age_seconds:
                    return make(FailureClass.STALE_DATA.value,
                                f"STALE_DATA:age={age:.0f}s")
        return None

    # ok is False: schema-first, then machine codes, never prose.
    error = str(outcome.get("error", "UNKNOWN_ERROR"))
    if data is not None and expected_schema:
        records = data if isinstance(data, list) else [data]
        for rec in records:
            if validate_record(rec):
                return make(FailureClass.MALFORMED_OUTPUT.value,
                            "SCHEMA_INVALID_ON_ERROR_PATH")
    klass = _code_of(error)
    if klass is not None:
        return make(klass, error)
    return make(FailureClass.UNKNOWN.value, error)
