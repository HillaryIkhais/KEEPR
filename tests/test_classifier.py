"""Classifier: schema-first, codes-not-prose, freshness/partial/conflict."""
from recourse.failures.classifier import classify
from recourse.failures.schemas import now_iso

VALID = {"ok": True,
         "data": {"invoice_id": "inv_001", "amount": 1137, "currency": "USD",
                  "status": "PAID", "updated_at": now_iso()},
         "meta": {"source": "accounting_primary"}}


def test_ok_valid_returns_none():
    assert classify(dict(VALID), expected_schema=True) is None


def test_envelope_shape_untrusted():
    assert classify("all good", expected_schema=True).failure_class == "MALFORMED_OUTPUT"
    assert classify({"data": {}}, expected_schema=True).failure_class == "MALFORMED_OUTPUT"


def test_schema_beats_reassuring_prose():
    bad = {"ok": True,
           "data": {"invoice_id": "inv_481", "amount": "$4,500",
                    "currency": "USD", "status": "PAID", "updated_at": now_iso()},
           "meta": {"source": "accounting_primary", "message": "all good, no error"}}
    f = classify(bad, expected_schema=True)
    assert f.failure_class == "MALFORMED_OUTPUT"
    assert "WRONG_TYPE:amount" in f.error


def test_schema_first_on_error_path():
    bad = {"ok": False, "error": "HTTP_503 SERVICE_UNAVAILABLE",
           "data": {"invoice_id": "x", "amount": "lots", "currency": "USD",
                    "status": "PAID", "updated_at": now_iso()},
           "meta": {}}
    assert classify(bad, expected_schema=True).failure_class == "MALFORMED_OUTPUT"


def test_code_mapping():
    cases = {"HTTP_503 SERVICE_UNAVAILABLE": "TRANSIENT",
             "connection timed out": "TRANSIENT",
             "HTTP_401 EXPIRED_CREDENTIALS": "AUTHENTICATION",
             "HTTP_403 FORBIDDEN": "AUTHORIZATION",
             "HTTP_422 VALIDATION_ERROR": "INVALID_INPUT",
             "409 VERSION_MISMATCH": "CONFLICTING_RESULT",
             "CONNECTION_REFUSED": "TOOL_UNAVAILABLE",
             "something utterly bizarre": "UNKNOWN"}
    for error, klass in cases.items():
        f = classify({"ok": False, "error": error, "meta": {}})
        assert f.failure_class == klass, error


def test_recoverability_never_retries_auth():
    for error in ("HTTP_401 EXPIRED_CREDENTIALS", "HTTP_403 FORBIDDEN"):
        f = classify({"ok": False, "error": error, "meta": {}})
        assert f.recoverability == "NON_RETRYABLE"


def test_stale_and_partial_and_conflict():
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    stale = {"ok": True, "data": {**VALID["data"], "updated_at": old},
             "meta": {"source": "s"}}
    assert classify(stale, expected_schema=True,
                    max_age_seconds=3600).failure_class == "STALE_DATA"
    partial = {"ok": True, "data": [VALID["data"]],
               "meta": {"partial": True, "missing": ["inv_044"]}}
    assert classify(partial, expected_schema=True).failure_class == "PARTIAL_RESULT"
    conflict = {"ok": True, "data": VALID["data"],
                "meta": {"conflict": True, "conflict_detail": "X says REFUNDED"}}
    assert classify(conflict, expected_schema=True).failure_class == "CONFLICTING_RESULT"
