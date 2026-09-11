"""Policy engine — maps exception type -> recovery envelope.

The LLM never writes its own permissions. Policy does.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .envelopes import RecoveryEnvelope


POLICY_TABLE: dict[str, dict] = {
    "payment_webhook_failed": {
        "allowed": ["inspect_order", "inspect_payment", "inspect_webhook",
                    "inspect_crm", "replay_webhook", "sync_crm"],
        "forbidden": ["refund_payment", "modify_payment", "rewrite_transaction",
                      "modify_payment_amount"],
        "required_evidence": ["payment_exists", "payment_succeeded", "order_exists"],
        "required_postconditions": [
            "order.status == paid",
            "payment.status == succeeded",
            "crm.balance == 0",
        ],
    },
    "ambiguous_financial_state": {
        "allowed": ["inspect_order", "inspect_payment", "inspect_crm"],
        "forbidden": ["refund_payment", "modify_payment", "rewrite_transaction",
                      "modify_payment_amount", "replay_webhook", "sync_crm"],
        "required_evidence": ["payment_exists", "order_exists"],
        "required_postconditions": [],
    },
}

DEFAULT_POLICY = {
    "allowed": ["inspect_order", "inspect_payment", "inspect_crm", "inspect_webhook"],
    "forbidden": ["refund_payment", "modify_payment", "rewrite_transaction",
                  "modify_payment_amount"],
    "required_evidence": [],
    "required_postconditions": [],
}


def envelope_for_exception(exception_id: str, exc_type: str,
                           ttl_minutes: int = 30,
                           max_attempts: int = 3) -> RecoveryEnvelope:
    pol = POLICY_TABLE.get(exc_type, DEFAULT_POLICY)
    now = datetime.now(timezone.utc)
    return RecoveryEnvelope(
        id=f"env_{exception_id}",
        exception_id=exception_id,
        allowed_actions=list(pol["allowed"]),
        forbidden_actions=list(pol["forbidden"]),
        max_attempts=max_attempts,
        expires_at=now + timedelta(minutes=ttl_minutes),
        required_evidence=list(pol["required_evidence"]),
        required_postconditions=list(pol["required_postconditions"]),
    )
