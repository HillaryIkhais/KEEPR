"""Bounded, single-use, expiring capabilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .states import CapabilityStatus


@dataclass
class Capability:
    capability_id: str
    exception_id: str
    action: str
    resource: str
    max_attempts: int = 1
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = CapabilityStatus.ACTIVE.value
    used_count: int = 0

    def validate(self, action: str, resource: str, now: datetime | None = None) -> tuple[bool, str]:
        now = now or datetime.now(timezone.utc)
        if self.status == CapabilityStatus.CONSUMED.value:
            return False, "CAPABILITY_CONSUMED"
        if self.status == CapabilityStatus.REVOKED.value:
            return False, "CAPABILITY_REVOKED"
        if self.status == CapabilityStatus.EXPIRED.value or now > self.expires_at:
            self.status = CapabilityStatus.EXPIRED.value
            return False, "CAPABILITY_EXPIRED"
        if self.status not in (CapabilityStatus.ACTIVE.value, CapabilityStatus.ISSUED.value):
            return False, "CAPABILITY_NOT_ACTIVE"
        if self.used_count >= self.max_attempts:
            self.status = CapabilityStatus.CONSUMED.value
            return False, "CAPABILITY_CONSUMED"
        if action != self.action:
            return False, "ACTION_MISMATCH"
        if resource != self.resource:
            return False, "RESOURCE_MISMATCH"
        return True, "OK"

    def consume(self) -> None:
        self.used_count += 1
        if self.used_count >= self.max_attempts:
            self.status = CapabilityStatus.CONSUMED.value
