"""SQLite persistence — complete audit trail."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS exceptions(
  id TEXT PRIMARY KEY, type TEXT, subject_id TEXT, severity TEXT,
  state TEXT, attempt_count INTEGER, envelope_id TEXT, resolution_id TEXT);
CREATE TABLE IF NOT EXISTS recovery_envelopes(
  id TEXT PRIMARY KEY, exception_id TEXT, allowed TEXT, forbidden TEXT,
  max_attempts INTEGER, expires_at TEXT);
CREATE TABLE IF NOT EXISTS capabilities(
  id TEXT PRIMARY KEY, exception_id TEXT, action TEXT, resource TEXT,
  max_attempts INTEGER, expires_at TEXT, status TEXT, used_count INTEGER);
CREATE TABLE IF NOT EXISTS evidence(
  id TEXT PRIMARY KEY, exception_id TEXT, source TEXT, query TEXT,
  value TEXT, observed_at TEXT);
CREATE TABLE IF NOT EXISTS actions(
  id TEXT PRIMARY KEY, exception_id TEXT, capability_id TEXT, action_type TEXT,
  requested_at TEXT, authorized_at TEXT, executed_at TEXT, result TEXT,
  idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS verification_runs(
  id TEXT PRIMARY KEY, exception_id TEXT, action_id TEXT,
  expected_state TEXT, observed_state TEXT, result TEXT, timestamp TEXT);
CREATE TABLE IF NOT EXISTS state_transitions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, exception_id TEXT, frm TEXT,
  to_state TEXT, at TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS escalations(
  id TEXT PRIMARY KEY, exception_id TEXT, reason TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS failures(
  id TEXT PRIMARY KEY, workflow_id TEXT, item_id TEXT, tool TEXT,
  attempt INTEGER, error TEXT, failure_class TEXT, recoverability TEXT,
  policy TEXT, observed_at TEXT);
CREATE TABLE IF NOT EXISTS workflow_runs(
  id TEXT PRIMARY KEY, task TEXT, state TEXT, items TEXT, updated_at TEXT);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    p = path or os.environ.get("RECOURSE_DB_PATH", "./recourse.db")
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    return conn
