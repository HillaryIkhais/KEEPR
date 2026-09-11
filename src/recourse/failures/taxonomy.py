"""Failure taxonomy — failures are first-class objects, not strings.

A Failure records what happened (tool, attempt, error code, class,
recoverability, selected policy). Classification never equals recovery:
the classifier says what happened, the policy selector decides what is
permitted next.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"                 # 503/timeout: safe to retry, bounded
    AUTHENTICATION = "AUTHENTICATION"       # 401/expired creds: NEVER retry
    AUTHORIZATION = "AUTHORIZATION"         # 403: NEVER retry, escalate
    INVALID_INPUT = "INVALID_INPUT"         # 400/422: caller bug, escalate
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"   # tool returned untrusted shape
    STALE_DATA = "STALE_DATA"               # record older than freshness bound
    PARTIAL_RESULT = "PARTIAL_RESULT"       # subset returned; retry remainder only
    CONFLICTING_RESULT = "CONFLICTING_RESULT"  # sources disagree: freeze
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"   # connection/DNS: retry then substitute
    UNKNOWN = "UNKNOWN"                     # unrecognized: freeze/escalate


class Recoverability(str, Enum):
    RECOVERABLE = "RECOVERABLE"             # retry/substitute may proceed
    NON_RETRYABLE = "NON_RETRYABLE"         # retry forbidden (auth*, invalid)
    NEEDS_RESOLUTION = "NEEDS_RESOLUTION"   # human/data resolution first
    UNDETERMINED = "UNDETERMINED"           # treat as dangerous: freeze/escalate


RECOVERABILITY: dict[str, str] = {
    FailureClass.TRANSIENT.value: Recoverability.RECOVERABLE.value,
    FailureClass.TOOL_UNAVAILABLE.value: Recoverability.RECOVERABLE.value,
    FailureClass.MALFORMED_OUTPUT.value: Recoverability.RECOVERABLE.value,
    FailureClass.STALE_DATA.value: Recoverability.RECOVERABLE.value,
    FailureClass.PARTIAL_RESULT.value: Recoverability.RECOVERABLE.value,
    FailureClass.AUTHENTICATION.value: Recoverability.NON_RETRYABLE.value,
    FailureClass.AUTHORIZATION.value: Recoverability.NON_RETRYABLE.value,
    FailureClass.INVALID_INPUT.value: Recoverability.NON_RETRYABLE.value,
    FailureClass.CONFLICTING_RESULT.value: Recoverability.NEEDS_RESOLUTION.value,
    FailureClass.UNKNOWN.value: Recoverability.UNDETERMINED.value,
}


@dataclass
class Failure:
    id: str
    workflow_id: str
    item_id: str
    tool: str
    attempt: int
    error: str
    failure_class: str
    recoverability: str
    policy: str = ""  # filled by the selector, never by the agent
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
