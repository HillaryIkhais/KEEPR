"""Authority scopes — RECOVERY CANNOT WIDEN AUTHORITY.

A scope is the set of tools granted when the runtime was registered.
Every recovery action is checked against the ORIGINAL scope: a substitute
source, rollback handler, or any other tool outside it is rejected with
AUTHORITY_WIDENING before any capability, adapter, or side effect.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorityScope:
    tools: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def of(cls, *tools: str) -> "AuthorityScope":
        return cls(frozenset(tools))

    def allows(self, tool: str) -> bool:
        return tool in self.tools

    def check_narrowing(self, requested: "AuthorityScope") -> tuple[bool, str]:
        """Requested recovery authority must be ⊆ original authority."""
        extra = set(requested.tools) - set(self.tools)
        if extra:
            return False, f"AUTHORITY_WIDENING: {sorted(extra)} outside original scope"
        return True, "OK"
