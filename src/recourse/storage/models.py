"""Storage models (thin helpers over sqlite)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_exception(conn: sqlite3.Connection, case) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO exceptions(id,type,subject_id,severity,state,"
        "attempt_count,envelope_id,resolution_id) VALUES (?,?,?,?,?,?,?,?)",
        (case.id, case.type, case.subject_id, case.severity, case.state,
         case.attempt_count, case.envelope_id, case.resolution_id),
    )
    conn.commit()


def save_envelope(conn: sqlite3.Connection, env) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO recovery_envelopes(id,exception_id,allowed,"
        "forbidden,max_attempts,expires_at) VALUES (?,?,?,?,?,?)",
        (env.id, env.exception_id, json.dumps(env.allowed_actions),
         json.dumps(env.forbidden_actions), env.max_attempts,
         env.expires_at.isoformat()),
    )
    conn.commit()


def save_capability(conn: sqlite3.Connection, cap) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO capabilities(id,exception_id,action,resource,"
        "max_attempts,expires_at,status,used_count) VALUES (?,?,?,?,?,?,?,?)",
        (cap.capability_id, cap.exception_id, cap.action, cap.resource,
         cap.max_attempts, cap.expires_at.isoformat(), cap.status, cap.used_count),
    )
    conn.commit()


def record_transition(conn: sqlite3.Connection, exception_id: str,
                      frm: str, to: str, reason: str = "") -> None:
    conn.execute(
        "INSERT INTO state_transitions(exception_id,frm,to_state,at,reason)"
        " VALUES (?,?,?,?,?)",
        (exception_id, frm, to, _now(), reason),
    )
    conn.commit()


def record_verification(conn: sqlite3.Connection, run_id: str, exception_id: str,
                        action_id: str, expected: dict, observed: dict,
                        result: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO verification_runs(id,exception_id,action_id,"
        "expected_state,observed_state,result,timestamp)"
        " VALUES (?,?,?,?,?,?,?)",
        (run_id, exception_id, action_id, json.dumps(expected),
         json.dumps(observed), result, _now()),
    )
    conn.commit()


def record_escalation(conn: sqlite3.Connection, esc_id: str,
                      exception_id: str, reason: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO escalations(id,exception_id,reason,at)"
        " VALUES (?,?,?,?)",
        (esc_id, exception_id, reason, _now()),
    )
    conn.commit()


def save_failure(conn: sqlite3.Connection, failure) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO failures(id,workflow_id,item_id,tool,attempt,"
        "error,failure_class,recoverability,policy,observed_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (failure.id, failure.workflow_id, failure.item_id, failure.tool,
         failure.attempt, failure.error, failure.failure_class,
         failure.recoverability, failure.policy,
         failure.observed_at.isoformat()),
    )
    conn.commit()


def save_workflow_run(conn: sqlite3.Connection, run) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO workflow_runs(id,task,state,items,updated_at)"
        " VALUES (?,?,?,?,?)",
        (run.id, run.task, run.state, json.dumps(run.items), _now()),
    )
    conn.commit()
