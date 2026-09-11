"""State machine: legal transitions pass, illegal ones raise."""
import pytest

from recourse.core.exceptions import ExceptionCase
from recourse.core.transitions import (
    ALLOWED_TRANSITIONS,
    IllegalTransitionError,
    can_transition,
    check_transition,
)


def test_happy_path_transitions():
    case = ExceptionCase(id="e1", type="payment_webhook_failed", subject_id="o1")
    for nxt in ["INVESTIGATING", "RECOVERY_PROPOSED", "AUTHORIZED",
                "EXECUTED", "VERIFYING", "RESOLVED"]:
        case.transition_to(nxt)
    assert case.state == "RESOLVED"


def test_illegal_transition_rejected():
    with pytest.raises(IllegalTransitionError):
        check_transition("DETECTED", "RESOLVED")
    with pytest.raises(IllegalTransitionError):
        check_transition("DETECTED", "EXECUTED")
    # No prompt / caller can bypass:
    case = ExceptionCase(id="e2", type="payment_webhook_failed", subject_id="o1")
    with pytest.raises(IllegalTransitionError):
        case.transition_to("AUTHORIZED")


def test_failure_paths():
    assert can_transition("VERIFYING", "RECOVERY_PROPOSED")
    assert can_transition("VERIFYING", "ESCALATED")
    assert can_transition("AUTHORIZED", "BLOCKED")
    assert not can_transition("RESOLVED", "INVESTIGATING")


def test_allowed_table_matches_spec():
    assert ALLOWED_TRANSITIONS["DETECTED"] == {"INVESTIGATING"}
    assert ALLOWED_TRANSITIONS["VERIFYING"] == {"RESOLVED", "RECOVERY_PROPOSED",
                                                "ESCALATED"}
