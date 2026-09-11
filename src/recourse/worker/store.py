"""Worker state persistence — survives kill/restart for the resume demo."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

_DB_PATH: str | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH or "recourse.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS worker_jobs (
            job_id    TEXT PRIMARY KEY,
            status    TEXT NOT NULL DEFAULT 'PENDING',
            total     INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS worker_invoices (
            job_id   TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            status   TEXT NOT NULL DEFAULT 'PENDING',
            attempts INTEGER NOT NULL DEFAULT 0,
            recovery_mode TEXT,
            lifecycle_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (job_id, invoice_id)
        );
    """)
    conn.commit()


def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path


def save_job(job_id: str, status: str, total: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    conn.execute("""
        INSERT INTO worker_jobs (job_id, status, total, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,
                                         updated_at=excluded.updated_at
    """, (job_id, status, total, now, now))
    conn.commit()
    conn.close()


def save_invoice(job_id: str, invoice_id: str, status: str,
                 attempts: int = 0, recovery_mode: str | None = None,
                 lifecycle: list[dict] | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    conn.execute("""
        INSERT INTO worker_invoices
            (job_id, invoice_id, status, attempts, recovery_mode,
             lifecycle_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, invoice_id) DO UPDATE SET
            status=excluded.status, attempts=excluded.attempts,
            recovery_mode=excluded.recovery_mode,
            lifecycle_json=excluded.lifecycle_json,
            updated_at=excluded.updated_at
    """, (job_id, invoice_id, status, attempts, recovery_mode,
          json.dumps(lifecycle or []), now, now))
    conn.commit()
    conn.close()


def load_invoices(job_id: str) -> dict[str, dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM worker_invoices WHERE job_id=?",
        (job_id,)).fetchall()
    conn.close()
    return {r["invoice_id"]: {
        "status": r["status"],
        "attempts": r["attempts"],
        "recovery_mode": r["recovery_mode"],
        "lifecycle": json.loads(r["lifecycle_json"] or "[]"),
    } for r in rows}


def load_job(job_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM worker_jobs WHERE job_id=?",
        (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {"job_id": row["job_id"], "status": row["status"],
            "total": row["total"]}


def reset_job(job_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM worker_invoices WHERE job_id=?", (job_id,))
    conn.execute("DELETE FROM worker_jobs WHERE job_id=?", (job_id,))
    conn.commit()
    conn.close()
