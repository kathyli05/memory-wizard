import sqlite3
from datetime import datetime, timedelta

from contacts.build_profiles import compute_profile
from contacts.store_profiles import init_db, upsert_profiles


NOW = datetime(2030, 1, 20, 12, 0)


def _message(timestamp, is_from_me, text="substantive message"):
    return {
        "thread_id": 1,
        "thread_name": "Fictional Person",
        "timestamp": timestamp,
        "is_from_me": is_from_me,
        "text": text,
    }


def test_reply_history_uses_observable_opportunities_and_cumulative_windows():
    messages = [
        _message(NOW - timedelta(days=19), False),
        _message(NOW - timedelta(days=19) + timedelta(minutes=30), True),
        _message(NOW - timedelta(days=17), False),
        _message(NOW - timedelta(days=15), True),
        _message(NOW - timedelta(days=13), False),  # old unanswered opportunity
        _message(NOW - timedelta(days=4), False),   # recent, still censored
    ]
    profile = compute_profile(messages, now=NOW)
    assert profile["median_response_latency_seconds_365d"] is None
    assert profile["reply_opportunity_count_365d"] == 3
    assert profile["replied_within_1h_count_365d"] == 1
    assert profile["replied_within_1d_count_365d"] == 1
    assert profile["replied_within_3d_count_365d"] == 2
    assert profile["replied_within_7d_count_365d"] == 2


def test_recent_answered_opportunity_is_observable_immediately():
    messages = [
        _message(NOW - timedelta(hours=2), False),
        _message(NOW - timedelta(hours=1), True),
    ]
    profile = compute_profile(messages, now=NOW)
    assert profile["reply_opportunity_count_365d"] == 1
    assert profile["replied_within_1h_count_365d"] == 1


def test_placeholder_reply_does_not_close_the_reply_opportunity():
    messages = [
        _message(NOW - timedelta(days=10), False, "Can you answer this?"),
        _message(NOW - timedelta(days=9), True, "I'll get back to you later"),
        _message(NOW - timedelta(days=8), True, "Here is the actual answer."),
    ]
    profile = compute_profile(messages, now=NOW)
    assert profile["reply_opportunity_count_365d"] == 1
    assert profile["replied_within_1d_count_365d"] == 0
    assert profile["replied_within_3d_count_365d"] == 1


def test_profile_store_adds_reply_columns_to_legacy_database(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE contact_profiles (
                thread_id INTEGER PRIMARY KEY,
                thread_name TEXT,
                message_count_90d INTEGER NOT NULL,
                messages_per_day_90d REAL NOT NULL,
                median_response_latency_seconds_365d REAL,
                conversation_count_365d INTEGER NOT NULL,
                initiation_ratio_me_365d REAL,
                computed_at TEXT NOT NULL
            )
        """)
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(contact_profiles)")}
    assert {
        "reply_opportunity_count_365d", "replied_within_1h_count_365d",
        "replied_within_1d_count_365d", "replied_within_3d_count_365d",
        "replied_within_7d_count_365d",
    } <= columns


def test_profile_store_round_trips_new_counts(tmp_path):
    db_path = tmp_path / "triage.db"
    profile = compute_profile([
        _message(NOW - timedelta(days=10), False),
        _message(NOW - timedelta(days=8), True),
    ], now=NOW)
    upsert_profiles(db_path, [profile])
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT reply_opportunity_count_365d, replied_within_3d_count_365d "
            "FROM contact_profiles"
        ).fetchone()
    assert row == (1, 1)
