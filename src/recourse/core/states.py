"""Core state definitions. Deterministic, no LLM involved."""
from enum import Enum


class ExceptionState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    RECOVERY_PROPOSED = "RECOVERY_PROPOSED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTED = "EXECUTED"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"


class CapabilityStatus(str, Enum):
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
