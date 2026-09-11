"""Exception registry — the unit of recovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .states import ExceptionState
from .transitions import check_transition


@dataclass
class ExceptionCase:
    id: str
    type: str
    subject_id: str
    severity: str = "high"
    state: str = ExceptionState.DETECTED.value
    attempt_count: int = 0
    max_attempts: int = 3
    envelope_id: Optional[str] = None
    resolution_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition_to(self, to: str, reason: str = "") -> None:
        check_transition(self.state, to)
        self.state = to
        if to == "RECOVERY_PROPOSED":
            pass  # attempt counted at execution time
