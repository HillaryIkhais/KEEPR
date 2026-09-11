"""Agent coordinator — the agent's hands, not its authority.

The Strands agent investigates (inspect_*), proposes (propose_recovery),
and triggers (execute_authorized_recovery). Every trigger enforces:

  propose-before-execute  (no proposal -> PROPOSAL_REQUIRED)
  single-use proposals    (replay without re-proposal is blocked)
  scope gating            (proposal AND execution check original scope)
  capability execution    (via workflows.authorized_call -> executor)

The model decides WHAT to try. It controls none of the gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.authority import AuthorityScope
from ..core.envelopes import RecoveryEnvelope
from ..failures.classifier import classify
from ..recovery.idempotency import IdempotencyStore
from ..verification.observations import verify_observation
from ..workflows import run as wf
from ..workloads.invoices import TRUSTED_SOURCES


@dataclass
class AgentCoordinator:
    run: Any  # WorkflowRun (loose to avoid import weight here)
    adapters: dict
    envelope: RecoveryEnvelope
    idem: IdempotencyStore
    expected: dict[str, int]
    scope: AuthorityScope
    max_age_seconds: float = 3600.0
    proposals: list[dict] = field(default_factory=list)
    accepted: set[tuple[str, str]] = field(default_factory=set)
    executions: list[dict] = field(default_factory=list)
    last_outcome: dict[str, dict] = field(default_factory=dict)

    # -- proposal ------------------------------------------------------
    def propose(self, item_id: str, action: str, rationale: str) -> dict:
        if action not in self.scope.tools:
            return {"accepted": False,
                    "reason": f"AUTHORITY_WIDENING:{action} outside original scope"}
        if not self.envelope.action_permitted(action):
            return {"accepted": False, "reason": "ACTION_NOT_PERMITTED"}
        self.proposals.append({"item_id": item_id, "action": action,
                               "rationale": rationale})
        self.accepted.add((item_id, action))
        return {"accepted": True, "item_id": item_id, "action": action,
                "note": "proposal recorded; execution still requires authorization"}

    # -- authorized execution ------------------------------------------
    def recover(self, item_id: str, action: str) -> dict:
        if (item_id, action) not in self.accepted:
            return {"ok": False, "error": "PROPOSAL_REQUIRED",
                    "detail": "propose_recovery must accept this action first"}
        self.accepted.discard((item_id, action))  # single-use
        outcome = wf.authorized_call(self.run, action, item_id, self.envelope,
                                     self.idem, self.adapters)
        self.executions.append({"item_id": item_id, "action": action})
        if str(outcome.get("error", "")).startswith("RECOVERY_BLOCKED:"):
            result = {"ok": False, "error": outcome["error"]}
            self.last_outcome[item_id] = result
            return result
        failure = classify(outcome, workflow_id=getattr(self.run, "id", ""),
                           item_id=item_id, tool=action,
                           attempt=len(self.executions) + 1,
                           expected_schema=True,
                           max_age_seconds=self.max_age_seconds)
        if failure is not None:
            result = {"ok": False, "error": failure.failure_class,
                      "recoverability": failure.recoverability,
                      "detail": failure.error}
            self.last_outcome[item_id] = result
            return result
        data, meta = outcome.get("data"), outcome.get("meta") or {}
        verdict = verify_observation(
            data, source=meta.get("source", "?"),
            expected_sources=TRUSTED_SOURCES,
            expected_amount=self.expected.get(item_id),
            max_age_seconds=self.max_age_seconds)
        result = {"ok": verdict.passed,
                  "error": None if verdict.passed else ";".join(verdict.problems),
                  "observed": verdict.observed}
        self.last_outcome[item_id] = result
        return result
