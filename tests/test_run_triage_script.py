import json
from datetime import datetime, timedelta

from scripts.run_triage import _partition_candidates, _redacted_request


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
    messages = [_message(1, "Private message body", sender="private@example.com")]

    request = _redacted_request(profile, messages)
    serialized = json.dumps(request)

    assert request["tool_choice"]["name"] == "emit_triage_assessment"
    assert "[REDACTED THREAD]" in serialized
    assert "[REDACTED SENDER]" in serialized
    assert "[REDACTED readable message 1]" in serialized
    assert "Private Contact Name" not in serialized
    assert "Private message body" not in serialized
    assert "private@example.com" not in serialized
