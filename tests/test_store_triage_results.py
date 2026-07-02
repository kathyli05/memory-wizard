"""Tests for triage.store_triage_results — the retention policy is the
thing that actually matters here: reasoning text must not outlive the
14-day window, while urgency/suggest_nudge (fully derived signals) must
survive untouched."""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage.store_triage_results import RETENTION_DAYS, enforce_retention, upsert_results


def _read_row(db_path, thread_id):
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM triage_results WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def test_upsert_writes_all_fields(tmp_path):
    db_path = tmp_path / "triage.db"
    now = datetime.now().isoformat()
    upsert_results(db_path, [{
        "thread_id": 1,
        "thread_name": "+15551234567",
        "urgency": "high",
        "reasoning": "They asked a direct question 3 days ago with no reply.",
        "suggest_nudge": True,
        "computed_at": now,
    }])

    row = _read_row(db_path, 1)
    assert row["urgency"] == "high"
    assert row["reasoning"] == "They asked a direct question 3 days ago with no reply."
    assert row["suggest_nudge"] == 1
    assert row["computed_at"] == now


def test_retention_clears_reasoning_past_window_but_keeps_derived_signals(tmp_path):
    db_path = tmp_path / "triage.db"
    now = datetime.now()
    old_computed_at = (now - timedelta(days=RETENTION_DAYS + 1)).isoformat()

    upsert_results(db_path, [{
        "thread_id": 1,
        "thread_name": "+15551234567",
        "urgency": "high",
        "reasoning": "This text should be gone after retention runs.",
        "suggest_nudge": True,
        "computed_at": old_computed_at,
    }])

    scrubbed = enforce_retention(db_path, now=now)

    assert scrubbed == 1
    row = _read_row(db_path, 1)
    assert row["reasoning"] is None
    assert row["urgency"] == "high"
    assert row["suggest_nudge"] == 1
    assert row["computed_at"] == old_computed_at


def test_retention_leaves_recent_rows_untouched(tmp_path):
    db_path = tmp_path / "triage.db"
    now = datetime.now()
    recent_computed_at = (now - timedelta(days=1)).isoformat()

    upsert_results(db_path, [{
        "thread_id": 1,
        "thread_name": "+15551234567",
        "urgency": "low",
        "reasoning": "Recent — should survive retention.",
        "suggest_nudge": False,
        "computed_at": recent_computed_at,
    }])

    scrubbed = enforce_retention(db_path, now=now)

    assert scrubbed == 0
    row = _read_row(db_path, 1)
    assert row["reasoning"] == "Recent — should survive retention."
