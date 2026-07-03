"""Tests for triage.store_triage_results — the retention policy is the
thing that actually matters here: reasoning text must not outlive the
14-day window, while urgency/suggest_nudge (fully derived signals) must
survive untouched. get_last_triaged_timestamps is what run_triage.py uses
to skip re-triaging unchanged threads, so it needs to round-trip cleanly."""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage.store_triage_results import (
    RETENTION_DAYS,
    dismiss_result,
    enforce_retention,
    get_active_results,
    get_feedback,
    get_last_triaged_timestamps,
    init_db,
    record_feedback,
    snooze_result,
    upsert_results,
)


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


def _seed(db_path, thread_id, *, urgency="med", computed_at=None):
    computed_at = computed_at or datetime.now().isoformat()
    upsert_results(db_path, [{
        "thread_id": thread_id,
        "thread_name": f"+1555000{thread_id:04d}",
        "urgency": urgency,
        "reasoning": f"reasoning for thread {thread_id}",
        "action_required": True,
        "next_action": f"Reply to thread {thread_id}.",
        "suggest_nudge": True,
        "needs_review": True,
        "last_message_timestamp": computed_at,
        "computed_at": computed_at,
    }])


def test_enforce_retention_is_safe_on_a_fresh_db(tmp_path):
    # The dashboard calls this on every load, possibly before any triage
    # run has ever created the table — it must init rather than raise.
    db_path = tmp_path / "triage.db"
    assert enforce_retention(db_path) == 0


def test_upsert_writes_all_fields(tmp_path):
    db_path = tmp_path / "triage.db"
    now = datetime.now().isoformat()
    last_message_at = (datetime.now() - timedelta(days=3)).isoformat()
    upsert_results(db_path, [{
        "thread_id": 1,
        "thread_name": "+15551234567",
        "urgency": "high",
        "reasoning": "They asked a direct question 3 days ago with no reply.",
        "action_required": True,
        "next_action": "Answer their direct question.",
        "suggest_nudge": True,
        "needs_review": True,
        "last_message_timestamp": last_message_at,
        "computed_at": now,
    }])

    row = _read_row(db_path, 1)
    assert row["urgency"] == "high"
    assert row["reasoning"] == "They asked a direct question 3 days ago with no reply."
    assert row["action_required"] == 1
    assert row["next_action"] == "Answer their direct question."
    assert row["suggest_nudge"] == 1
    assert row["needs_review"] == 1
    assert row["last_message_timestamp"] == last_message_at
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
        "action_required": True,
        "next_action": "Complete the old request.",
        "suggest_nudge": True,
        "last_message_timestamp": old_computed_at,
        "computed_at": old_computed_at,
    }])

    scrubbed = enforce_retention(db_path, now=now)

    assert scrubbed == 1
    row = _read_row(db_path, 1)
    assert row["reasoning"] is None
    assert row["next_action"] is None
    assert row["action_required"] == 1
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
        "last_message_timestamp": recent_computed_at,
        "computed_at": recent_computed_at,
    }])

    scrubbed = enforce_retention(db_path, now=now)

    assert scrubbed == 0
    row = _read_row(db_path, 1)
    assert row["reasoning"] == "Recent — should survive retention."


def test_get_last_triaged_timestamps_empty_on_fresh_db(tmp_path):
    db_path = tmp_path / "triage.db"
    assert get_last_triaged_timestamps(db_path) == {}


def test_get_last_triaged_timestamps_returns_stored_values(tmp_path):
    db_path = tmp_path / "triage.db"
    last_message_at = datetime.now().isoformat()
    upsert_results(db_path, [{
        "thread_id": 1,
        "thread_name": "+15551234567",
        "urgency": "med",
        "reasoning": "some reasoning",
        "suggest_nudge": False,
        "last_message_timestamp": last_message_at,
        "computed_at": last_message_at,
    }])

    assert get_last_triaged_timestamps(db_path) == {1: last_message_at}


def test_fresh_result_defaults_to_pending(tmp_path):
    db_path = tmp_path / "triage.db"
    _seed(db_path, 1)

    assert _read_row(db_path, 1)["status"] == "pending"


