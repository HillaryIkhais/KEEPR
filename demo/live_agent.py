"""Live Strands reconciliation — 3 invoices through a real model.

Requires AWS credentials with Bedrock access, e.g.:

  export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
  export AWS_REGION=us-east-1
  ./.venv/bin/python demo/live_agent.py

The model investigates with tools and proposes/trigger recovery; every
mutation passes the RECOURSE hook + coordinator gates. Deterministic
coverage of the same path lives in tests/test_strands.py (no creds).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from recourse.agent.agent import build_agent, run_agent_reconciliation
from recourse.agent.coordinator import AgentCoordinator
from recourse.agent.tools import bind_coordinator
from recourse.core.authority import AuthorityScope
from recourse.recovery.idempotency import IdempotencyStore
from recourse.workflows.run import new_run, run_envelope
from recourse.workloads.invoices import (
    AlternateSource,
    PrimaryAccounting,
    invoice_ids,
    ledger_amounts,
)


def main() -> int:
    ledger = ledger_amounts(3)
    ids = invoice_ids(3)
    # inv_002 fails once (transient), inv_003 is malformed at the primary.
    primary = PrimaryAccounting(ledger, faults={"inv_003": "malformed_amount"})
    used = {"n": 0}
    orig = primary.fetch

    def flaky(iid: str) -> dict:
        if iid == "inv_002" and used["n"] == 0:
            used["n"] += 1
            primary.calls.append(iid)
            from recourse.failures.schemas import now_iso
            from recourse.workloads.invoices import SOURCE_PRIMARY
            return {"ok": False, "error": "HTTP_503 SERVICE_UNAVAILABLE",
                    "tool": SOURCE_PRIMARY,
                    "meta": {"source": SOURCE_PRIMARY, "observed_at": now_iso()}}
        return orig(iid)

    scope = AuthorityScope.of("fetch_primary", "fetch_alternate")
    run = new_run("live_1", "live-invoice-reconciliation", ids, scope)
    run.transition_to("RUNNING")
    coord = AgentCoordinator(run=run,
                             adapters={"primary": primary,
                                       "alternate": AlternateSource(ledger)},
                             envelope=run_envelope("live_1", scope),
                             idem=IdempotencyStore(), expected=ledger,
                             scope=scope)
    built = build_agent("bedrock", scope=scope, coordinator=coord,
                        region_name=os.environ.get("AWS_REGION", "us-east-1"))
    if built["mode"] != "strands":
        print(f"agent fallback: {built.get('fallback_reason')}")
        return 2
    bind_coordinator(coord)
    print(f"tools: {built['tools']}\n")
    try:
        outcomes = run_agent_reconciliation(built["agent"], coord, ids)
    except Exception as e:
        if "credential" in str(e).lower() or "auth" in str(e).lower() \
                or "UnrecognizedClientException" in type(e).__name__:
            print("Bedrock credentials missing/invalid. Export AWS keys first.")
            return 2
        raise
    for iid, out in outcomes.items():
        print(f"{iid}: ok={out.get('ok')} err={out.get('error')}")
    print(f"\nproposals={len(coord.proposals)} executions={len(coord.executions)} "
          f"denials={len(built['hook'].denials)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
