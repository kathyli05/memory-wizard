import json
import sqlite3
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from scripts.run_triage import (
    _apply_max_calls,
    _build_parser,
    _partition_candidates,
    _redacted_request,
    _run,
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

    request = _redacted_request(profile, messages, NOW)
    serialized = json.dumps(request)

    assert request["tool_choice"]["name"] == "emit_triage_assessment"
    assert "needs_review" in request["tools"][0]["input_schema"]["required"]
    assert "action_required" in request["tools"][0]["input_schema"]["required"]
    assert "next_action" in request["tools"][0]["input_schema"]["required"]
    assert "provide availability" in request["system"]
    assert "Use this urgency rubric consistently" in request["system"]
    assert "Keep urgency, credibility, and safe action distinct" in request["system"]
    assert "solely because the contact is new" in request["system"]
    assert "<assessment_time>\\nLocal time: 2026-07-01 12:00" in serialized
    assert "Median response latency" not in serialized
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


def test_max_calls_must_be_positive_and_caps_preview_shape():
    parser = _build_parser()

    assert parser.parse_args(["--max-calls", "2"]).max_calls == 2
    with pytest.raises(SystemExit):
        parser.parse_args(["--max-calls", "0"])

    candidates = [(index, [index]) for index in range(4)]
    assert _apply_max_calls(candidates, None) == candidates
    assert _apply_max_calls(candidates, 2) == candidates[:2]


def test_call_run_stores_partial_successes_and_enforces_retention(
    monkeypatch, capsys, tmp_path
):
    messages = [_message(1, "one"), _message(2, "two"), _message(3, "three")]
    candidates = [_candidate(1), _candidate(2), _candidate(3)]
    profiles = [
        {
            "thread_id": thread_id,
            "thread_name": "private",
            "median_response_latency_seconds_365d": None,
            "message_count_90d": 1,
            "messages_per_day_90d": 0.01,
            "initiation_ratio_me_365d": None,
        }
        for thread_id in (1, 2, 3)
    ]
    stored = []
    call_count = 0

    def fake_run(client, profile, thread_messages, assessment_time):
        nonlocal call_count
        assert assessment_time.tzinfo is not None
        call_count += 1
        if profile["thread_id"] == 2:
            raise RuntimeError("private provider error")
        return {
            "thread_id": profile["thread_id"],
            "urgency": "med",
            "reasoning": "derived rationale",
            "action_required": True,
            "next_action": "Confirm the synthetic request.",
            "suggest_nudge": True,
            "needs_review": False,
            "_usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_creation_tokens": 10,
                "cache_read_tokens": 5,
            },
        }

    monkeypatch.setattr("scripts.run_triage.parse_messages", lambda _: messages)
    monkeypatch.setattr("scripts.run_triage.find_unanswered_threads", lambda *a, **k: candidates)
    monkeypatch.setattr("scripts.run_triage.compute_all_profiles", lambda _: profiles)
    monkeypatch.setattr("scripts.run_triage.get_last_triaged_timestamps", lambda _: {})
    monkeypatch.setattr("scripts.run_triage._create_anthropic_client", lambda: object())
    monkeypatch.setattr("scripts.run_triage.run_triage", fake_run)
    monkeypatch.setattr(
        "scripts.run_triage.upsert_results",
        lambda db_path, results: stored.extend(results),
    )
    monkeypatch.setattr("scripts.run_triage.enforce_retention", lambda _: 0)

    args = SimpleNamespace(
        threshold_hours=0,
        lookback_days=7,
        dest=tmp_path / "triage.db",
        retriage_one=False,
        retriage_all=False,
        max_calls=None,
        call=True,
    )
    _run("synthetic-copy.db", args)

    output = capsys.readouterr().out
    assert "API calls about to be made: 3" in output
    assert "stored 2 successful result(s); 1 request(s) failed" in output
    assert "private provider error" not in output
    assert call_count == 3
    assert [result["thread_id"] for result in stored] == [1, 3]

    conn = sqlite3.connect(args.dest)
    try:
        run = conn.execute(
            "SELECT attempted_count, success_count, failure_count, input_tokens, "
            "output_tokens FROM triage_runs"
        ).fetchone()
        calls = conn.execute(
            "SELECT thread_id, status, error_type FROM triage_call_log ORDER BY thread_id"
        ).fetchall()
    finally:
        conn.close()
    assert run == (3, 2, 1, 200, 40)
    assert calls == [
        (1, "success", None),
        (2, "failure", "unexpected"),
        (3, "success", None),
    ]
    assert "usage: input=200 output=40" in output


def test_zero_candidate_call_run_records_zero_attempt_summary(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.run_triage.parse_messages", lambda _: [])
    monkeypatch.setattr("scripts.run_triage.find_unanswered_threads", lambda *a, **k: [])
    monkeypatch.setattr("scripts.run_triage.compute_all_profiles", lambda _: [])
    monkeypatch.setattr("scripts.run_triage.get_last_triaged_timestamps", lambda _: {})
    monkeypatch.setattr(
        "scripts.run_triage._create_anthropic_client",
        lambda: (_ for _ in ()).throw(AssertionError("zero candidates needs no client")),
    )
    args = SimpleNamespace(
        threshold_hours=24, lookback_days=7, dest=tmp_path / "triage.db",
        retriage_one=False, retriage_all=False, max_calls=5, call=True,
    )
    _run("synthetic-copy.db", args)
    with sqlite3.connect(args.dest) as conn:
        assert conn.execute(
            "SELECT eligible_count, attempted_count, success_count, failure_count "
            "FROM triage_runs"
        ).fetchone() == (0, 0, 0, 0)


def test_capped_call_run_attempts_only_the_cap(monkeypatch, tmp_path):
    messages = [_message(1, "one"), _message(2, "two")]
    candidates = [_candidate(1), _candidate(2)]
    profiles = [{
        "thread_id": thread_id, "thread_name": "private",
        "median_response_latency_seconds_365d": None,
        "message_count_90d": 1, "messages_per_day_90d": 0.01,
        "initiation_ratio_me_365d": None,
    } for thread_id in (1, 2)]
    monkeypatch.setattr("scripts.run_triage.parse_messages", lambda _: messages)
    monkeypatch.setattr("scripts.run_triage.find_unanswered_threads", lambda *a, **k: candidates)
    monkeypatch.setattr("scripts.run_triage.compute_all_profiles", lambda _: profiles)
    monkeypatch.setattr("scripts.run_triage.get_last_triaged_timestamps", lambda _: {})
    monkeypatch.setattr("scripts.run_triage._create_anthropic_client", lambda: object())
    monkeypatch.setattr("scripts.run_triage.run_triage", lambda *a: {
        "thread_id": a[1]["thread_id"], "urgency": "low", "reasoning": "derived",
        "action_required": False, "next_action": "",
        "suggest_nudge": False, "needs_review": False,
        "_usage": {"input_tokens": 1, "output_tokens": 1,
                   "cache_creation_tokens": 0, "cache_read_tokens": 0},
    })
    args = SimpleNamespace(
        threshold_hours=24, lookback_days=7, dest=tmp_path / "triage.db",
        retriage_one=False, retriage_all=False, max_calls=1, call=True,
    )
    _run("synthetic-copy.db", args)
    with sqlite3.connect(args.dest) as conn:
        assert conn.execute(
            "SELECT eligible_count, attempted_count FROM triage_runs"
        ).fetchone() == (2, 1)
        assert conn.execute("SELECT COUNT(*) FROM triage_call_log").fetchone()[0] == 1
