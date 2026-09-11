"""Strands agent: investigate + propose through real tools; execution gated.

Strands is the intelligence layer; RECOURSE is the control plane around it.
Credential-free mode ("stub") keeps tests/gauntlet deterministic without
model calls. Live mode builds a real Agent with bound tools and the
RECOURSE hook provider — the model's proposals drive recovery, the gates
decide whether anything happens.
"""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import AgentCoordinator
from .hooks import RecourseHookProvider, SIDE_EFFECTING_TOOLS
from .prompts import RECONCILIATION_TASK_PROMPT, SYSTEM_PROMPT
from .tools import AGENT_TOOLS, bind_coordinator
from ..recovery.planner import plan_recovery


@dataclass
class InvestigationResult:
    evidence: dict
    diagnosis: str
    proposal: object


def stub_investigate(order_id: str, payment_id: str, customer_id: str,
                     webhook_id: str, exception_id: str,
                     orders, payments, crm, webhooks) -> InvestigationResult:
    o = orders.get_order(order_id) or {}
    p = payments.get_payment(payment_id) or {}
    c = crm.get_customer(customer_id) or {}
    wh = webhooks.get_webhook(webhook_id)
    missing = wh and not wh.get("delivered")
    diagnosis = ("payment webhook missing; payment succeeded but CRM never updated"
                 if missing else "unknown")
    proposal = plan_recovery(
        exception_id, "replay_webhook", webhook_id,
        "Replay missing payment.succeeded webhook to reconcile CRM.",
        ["order.status == paid", "payment.status == succeeded", "crm.balance == 0"],
    )
    return InvestigationResult(
        evidence={"order": o, "payment": p, "crm": c, "webhook_missing": missing},
        diagnosis=diagnosis, proposal=proposal)


def build_agent(model_provider: str = "stub", scope=None,
                coordinator: AgentCoordinator | None = None,
                model_id: str | None = None, region_name: str | None = None,
                **kwargs) -> dict:
    """Build a Strands agent or fall back to the deterministic stub.

    model_provider="stub" (default): no model calls; tests/gauntlet safe.
    Anything else: real Agent with bound tools + hook. Requires strands
    installed (it is, in .venv) and AWS credentials at INVOKE time —
    construction itself makes no network calls.
    """
    if model_provider == "stub":
        return {"mode": "stub", "system_prompt": SYSTEM_PROMPT}
    try:
        from strands import Agent
        from strands.models.bedrock import BedrockModel
    except Exception as e:
        return {"mode": "stub", "system_prompt": SYSTEM_PROMPT,
                "fallback_reason": f"strands unavailable: {e}"}
    from ..core.authority import AuthorityScope
    real_scope = scope if isinstance(scope, AuthorityScope) \
        else AuthorityScope.of(*(["fetch_primary", "fetch_alternate",
                                  "fetch_authoritative"] if scope is None else scope))
    if coordinator is not None:
        bind_coordinator(coordinator)
    provider = RecourseHookProvider(real_scope)
    model = BedrockModel(
        model_id=model_id or "us.anthropic.claude-sonnet-4-20250514-v1:0",
        **({"region_name": region_name} if region_name else {}),
        **kwargs,
    )
    agent = Agent(model=model, tools=list(AGENT_TOOLS),
                  system_prompt=SYSTEM_PROMPT, hooks=[provider])
    return {"mode": "strands", "agent": agent, "hook": provider,
            "tools": [getattr(t, "tool_name", getattr(t, "__name__", "?"))
                      for t in AGENT_TOOLS],
            "system_prompt": SYSTEM_PROMPT,
            "side_effecting_tools": sorted(SIDE_EFFECTING_TOOLS)}


def run_agent_reconciliation(agent, coordinator: AgentCoordinator,
                             items: list[str]) -> dict[str, dict]:
    """Drive items through the LIVE agent: per item, the model investigates
    with tools and proposes/triggers recovery; the coordinator gates and
    verifies. Returns item -> last outcome. Model decides WHAT to try."""
    outcomes: dict[str, dict] = {}
    for item_id in items:
        prompt = RECONCILIATION_TASK_PROMPT.format(item_id=item_id)
        try:
            agent(prompt)
        except Exception as e:
            outcomes[item_id] = {"ok": False, "error": f"AGENT_ERROR:{e}"}
            continue
        outcomes[item_id] = coordinator.last_outcome.get(
            item_id, {"ok": False, "error": "NO_RECOVERY_ATTEMPTED",
                      "detail": "agent inspected but never triggered recovery"})
    return outcomes
