"""Recovery policy selector — failure class decides what is permitted next.

Chains are bounded and ordered. The two hard rules:
  * AUTHENTICATION / AUTHORIZATION / INVALID_INPUT: retry is forbidden.
  * SUBSTITUTE is only offered when the alternate tool is inside the
    original authority scope; otherwise the chain collapses to ESCALATE
    (recovery cannot widen authority — enforced with core.authority).
"""
from __future__ import annotations

from .taxonomy import FailureClass

# Recovery action vocabulary shared with the workflow runner.
RETRY = "retry"
REJECT = "reject"              # discard the poisoned observation
SUBSTITUTE = "substitute"      # try an alternate in-scope source/tool
RETRY_REMAINDER = "retry_remainder"  # partial results: only the missing slice
ROLLBACK = "rollback"          # undo external effects, restore PENDING
REPLAN = "replan"              # select a different plan shape (reserved)
FREEZE = "freeze"              # halt workflow, await resolution
ESCALATE = "escalate"          # hand to human with full evidence

DEFAULT_CHAINS: dict[str, list[str]] = {
    FailureClass.TRANSIENT.value: [RETRY, RETRY, SUBSTITUTE, ESCALATE],
    FailureClass.TOOL_UNAVAILABLE.value: [RETRY, SUBSTITUTE, ESCALATE],
    FailureClass.MALFORMED_OUTPUT.value: [REJECT, SUBSTITUTE, ESCALATE],
    FailureClass.STALE_DATA.value: [SUBSTITUTE, ESCALATE],
    FailureClass.PARTIAL_RESULT.value: [RETRY_REMAINDER, ROLLBACK, ESCALATE],
    FailureClass.CONFLICTING_RESULT.value: [FREEZE],
    FailureClass.AUTHENTICATION.value: [ESCALATE],
    FailureClass.AUTHORIZATION.value: [ESCALATE],
    FailureClass.INVALID_INPUT.value: [ESCALATE],
    FailureClass.UNKNOWN.value: [FREEZE, ESCALATE],
}


def next_action(failure_class: str, step: int,
                chains: dict[str, list[str]] | None = None,
                substitute_available: bool = True) -> str:
    """Return the permitted recovery action for this step of the chain.

    step is 0-indexed into the chain; past the end yields ESCALATE
    (chains are bounded — no infinite retry). If no in-scope substitute
    exists, SUBSTITUTE steps collapse to ESCALATE.
    """
    chain = (chains or DEFAULT_CHAINS).get(failure_class, [FREEZE, ESCALATE])
    action = chain[step] if step < len(chain) else ESCALATE
    if action == SUBSTITUTE and not substitute_available:
        return ESCALATE
    return action
