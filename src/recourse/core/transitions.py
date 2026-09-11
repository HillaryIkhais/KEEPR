"""Deterministic exception state machine. No prompt can bypass this."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Set

from .states import ExceptionState


ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "DETECTED": {"INVESTIGATING"},
    "INVESTIGATING": {"RECOVERY_PROPOSED"},
    "RECOVERY_PROPOSED": {"AUTHORIZED", "ESCALATED"},
    "AUTHORIZED": {"EXECUTED", "BLOCKED"},
    "EXECUTED": {"VERIFYING"},
    "VERIFYING": {"RESOLVED", "RECOVERY_PROPOSED", "ESCALATED"},
    # Terminal-ish escape hatches (audited, always allowed from open states):
    "BLOCKED": {"RECOVERY_PROPOSED", "ESCALATED"},
}

TERMINAL_STATES = {"RESOLVED", "ESCALATED", "QUARANTINED"}


class IllegalTransitionError(ValueError):
    pass


def can_transition(frm: str, to: str) -> bool:
    if to in TERMINAL_STATES and frm not in TERMINAL_STATES:
        # QUARANTINED is reachable from VERIFYING/RECOVERY_PROPOSED on ambiguity
        if to == "QUARANTINED" and frm in {"VERIFYING", "RECOVERY_PROPOSED", "INVESTIGATING", "DETECTED"}:
            return True
        if to in ALLOWED_TRANSITIONS.get(frm, set()):
            return True
        # ESCALATED reachable from open states
        if to == "ESCALATED" and frm in {"DETECTED", "INVESTIGATING", "RECOVERY_PROPOSED", "VERIFYING", "BLOCKED"}:
            return True
        return False
    return to in ALLOWED_TRANSITIONS.get(frm, set())


def check_transition(frm: str, to: str) -> None:
    if not can_transition(frm, to):
        raise IllegalTransitionError(f"Illegal transition {frm} -> {to}")


@dataclass
class TransitionRecord:
    exception_id: str
    frm: str
    to: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
