"""Deterministic playbooks — what 'recovery' means per action."""
from __future__ import annotations

PLAYBOOKS: dict[str, dict] = {
    "replay_webhook": {
        "description": "Replay a missing payment.succeeded webhook to reconcile CRM.",
        "mutating": True,
        "required_postconditions": [
            "order.status == paid",
            "payment.status == succeeded",
            "crm.balance == 0",
        ],
    },
    "sync_crm": {
        "description": "Recompute CRM state from ground-truth order/payment state.",
        "mutating": True,
        "required_postconditions": [
            "order.status == paid",
            "payment.status == succeeded",
            "crm.balance == 0",
        ],
    },
    "inspect_order": {"description": "Read-only order inspection.", "mutating": False},
    "inspect_payment": {"description": "Read-only payment inspection.", "mutating": False},
    "inspect_crm": {"description": "Read-only CRM inspection.", "mutating": False},
    "inspect_webhook": {"description": "Read-only webhook history inspection.", "mutating": False},
}


def get_playbook(action: str) -> dict | None:
    return PLAYBOOKS.get(action)


def is_mutating(action: str) -> bool:
    pb = PLAYBOOKS.get(action)
    return bool(pb and pb.get("mutating"))
