"""Tool executor: Envelope -> Authority Scope -> Capability -> Idempotency -> Tool.

LLM -> tool never means LLM -> arbitrary side effect. Recovery cannot
widen authority: the action's tool must be inside the ORIGINAL scope
granted at runtime registration, checked before any adapter is touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..core.capabilities import Capability
from ..core.envelopes import RecoveryEnvelope
from .idempotency import IdempotencyStore, idempotency_key
from .tools import get_tool, is_mutating_tool

if TYPE_CHECKING:
    from ..core.authority import AuthorityScope


class AuthorizationError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def execute_recovery(action: str, resource: str, capability: Capability,
                     envelope: RecoveryEnvelope, idem: IdempotencyStore,
                     adapters: dict, now: datetime | None = None,
                     scope: "AuthorityScope | None" = None) -> dict:
    now = now or datetime.now(timezone.utc)

    # 1. Envelope expiry
    if envelope.is_expired(now):
        raise AuthorizationError("ENVELOPE_EXPIRED")
    # 2. Policy / envelope permission
    if not envelope.action_permitted(action):
        raise AuthorizationError("ACTION_NOT_PERMITTED")
    # 3. Authority non-widening: recovery tool must be in original scope.
    if scope is not None and not scope.allows(action):
        raise AuthorizationError(
            f"AUTHORITY_WIDENING:{action} outside original scope")
    # 4. Capability validity
    ok, reason = capability.validate(action, resource, now)
    if not ok:
        raise AuthorizationError(reason)
    # 5. Idempotency — mutating actions only, so read-only recovery
    #    retries (retry/substitute fetches) can never trip DUPLICATE_ACTION.
    mutating = is_mutating_tool(action)
    key = idempotency_key(capability.exception_id, action, resource)
    if mutating and idem.already_executed(key):
        raise AuthorizationError("DUPLICATE_ACTION")
    # 6. Dispatch (only allowlisted tools reach here)
    if action == "replay_webhook":
        result = adapters["payments"].replay_webhook(resource)
    elif action == "sync_crm":
        result = adapters["crm"].sync_customer(resource)
    else:
        entry = get_tool(action)
        if entry is None:
            raise AuthorizationError("UNKNOWN_ACTION")
        try:
            raw = entry["handler"](resource, adapters)
        except Exception as e:
            raise AuthorizationError(f"TOOL_ERROR:{e}")
        if not isinstance(raw, dict):
            raise AuthorizationError("TOOL_MALFORMED_RESULT")
        if not entry["mutating"]:
            # Read-only recovery fetches pass through: the caller
            # classifies/verifies the outcome; a failing substitute
            # continues the chain instead of raising here.
            capability.consume()
            return {"ok": True, "idempotency_key": key, "result": raw}
        result = raw
    if not isinstance(result, dict) or not result.get("ok"):
        err = result.get("error", "EXECUTION_FAILED") if isinstance(result, dict) else "TOOL_MALFORMED_RESULT"
        raise AuthorizationError(err)
    # 7. Consume + record
    capability.consume()
    if mutating:
        idem.mark_executed(key, exception_id=capability.exception_id,
                           capability_id=capability.capability_id,
                           action_type=action)
    return {"ok": True, "idempotency_key": key, "result": result}
