"""Tests for the lookback window on triage.detect_unanswered.

Guards against threads that have sat unanswered for a long time (e.g.
since 2023) becoming triage candidates ahead of recent ones and burning
API calls on threads the user has already decided not to reply to.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.parse_messages import parse_messages
from tests.fixtures.make_fixture_db import build_fixture_db
from triage.detect_unanswered import find_unanswered_threads


def _candidate_thread_ids(messages, **kwargs):
    return {c["thread_id"] for c in find_unanswered_threads(messages, **kwargs)}


def test_default_lookback_excludes_very_old_thread_but_keeps_recent_one(tmp_path):
    db_path = build_fixture_db(tmp_path / "fixture_chat.db")
    messages = parse_messages(db_path)

    thread_ids = _candidate_thread_ids(messages)

    assert 3 in thread_ids  # ~3 days old, well within the default window
    assert 5 not in thread_ids  # ~200 days old, past the default 150-day window


def test_lookback_none_disables_the_window(tmp_path):
    db_path = build_fixture_db(tmp_path / "fixture_chat.db")
    messages = parse_messages(db_path)

    thread_ids = _candidate_thread_ids(messages, lookback_days=None)

    assert 5 in thread_ids


def test_wide_lookback_includes_old_thread(tmp_path):
    db_path = build_fixture_db(tmp_path / "fixture_chat.db")
    messages = parse_messages(db_path)

    thread_ids = _candidate_thread_ids(messages, lookback_days=365)

    assert 5 in thread_ids
