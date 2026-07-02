"""Persist triage results to ./data/triage.db, with the retention policy applied.

Per CLAUDE.md: raw message text is deleted from our local DB after the
retention period (default 14 days) — only derived signals persist past
that window. `reasoning` is the one field here that's derived from message
content (it can quote or paraphrase the messages it was computed from), so
enforce_retention clears it past the window; `urgency`/`suggest_nudge` are
already fully derived signals and are left alone.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

RETENTION_DAYS = 14

SCHEMA = """
CREATE TABLE IF NOT EXISTS triage_results (
    thread_id INTEGER PRIMARY KEY,
    thread_name TEXT,
    urgency TEXT NOT NULL,
    reasoning TEXT,
    suggest_nudge INTEGER NOT NULL,
    computed_at TEXT NOT NULL
);
"""

_UPSERT = """
INSERT INTO triage_results (
    thread_id, thread_name, urgency, reasoning, suggest_nudge, computed_at
) VALUES (
    :thread_id, :thread_name, :urgency, :reasoning, :suggest_nudge, :computed_at
)
ON CONFLICT(thread_id) DO UPDATE SET
    thread_name=excluded.thread_name,
    urgency=excluded.urgency,
    reasoning=excluded.reasoning,
    suggest_nudge=excluded.suggest_nudge,
    computed_at=excluded.computed_at
"""


def init_db(db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_results(db_path: Path, results: list[dict]) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            _UPSERT,
            [{**r, "suggest_nudge": int(r["suggest_nudge"])} for r in results],
        )
        conn.commit()
    finally:
        conn.close()


def enforce_retention(db_path: Path, *, now: datetime | None = None) -> int:
    """Null out `reasoning` on rows older than RETENTION_DAYS. Returns the
    number of rows scrubbed."""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=RETENTION_DAYS)).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE triage_results SET reasoning = NULL "
            "WHERE computed_at < ? AND reasoning IS NOT NULL",
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
