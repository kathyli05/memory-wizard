"""Persist triage results to ./data/triage.db, with the retention policy applied.

Per CLAUDE.md: raw message text is deleted from our local DB after the
retention period (default 14 days) — only derived signals persist past
that window. `reasoning` is the one field here that's derived from message
content (it can quote or paraphrase the messages it was computed from), so
enforce_retention clears it past the window; `urgency`/`suggest_nudge` are
already fully derived signals and are left alone.

Dashboard action state (status/snoozed_until) lives on this same row.
upsert_results always resets a thread to 'pending' — it's only ever called
for threads that are new or have a new message since last triaged (the
run_triage.py dedup logic), so "freshly triaged" and "needs attention
again" are the same event; dismiss/snooze naturally clear when that
happens without any extra plumbing.
"""

from __future__ import annotations

import os
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
    needs_review INTEGER NOT NULL DEFAULT 0,
    last_message_timestamp TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'dismissed', 'snoozed')),
    snoozed_until TEXT
);

CREATE TABLE IF NOT EXISTS triage_feedback (
    thread_id INTEGER NOT NULL,
    result_computed_at TEXT NOT NULL,
    model_urgency TEXT NOT NULL CHECK(model_urgency IN ('low', 'med', 'high')),
    urgency_correct INTEGER CHECK(urgency_correct IN (0, 1) OR urgency_correct IS NULL),
    corrected_urgency TEXT CHECK(corrected_urgency IN ('low', 'med', 'high') OR corrected_urgency IS NULL),
    reply_worthy INTEGER NOT NULL CHECK(reply_worthy IN (0, 1)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, result_computed_at),
    CHECK (
        (reply_worthy = 0 AND urgency_correct IS NULL AND corrected_urgency IS NULL)
        OR (reply_worthy = 1 AND urgency_correct = 1 AND corrected_urgency IS NULL)
        OR (reply_worthy = 1 AND urgency_correct = 0 AND corrected_urgency IS NOT NULL)
    )
);
"""

_UPSERT = """
INSERT INTO triage_results (
    thread_id, thread_name, urgency, reasoning, suggest_nudge, needs_review,
    last_message_timestamp, computed_at, status, snoozed_until
) VALUES (
    :thread_id, :thread_name, :urgency, :reasoning, :suggest_nudge, :needs_review,
    :last_message_timestamp, :computed_at, 'pending', NULL
)
ON CONFLICT(thread_id) DO UPDATE SET
    thread_name=excluded.thread_name,
    urgency=excluded.urgency,
    reasoning=excluded.reasoning,
    suggest_nudge=excluded.suggest_nudge,
    needs_review=excluded.needs_review,
    last_message_timestamp=excluded.last_message_timestamp,
    computed_at=excluded.computed_at,
    status='pending',
    snoozed_until=NULL
"""

_ACTIVE_RESULTS_QUERY = """
SELECT thread_id, thread_name, urgency, reasoning, suggest_nudge, needs_review,
       last_message_timestamp, computed_at, status, snoozed_until
FROM triage_results
WHERE status = 'pending'
ORDER BY CASE urgency WHEN 'high' THEN 0 WHEN 'med' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
         computed_at ASC
"""


def init_db(db_path: Path) -> None:
    db_path = Path(db_path)
    parent_existed = db_path.parent.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed:
        # owner-only when we created it (never tighten a pre-existing user dir)
        os.chmod(db_path.parent, 0o700)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(triage_results)")}
        if "needs_review" not in columns:
            conn.execute(
                "ALTER TABLE triage_results "
                "ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0"
            )
        conn.commit()
    finally:
        conn.close()


def upsert_results(db_path: Path, results: list[dict]) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            _UPSERT,
            [
                {
                    **r,
                    "suggest_nudge": int(r["suggest_nudge"]),
                    "needs_review": int(r.get("needs_review", False)),
                }
                for r in results
            ],
        )
        conn.commit()
    finally:
        conn.close()


def record_feedback(
    db_path: Path,
    *,
    thread_id: int,
    result_computed_at: str,
    model_urgency: str,
    urgency_correct: bool | None,
    corrected_urgency: str | None,
    reply_worthy: bool,
    created_at: datetime | None = None,
) -> None:
    """Store derived user feedback without names, reasoning, or message text."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO triage_feedback (
                thread_id, result_computed_at, model_urgency, urgency_correct,
                corrected_urgency, reply_worthy, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id, result_computed_at) DO UPDATE SET
                model_urgency=excluded.model_urgency,
                urgency_correct=excluded.urgency_correct,
                corrected_urgency=excluded.corrected_urgency,
                reply_worthy=excluded.reply_worthy,
                created_at=excluded.created_at
            """,
            (
                thread_id,
                result_computed_at,
                model_urgency,
                None if urgency_correct is None else int(urgency_correct),
                corrected_urgency,
                int(reply_worthy),
                (created_at or datetime.now()).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_feedback(db_path: Path) -> list[dict]:
    """Return derived feedback rows, oldest first, for local quality review."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM triage_feedback ORDER BY created_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_last_triaged_timestamps(db_path: Path) -> dict[int, str]:
    """thread_id -> last_message_timestamp of its most recent triage run.
    Empty dict if no results have been stored yet (including a fresh db)."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT thread_id, last_message_timestamp FROM triage_results"
        ).fetchall()
        return dict(rows)
    finally:
        conn.close()


def get_active_results(db_path: Path, *, now: datetime | None = None) -> list[dict]:
    """Results not dismissed and not currently snoozed, ordered by urgency
    (high -> med -> low) then oldest-computed first. Expires any snooze
    whose date has passed back to 'pending' first, so the stored status
    stays consistent rather than just being masked at query time."""
    now = now or datetime.now()
    now_iso = now.isoformat()

    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE triage_results SET status = 'pending', snoozed_until = NULL "
            "WHERE status = 'snoozed' AND snoozed_until <= ?",
            (now_iso,),
        )
        conn.commit()

        conn.row_factory = sqlite3.Row
        rows = conn.execute(_ACTIVE_RESULTS_QUERY).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def dismiss_result(db_path: Path, thread_id: int) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE triage_results SET status = 'dismissed', snoozed_until = NULL "
            "WHERE thread_id = ?",
            (thread_id,),
        )
        conn.commit()
    finally:
        conn.close()


def snooze_result(db_path: Path, thread_id: int, until: datetime) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE triage_results SET status = 'snoozed', snoozed_until = ? "
            "WHERE thread_id = ?",
            (until.isoformat(), thread_id),
        )
        conn.commit()
    finally:
        conn.close()


def enforce_retention(db_path: Path, *, now: datetime | None = None) -> int:
    """Null out `reasoning` on rows older than RETENTION_DAYS. Returns the
    number of rows scrubbed. Called by both triage runs and every dashboard
    load, so stale reasoning gets scrubbed even if triage stops running."""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=RETENTION_DAYS)).isoformat()

    init_db(db_path)
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
