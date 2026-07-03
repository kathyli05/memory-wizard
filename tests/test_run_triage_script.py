import json
import sys
from datetime import datetime, timedelta

import pytest

from scripts.run_triage import (
    _build_parser,
    _partition_candidates,
    _redacted_request,
    main,
)
from triage.detect_unanswered import find_unanswered_threads


NOW = datetime(2026, 7, 1, 12, 0)


def _message(thread_id, text, *, sender="private-sender"):
    return {
        "thread_id": thread_id,
        "thread_name": "private-thread-name",
        "thread_display_name": None,
        "thread_identifier": "private-identifier",
        "sender": sender,
        "text": text,
        "timestamp": NOW - timedelta(days=thread_id),
        "is_from_me": False,
    }


def _candidate(thread_id):
    timestamp = NOW - timedelta(days=thread_id)
    return {
        "thread_id": thread_id,
        "thread_name": "private-thread-name",
        "last_message_timestamp": timestamp,
    }


def test_retriage_one_selects_at_most_one_previous_result():
    messages = [_message(1, "private text one"), _message(2, "private text two")]
    candidates = [_candidate(1), _candidate(2)]
    last_triaged = {
        1: NOW.isoformat(),
        2: NOW.isoformat(),
    }

    selected, filtered, unchanged = _partition_candidates(
        messages, candidates, last_triaged, retriage_one=True
    )

    assert [item[0]["thread_id"] for item in selected] == [1]
    assert len(selected) == 1
    assert filtered == []
    assert unchanged == []


def test_retriage_one_skips_threads_without_a_previous_result():
    messages = [_message(1, "new"), _message(2, "previous")]
    candidates = [_candidate(1), _candidate(2)]

    selected, _, _ = _partition_candidates(
        messages,
        candidates,
        {2: NOW.isoformat()},
        retriage_one=True,
    )

    assert [item[0]["thread_id"] for item in selected] == [2]


def test_retriage_all_selects_all_eligible_prior_results():
    messages = [_message(1, "first"), _message(2, "second")]
    candidates = [_candidate(1), _candidate(2)]

    selected, filtered, unchanged = _partition_candidates(
        messages,
        candidates,
        {1: NOW.isoformat(), 2: NOW.isoformat()},
        retriage_all=True,
    )

    assert [item[0]["thread_id"] for item in selected] == [1, 2]
    assert filtered == []
    assert unchanged == []


def test_retriage_all_excludes_never_triaged_threads():
    messages = [_message(1, "never triaged"), _message(2, "prior result")]
    candidates = [_candidate(1), _candidate(2)]

    selected, _, _ = _partition_candidates(
        messages, candidates, {2: NOW.isoformat()}, retriage_all=True
    )

    assert [item[0]["thread_id"] for item in selected] == [2]


def test_retriage_all_excludes_automated_threads():
    messages = [
        _message(1, "Your verification code is 123456", sender="65123"),
        _message(2, "Could you reply about dinner?"),
    ]
    candidates = [_candidate(1), _candidate(2)]

    selected, filtered, _ = _partition_candidates(
        messages,
        candidates,
        {1: NOW.isoformat(), 2: NOW.isoformat()},
        retriage_all=True,
    )

    assert [item[0]["thread_id"] for item in selected] == [2]
    assert [item[0]["thread_id"] for item in filtered] == [1]
    assert filtered[0][1] == (
        "matches a verification or one-time-code pattern and contains "
        "no genuine reply request"
    )


def test_retriage_all_preserves_lookback_filtering():
    recent = _message(1, "recent")
    recent["timestamp"] = NOW - timedelta(days=3)
    old = _message(2, "old")
    old["timestamp"] = NOW - timedelta(days=8)
    messages = [recent, old]
    candidates = find_unanswered_threads(
        messages, threshold_hours=24, lookback_days=7, now=NOW
    )

    selected, _, _ = _partition_candidates(
        messages,
        candidates,
        {1: NOW.isoformat(), 2: NOW.isoformat()},
        retriage_all=True,
    )

    assert [item[0]["thread_id"] for item in selected] == [1]


def test_regular_mode_still_deduplicates_unchanged_results():
    messages = [_message(1, "private")]
    candidates = [_candidate(1)]

    selected, _, unchanged = _partition_candidates(
        messages, candidates, {1: NOW.isoformat()}
    )

    assert selected == []
    assert [candidate["thread_id"] for candidate in unchanged] == [1]


def test_preview_preserves_request_shape_but_redacts_private_strings():
    profile = {
        "thread_id": 1,
        "thread_name": "Private Contact Name",
        "median_response_latency_seconds_365d": None,
        "message_count_90d": 1,
        "messages_per_day_90d": 0.01,
        "initiation_ratio_me_365d": None,
    }
    messages = [
        _message(1, "Private message body", sender="private@example.com"),
        _message(1, "Second private body", sender="+15551234567"),
    ]

    request = _redacted_request(profile, messages)
    serialized = json.dumps(request)

    assert request["tool_choice"]["name"] == "emit_triage_assessment"
    assert "[REDACTED THREAD]" in serialized
    assert "[REDACTED SENDER]" in serialized
    assert "[REDACTED readable message 1]" in serialized
    assert "Private Contact Name" not in serialized
    assert "Private message body" not in serialized
    assert "Second private body" not in serialized
    assert "private@example.com" not in serialized
    assert "+15551234567" not in serialized


def test_retriage_flags_are_mutually_exclusive():
    parser = _build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--retriage-one", "--retriage-all"])

    assert exc_info.value.code == 2


def test_call_retriage_all_requires_confirmation_before_copy(monkeypatch, capsys):
    copy_attempted = False

    def forbidden_copy(*args, **kwargs):
        nonlocal copy_attempted
        copy_attempted = True
        raise AssertionError("Messages copy must not start before confirmation")

    monkeypatch.setattr("scripts.run_triage.ephemeral_copy", forbidden_copy)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_triage.py", "--call", "--retriage-all"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert not copy_attempted
    assert "requires explicit --confirm-retriage-all" in capsys.readouterr().err


def test_retriage_context_is_capped_at_last_five_messages():
    messages = []
    for index in range(7):
        message = _message(1, f"private message {index}")
        message["timestamp"] = NOW - timedelta(minutes=7 - index)
        messages.append(message)

    selected, _, _ = _partition_candidates(
        messages,
        [_candidate(1)],
        {1: NOW.isoformat()},
        retriage_all=True,
    )

    context = selected[0][1]
    assert len(context) == 5
    assert [message["text"] for message in context] == [
        "private message 2",
        "private message 3",
        "private message 4",
        "private message 5",
        "private message 6",
    ]
