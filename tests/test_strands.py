"""Strands layer: tools bound to a coordinator, proposal gating, hook cancel.

All credential-free: construction and gating never call a model. The live
model path is exercised by demo/live_agent.py (needs AWS credentials).
"""
import json

import pytest

from recourse.agent.agent import build_agent
from recourse.agent.coordinator import AgentCoordinator
from recourse.agent.hooks import RecourseHookProvider
from recourse.agent.tools import (
    AGENT_TOOLS,
    bind_coordinator,
    execute_authorized_recovery,
    inspect_invoice,
    propose_recovery,
    unbind_coordinator,
)
from recourse.core.authority import AuthorityScope
from recourse.recovery.idempotency import IdempotencyStore
from recourse.workflows.run import new_run, run_envelope
from recourse.workloads.invoices import (
    AlternateSource,
    PrimaryAccounting,
    ledger_amounts,
)


def _unwrap(res):
    """Normalize a @tool direct-call result to a plain dict."""
    if isinstance(res, dict) and ("ok" in res or "accepted" in res):
        return res
    content = (res.get("content") if isinstance(res, dict) else None) or []
    if content and isinstance(content[0], dict) and "text" in content[0]:
        try:
            return json.loads(content[0]["text"])
        except ValueError:
            return {"raw": content[0]["text"]}
    if isinstance(res, dict) and res.get("status") in ("success", "error"):
        return {"tool_status": res["status"], "content": content}
    return res


@pytest.fixture
def coord():
    ledger = ledger_amounts(5)
    scope = AuthorityScope.of("fetch_primary", "fetch_alternate")
    run = new_run("r_str", "t", [f"inv_{i:03d}" for i in range(1, 6)], scope)
    run.transition_to("RUNNING")
    c = AgentCoordinator(run=run,
                         adapters={"primary": PrimaryAccounting(ledger),
                                   "alternate": AlternateSource(ledger)},
                         envelope=run_envelope("r_str", scope),
                         idem=IdempotencyStore(), expected=ledger, scope=scope)
    bind_coordinator(c)
    yield c
    unbind_coordinator()


def test_inspect_tool_reads_primary(coord):
    res = _unwrap(inspect_invoice("inv_001"))
    assert res["ok"] is True and res["record"]["amount"] == ledger_amounts(5)["inv_001"]


def test_tools_require_binding():
    unbind_coordinator()
    with pytest.raises(RuntimeError):
        inspect_invoice("inv_001")


def test_propose_rejects_out_of_scope(coord):
    res = _unwrap(propose_recovery("inv_001", "request_payroll_access", "need it"))
    assert res["accepted"] is False
    assert res["reason"].startswith("AUTHORITY_WIDENING")
    assert ("inv_001", "request_payroll_access") not in coord.accepted


def test_execute_requires_proposal(coord):
    res = _unwrap(execute_authorized_recovery("inv_001", "fetch_alternate"))
    assert res["ok"] is False and res["error"] == "PROPOSAL_REQUIRED"


def test_propose_then_execute_verified(coord):
    assert _unwrap(propose_recovery("inv_001", "fetch_alternate", "verify backup"))["accepted"] is True
    res = _unwrap(execute_authorized_recovery("inv_001", "fetch_alternate"))
    assert res["ok"] is True, res
    # Proposal was single-use: immediate replay needs a fresh proposal.
    res2 = _unwrap(execute_authorized_recovery("inv_001", "fetch_alternate"))
    assert res2["error"] == "PROPOSAL_REQUIRED"


def test_hook_cancels_widening_before_tool_runs():
    provider = RecourseHookProvider(AuthorityScope.of("fetch_primary", "fetch_alternate"))

    class FakeEvent:
        def __init__(self, name, action):
            self.tool_use = {"name": name, "input": {"item_id": "inv_001", "action": action}}
            self.cancel_tool = False

    evil = FakeEvent("execute_authorized_recovery", "request_payroll_access")
    provider.on_before_tool_call(evil)
    assert evil.cancel_tool and "AUTHORITY_WIDENING" in str(evil.cancel_tool)
    assert len(provider.denials) == 1

    ok_event = FakeEvent("execute_authorized_recovery", "fetch_alternate")
    provider.on_before_tool_call(ok_event)
    assert ok_event.cancel_tool is False

    read_event = FakeEvent("inspect_invoice", "")
    provider.on_before_tool_call(read_event)
    assert read_event.cancel_tool is False


def test_build_agent_constructs_live_wiring_without_network():
    built = build_agent("bedrock", scope=["fetch_primary", "fetch_alternate"])
    assert built["mode"] == "strands"
    assert len(built["tools"]) == len(AGENT_TOOLS) == 6
    assert isinstance(built["hook"], RecourseHookProvider)
    assert built["agent"] is not None  # constructed; no model call made


def test_build_agent_stub_default():
    built = build_agent()
    assert built["mode"] == "stub"
