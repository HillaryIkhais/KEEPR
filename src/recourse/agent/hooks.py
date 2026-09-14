"""Strands BeforeToolCall hook: side-effecting tools require KEEPR auth.

Agent attempts forbidden action -> hook -> scope check -> CANCELLED
before the tool body ever runs. The coordinator re-enforces the same
rule at execution (defense in depth).
"""
from __future__ import annotations

from ..core.authority import AuthorityScope

SIDE_EFFECTING_TOOLS = {"replay_webhook", "sync_crm", "refund_payment",
                        "modify_payment", "modify_payment_amount",
                        "rewrite_transaction",
                        "execute_authorized_recovery"}

# Tools the agent may invoke that route into the recovery control plane.
# The hook checks the requested ACTION inside the tool input, not just
# the tool name: execute_authorized_recovery(fetch_alternate) is fine,
# execute_authorized_recovery(request_payroll_access) is cancelled.
MUTATING_AGENT_TOOLS = {"execute_authorized_recovery"}


def recourse_before_tool_call(tool_name: str, tool_input: dict,
                              authorize_fn) -> dict:
    """Return {'allow': bool, 'reason': str}. authorize_fn(tool_name, tool_input)->(bool,str)."""
    if tool_name not in SIDE_EFFECTING_TOOLS:
        return {"allow": True, "reason": "READ_ONLY"}
    ok, reason = authorize_fn(tool_name, tool_input)
    return {"allow": ok, "reason": reason}


def strands_hook_adapter(agent_context, **kwargs):
    """Legacy dict-style adapter (kept for backward compatibility)."""
    tool_name = kwargs.get("tool_name", "")
    tool_input = kwargs.get("tool_input", {})
    auth = getattr(agent_context, "recourse_authorize", None)
    if auth is None:
        return {"cancel": tool_name in SIDE_EFFECTING_TOOLS,
                "reason": "NO_AUTHORIZER"}
    res = recourse_before_tool_call(tool_name, tool_input, auth)
    return {"cancel": not res["allow"], "reason": res["reason"]}


def scope_authorizer(scope: AuthorityScope):
    """Build an authorize_fn that enforces the original authority scope."""

    def authorize(tool_name: str, tool_input: dict) -> tuple[bool, str]:
        if tool_name in MUTATING_AGENT_TOOLS:
            action = (tool_input or {}).get("action", "")
            if not scope.allows(action or tool_name):
                return False, f"AUTHORITY_WIDENING:{action} outside original scope"
            return True, "IN_SCOPE"
        if tool_name in SIDE_EFFECTING_TOOLS:
            return False, f"FORBIDDEN_TOOL:{tool_name}"
        return True, "READ_ONLY"

    return authorize


class RecourseHookProvider:
    """Real Strands hook provider. Register via Agent(hooks=[...]).

    Cancels out-of-scope recovery execution before the tool body runs.
    """

    def __init__(self, scope: AuthorityScope):
        self.scope = scope
        self.authorize = scope_authorizer(scope)
        self.denials: list[dict] = []

    def register_hooks(self, registry) -> None:
        try:
            from strands.hooks.events import BeforeToolCallEvent
        except Exception:
            return  # strands unavailable: provider stays inert
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool_call)

    def on_before_tool_call(self, event) -> None:
        use = getattr(event, "tool_use", None)
        if isinstance(use, dict):
            name, tool_input = use.get("name", ""), use.get("input", {}) or {}
        else:
            name = getattr(use, "name", "")
            tool_input = getattr(use, "input", {}) or {}
        res = recourse_before_tool_call(name, tool_input, self.authorize)
        if not res["allow"]:
            self.denials.append({"tool": name, "input": tool_input,
                                 "reason": res["reason"]})
            try:
                event.cancel_tool = res["reason"]
            except Exception:
                pass
