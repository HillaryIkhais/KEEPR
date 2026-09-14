"""KEEPR SDK — the adoptable surface.

Two entry points:

  runtime = RecoveryRuntime(scope={...},
                            policies=[Retry(2), Substitute(), Escalate()])
  run = runtime.run_items(items, fetch_primary=..., fetch_alternate=...,
                          expected=..., task="invoice-reconciliation")

  @recoverable(on_transient="retry", on_malformed="substitute",
               alternate=fetch_backup, alternate_name="fetch_backup",
               scope={"fetch_primary", "fetch_backup"}, verify=check,
               schema=True)
  def fetch_invoice(iid): ...

Policies select the recovery CHAIN per failure class; the authority scope
is fixed at registration and can only narrow. The decorator loop is
bounded: at most max_attempts primary calls plus one substitute, then
RecoveryEscalated.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from .core.authority import AuthorityScope
from .failures.classifier import classify
from .failures.selector import DEFAULT_CHAINS
from .failures.taxonomy import RECOVERABILITY, Failure, FailureClass
from .recovery.idempotency import IdempotencyStore
from .workflows.run import new_run, reconcile_all, run_envelope
from .workloads import invoices as _invoices  # noqa: F401 (registers fetch_* tools)


# ---------------------------------------------------------------- policies

@dataclass
class Retry:
    max_attempts: int = 2


@dataclass
class Substitute:
    pass


@dataclass
class Rollback:
    pass


@dataclass
class Escalate:
    pass


@dataclass
class Freeze:
    pass


RECOVERABLE_CLASSES = {
    FailureClass.TRANSIENT.value,
    FailureClass.TOOL_UNAVAILABLE.value,
    FailureClass.MALFORMED_OUTPUT.value,
    FailureClass.STALE_DATA.value,
    FailureClass.PARTIAL_RESULT.value,
}


def chains_for(policies: list) -> dict[str, list[str]]:
    """Derive bounded per-class chains from the declared policy set.

    Absent Retry drops retry steps; absent Substitute collapses substitute
    to escalate (mirroring the scope rule); present Rollback inserts a
    rollback before the terminal escalate of recoverable classes.
    """
    kinds = {type(p).__name__ for p in policies}
    retry_n = next((p.max_attempts for p in policies if isinstance(p, Retry)), 0)
    out: dict[str, list[str]] = {}
    for klass, chain in DEFAULT_CHAINS.items():
        steps: list[str] = []
        retries_used = 0
        for s in chain:
            if s in ("retry", "retry_remainder"):
                if retries_used < retry_n:
                    steps.append(s)
                    retries_used += 1
            elif s == "substitute" and "Substitute" not in kinds:
                steps.append("escalate")
            else:
                steps.append(s)
        if "Rollback" in kinds and klass in RECOVERABLE_CLASSES:
            if steps and steps[-1] == "escalate":
                steps = steps[:-1] + ["rollback", "escalate"]
        # Collapse consecutive duplicates (e.g. substitute->escalate next
        # to the chain's own terminal escalate).
        deduped: list[str] = []
        for s in steps:
            if not deduped or deduped[-1] != s or s in ("retry", "retry_remainder"):
                deduped.append(s)
        out[klass] = deduped or ["escalate"]
    return out


class _FnAdapter:
    """Adapt a plain fetch callable to the source interface."""

    def __init__(self, fn: Callable[[str], dict]):
        self.fn = fn

    def fetch(self, resource: str) -> dict:
        return self.fn(resource)


class RecoveryRuntime:
    """Recovery-governed runner. Scope fixed at registration; never widens."""

    def __init__(self, scope, policies: list | None = None,
                 max_age_seconds: float = 3600.0, max_attempts: int = 3):
        if isinstance(scope, AuthorityScope):
            self.scope = scope
        else:
            self.scope = AuthorityScope.of(*scope)
        self.policies = policies if policies is not None else [
            Retry(2), Substitute(), Escalate()]
        self.chains = chains_for(self.policies)
        self.max_age_seconds = max_age_seconds
        self.max_attempts = max_attempts

    def run_items(self, items: list[str], *, fetch_primary,
                  fetch_alternate=None, fetch_authoritative=None,
                  expected: dict[str, int], task: str = "reconciliation",
                  run_id: str = "run_1"):
        adapters: dict[str, Any] = {"primary": _FnAdapter(fetch_primary)}
        if fetch_alternate is not None:
            adapters["alternate"] = _FnAdapter(fetch_alternate)
        if fetch_authoritative is not None:
            adapters["authoritative"] = _FnAdapter(fetch_authoritative)
        run = new_run(run_id, task, items, self.scope)
        envelope = run_envelope(run_id, self.scope, self.max_attempts)
        return reconcile_all(run, adapters, envelope, expected,
                             chains=self.chains,
                             max_age_seconds=self.max_age_seconds,
                             idem=IdempotencyStore())


# ------------------------------------------------------------- decorator

class RecoveryEscalated(Exception):
    def __init__(self, reason: str, failure: Failure | None = None):
        super().__init__(reason)
        self.reason = reason
        self.failure = failure


def _strategy_for(failure_class: str, *, on_transient: str, on_malformed: str,
                  on_conflict: str, on_auth: str, on_unknown: str) -> str:
    if failure_class in (FailureClass.TRANSIENT.value,
                         FailureClass.TOOL_UNAVAILABLE.value,
                         FailureClass.PARTIAL_RESULT.value):
        return on_transient
    if failure_class in (FailureClass.MALFORMED_OUTPUT.value,
                         FailureClass.STALE_DATA.value,
                         FailureClass.INVALID_INPUT.value):
        return on_malformed
    if failure_class == FailureClass.CONFLICTING_RESULT.value:
        return on_conflict
    if failure_class in (FailureClass.AUTHENTICATION.value,
                         FailureClass.AUTHORIZATION.value):
        return on_auth
    return on_unknown


def recoverable(*, on_transient: str = "retry", on_malformed: str = "substitute",
                on_conflict: str = "freeze", on_auth: str = "escalate",
                on_unknown: str = "freeze", max_attempts: int = 2,
                alternate: Callable | None = None,
                alternate_name: str = "alternate",
                scope: set[str] | AuthorityScope | None = None,
                verify: Callable[[dict], bool] | None = None,
                schema: bool = False,
                max_age_seconds: float = 3600.0):
    """Govern one fallible function with classify -> recover -> verify."""
    if isinstance(scope, AuthorityScope):
        scope_tools = set(scope.tools)
    else:
        scope_tools = set(scope or [])

    def deco(fn: Callable):
        fn_name = getattr(fn, "__name__", "fn")

        @wraps(fn)
        def wrapper(*args, **kwargs):
            calls = 0
            substituted = False
            outcome = fn(*args, **kwargs)
            calls += 1
            failure = classify(outcome, tool=fn_name, attempt=calls,
                               expected_schema=schema,
                               max_age_seconds=max_age_seconds)
            guard = 0
            while failure is not None:
                guard += 1
                if guard > max_attempts + 3:
                    raise RecoveryEscalated(
                        f"RECOVERY_BOUND_EXCEEDED:{failure.failure_class}", failure)
                strategy = _strategy_for(
                    failure.failure_class, on_transient=on_transient,
                    on_malformed=on_malformed, on_conflict=on_conflict,
                    on_auth=on_auth, on_unknown=on_unknown)
                if strategy == "retry":
                    if calls >= max_attempts:
                        raise RecoveryEscalated(
                            f"RETRY_EXHAUSTED:{failure.failure_class}", failure)
                    outcome = fn(*args, **kwargs)
                    calls += 1
                elif strategy == "substitute":
                    if substituted or alternate is None \
                            or alternate_name not in scope_tools:
                        raise RecoveryEscalated(
                            f"AUTHORITY_WIDENING:{alternate_name} outside scope"
                            if alternate_name not in scope_tools
                            else f"SUBSTITUTE_EXHAUSTED:{failure.failure_class}",
                            failure)
                    outcome = alternate(*args, **kwargs)
                    substituted = True
                elif strategy in ("freeze", "escalate"):
                    raise RecoveryEscalated(
                        f"{strategy.upper()}:{failure.failure_class}", failure)
                else:
                    raise RecoveryEscalated(
                        f"UNKNOWN_STRATEGY:{strategy}", failure)
                failure = classify(outcome, tool=fn_name, attempt=calls + 1,
                                   expected_schema=schema,
                                   max_age_seconds=max_age_seconds)
                if failure is None and verify is not None \
                        and not verify(outcome):
                    failure = Failure(
                        id="F-verify", workflow_id="", item_id="",
                        tool=fn_name, attempt=calls + 1,
                        error="VERIFY_FAILED",
                        failure_class=FailureClass.MALFORMED_OUTPUT.value,
                        recoverability=RECOVERABILITY[
                            FailureClass.MALFORMED_OUTPUT.value])
            if verify is not None and not verify(outcome):
                raise RecoveryEscalated("VERIFY_FAILED", None)
            if isinstance(outcome, dict) and "data" in outcome:
                return outcome["data"]
            return outcome

        return wrapper
    return deco
