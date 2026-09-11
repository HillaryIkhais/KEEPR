"""Seed the canonical mock world (and optional SQLite audit DB)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from recourse.adapters.world import MockWorld
from recourse.core.exceptions import ExceptionCase
from recourse.core.policies import envelope_for_exception
from recourse.storage.database import connect
from recourse.storage.models import save_envelope, save_exception


def main() -> None:
    world = MockWorld.canonical_missing_webhook()
    case = ExceptionCase(id="exc_1842", type="payment_webhook_failed",
                         subject_id="order_1842")
    env = envelope_for_exception("exc_1842", "payment_webhook_failed")
    case.envelope_id = env.id
    print("ORDER   order_1842  $500 / paid")
    print("PAYMENT pay_5001    $500 / succeeded")
    print("CRM     customer_91 $500 / unreconciled  (webhook wh_9231 missing)")
    print(f"EXCEPTION {case.id}  state={case.state}  envelope={env.id}")
    print(f"  allowed:   {env.allowed_actions}")
    print(f"  forbidden: {env.forbidden_actions}")
    try:
        conn = connect()
        save_exception(conn, case)
        save_envelope(conn, env)
        conn.close()
        print("seeded sqlite audit db")
    except Exception as e:
        print(f"(sqlite seed skipped: {e})")


if __name__ == "__main__":
    main()