def test_active_results_sorted_by_urgency_high_to_low(tmp_path):
    db_path = tmp_path / "triage.db"
    _seed(db_path, 1, urgency="low")
    _seed(db_path, 2, urgency="high")
    _seed(db_path, 3, urgency="med")

    active = get_active_results(db_path)

    assert [r["thread_id"] for r in active] == [2, 3, 1]


def test_dismiss_removes_from_active_results(tmp_path):
    db_path = tmp_path / "triage.db"
    _seed(db_path, 1)

    dismiss_result(db_path, 1)

    assert _read_row(db_path, 1)["status"] == "dismissed"
    assert get_active_results(db_path) == []


def test_snoozed_thread_excluded_until_it_expires(tmp_path):
    db_path = tmp_path / "triage.db"
    now = datetime.now()
    _seed(db_path, 1)

    snooze_result(db_path, 1, until=now + timedelta(days=3))

    # still snoozed: excluded
    assert get_active_results(db_path, now=now) == []

    # past the snooze date: reappears, and the stored status is normalized
    # back to pending rather than just being masked at query time
    active = get_active_results(db_path, now=now + timedelta(days=4))
    assert [r["thread_id"] for r in active] == [1]
    assert _read_row(db_path, 1)["status"] == "pending"
    assert _read_row(db_path, 1)["snoozed_until"] is None


def test_reupserting_a_dismissed_thread_reopens_it(tmp_path):
    db_path = tmp_path / "triage.db"
    _seed(db_path, 1, computed_at=(datetime.now() - timedelta(days=1)).isoformat())
    dismiss_result(db_path, 1)
    assert get_active_results(db_path) == []

    # a new triage run for this thread (i.e. a new message arrived) should
    # naturally reopen it, with no dismiss-specific logic needed
    _seed(db_path, 1, computed_at=datetime.now().isoformat())

    active = get_active_results(db_path)
    assert [r["thread_id"] for r in active] == [1]


def test_init_db_adds_needs_review_to_existing_results_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE triage_results (
                thread_id INTEGER PRIMARY KEY,
                thread_name TEXT,
                urgency TEXT NOT NULL,
                reasoning TEXT,
                suggest_nudge INTEGER NOT NULL,
                last_message_timestamp TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                snoozed_until TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(triage_results)")}
    finally:
        conn.close()
    assert {"needs_review", "action_required", "next_action", "run_id", "prompt_version", "prompt_fingerprint", "model"} <= columns

    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    finally:
        conn.close()
    assert {"triage_runs", "triage_call_log"} <= tables


def test_feedback_storage_contains_only_derived_fields_and_can_be_corrected(tmp_path):
    db_path = tmp_path / "triage.db"
    assessed_at = "2026-07-03T10:00:00"

    record_feedback(
        db_path,
        thread_id=7,
        result_computed_at=assessed_at,
        model_urgency="high",
        urgency_correct=False,
        corrected_urgency="med",
        reply_worthy=True,
        created_at=datetime(2026, 7, 3, 11, 0),
    )
    record_feedback(
        db_path,
        thread_id=7,
        result_computed_at=assessed_at,
        model_urgency="high",
        urgency_correct=None,
        corrected_urgency=None,
        reply_worthy=False,
        created_at=datetime(2026, 7, 3, 12, 0),
    )

    feedback = get_feedback(db_path)
    assert feedback == [{
        "thread_id": 7,
        "result_computed_at": assessed_at,
        "model_urgency": "high",
        "urgency_correct": None,
        "corrected_urgency": None,
        "reply_worthy": 0,
        "created_at": "2026-07-03T12:00:00",
    }]
    assert set(feedback[0]) == {
        "thread_id",
        "result_computed_at",
        "model_urgency",
        "urgency_correct",
        "corrected_urgency",
        "reply_worthy",
        "created_at",
    }


def test_feedback_rejects_inconsistent_derived_values(tmp_path):
    with pytest.raises(sqlite3.IntegrityError):
        record_feedback(
            tmp_path / "triage.db",
            thread_id=1,
            result_computed_at="2026-07-03T10:00:00",
            model_urgency="high",
            urgency_correct=True,
            corrected_urgency="low",
            reply_worthy=True,
        )
