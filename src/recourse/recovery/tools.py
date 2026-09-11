"""Tool registry — workloads register recovery tools with mutability flags.

Idempotency only constrains MUTATING actions: retries of read-only
recovery fetches must never trip DUPLICATE_ACTION.
"""
from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, dict] = {}


def register_tool(name: str, handler: Callable[..., dict],
                  mutating: bool = True) -> None:
    _REGISTRY[name] = {"handler": handler, "mutating": mutating}


def get_tool(name: str) -> dict | None:
    return _REGISTRY.get(name)


def is_mutating_tool(name: str) -> bool:
    entry = _REGISTRY.get(name)
    if entry is None:
        return True  # unknown tools default to the safe side
    return bool(entry["mutating"])


def registered_tools() -> list[str]:
    return sorted(_REGISTRY)
