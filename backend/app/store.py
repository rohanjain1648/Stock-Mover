"""SQLite state: runs, decisions, alerts_sent, notif_log.

One short-lived connection per call (safe across the request threadpool, the scheduler
thread and the background engine thread); writes are serialised with a lock.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_DB: Path | None = None
_WRITE = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    generated_at TEXT,
    trigger TEXT,
    n_groups INTEGER,
    passed INTEGER NOT NULL,
    stored_at TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    run_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    note TEXT,
    decided_by TEXT,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (run_id, group_id)
);
CREATE TABLE IF NOT EXISTS alerts_sent (
    am_id TEXT NOT NULL,
    week TEXT NOT NULL,
    group_id TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (am_id, week, group_id)
);
CREATE TABLE IF NOT EXISTS notif_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    recipient TEXT,
    subject TEXT,
    ok INTEGER NOT NULL,
    reason TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(path) -> None:
    global _DB
    _DB = Path(path)
    _DB.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript(_SCHEMA)


@contextmanager
def _conn():
    if _DB is None:
        raise RuntimeError("store.init_db() not called")
    c = sqlite3.connect(_DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def save_run(run: dict) -> None:
    passed = bool(run.get("validation", {}).get("passed"))
    with _WRITE, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO runs (run_id, generated_at, trigger, n_groups, passed, stored_at, body) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run["run_id"], run.get("generated_at"), run.get("trigger"),
             len(run.get("groups", [])), int(passed), _now(), json.dumps(run, ensure_ascii=False)))


def latest_run() -> dict | None:
    """Newest run whose validation passed (a failed run is history only, never live)."""
    with _conn() as c:
        row = c.execute("SELECT body FROM runs WHERE passed = 1 "
                        "ORDER BY generated_at DESC, rowid DESC LIMIT 1").fetchone()
    return json.loads(row["body"]) if row else None


def list_runs() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT run_id, generated_at, trigger, n_groups, passed FROM runs "
                         "ORDER BY generated_at DESC, rowid DESC").fetchall()
    return [{**dict(r), "passed": bool(r["passed"])} for r in rows]


def set_decision(run_id: str, group_id: str, decision: str, note: str | None, by: str | None) -> None:
    with _WRITE, _conn() as c:
        c.execute("INSERT OR REPLACE INTO decisions (run_id, group_id, decision, note, decided_by, decided_at) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (run_id, group_id, decision, note, by, _now()))


def decisions(run_id: str) -> dict[str, dict]:
    with _conn() as c:
        rows = c.execute("SELECT group_id, decision, note, decided_by, decided_at FROM decisions "
                         "WHERE run_id = ?", (run_id,)).fetchall()
    return {r["group_id"]: {"decision": r["decision"], "note": r["note"], "by": r["decided_by"],
                            "at": r["decided_at"]} for r in rows}


def alerts_sent_count(am_id: str, week: str) -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM alerts_sent WHERE am_id = ? AND week = ?",
                         (am_id, week)).fetchone()[0]


def record_alert(am_id: str, week: str, group_id: str) -> None:
    with _WRITE, _conn() as c:
        c.execute("INSERT OR IGNORE INTO alerts_sent (am_id, week, group_id, sent_at) VALUES (?, ?, ?, ?)",
                  (am_id, week, group_id, _now()))


def log_notification(channel: str, to: str, subject: str, ok: bool, reason: str | None = None) -> None:
    with _WRITE, _conn() as c:
        c.execute("INSERT INTO notif_log (sent_at, channel, recipient, subject, ok, reason) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (_now(), channel, to, subject, int(bool(ok)), reason))


def notification_log() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT sent_at, channel, recipient, subject, ok, reason FROM notif_log "
                         "ORDER BY id DESC LIMIT 200").fetchall()
    return [{"sent_at": r["sent_at"], "channel": r["channel"], "to": r["recipient"], "subject": r["subject"],
             "ok": bool(r["ok"]), "reason": r["reason"]} for r in rows]
