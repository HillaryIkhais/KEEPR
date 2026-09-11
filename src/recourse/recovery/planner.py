"""Recovery planner — agent proposal -> authorized plan (no side effects here)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryProposal:
    exception_id: str
    action: str
    resource: str
    rationale: str
    expected_postconditions: list[str]


def plan_recovery(exception_id: str, action: str, resource: str,
                  rationale: str, expected: list[str]) -> RecoveryProposal:
    return RecoveryProposal(exception_id, action, resource, rationale, list(expected))
