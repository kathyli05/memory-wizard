"""Compute per-thread contact profiles from parsed messages.

Pure functions — take the message list from ingestion.parse_messages,
return derived-signal dicts only. No message text is read or retained
beyond this computation.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

FREQUENCY_WINDOW_DAYS = 90
STATS_WINDOW_DAYS = 365
CONVERSATION_GAP_HOURS = 24


def compute_profile(thread_messages: list[dict], *, now: datetime) -> dict:
    """thread_messages must be one thread's messages, sorted by timestamp ascending."""
    thread_id = thread_messages[0]["thread_id"]
    thread_name = thread_messages[0]["thread_name"]

    freq_cutoff = now - timedelta(days=FREQUENCY_WINDOW_DAYS)
    stats_cutoff = now - timedelta(days=STATS_WINDOW_DAYS)

    recent_90d = [m for m in thread_messages if m["timestamp"] >= freq_cutoff]
    message_count_90d = len(recent_90d)
    messages_per_day_90d = message_count_90d / FREQUENCY_WINDOW_DAYS

    recent_365d = [m for m in thread_messages if m["timestamp"] >= stats_cutoff]

    median_response_latency_seconds_365d = _median_response_latency(recent_365d)
    conversation_count_365d, initiation_ratio_me_365d = _initiation_stats(recent_365d)

    return {
        "thread_id": thread_id,
        "thread_name": thread_name,
        "message_count_90d": message_count_90d,
        "messages_per_day_90d": messages_per_day_90d,
        "median_response_latency_seconds_365d": median_response_latency_seconds_365d,
        "conversation_count_365d": conversation_count_365d,
        "initiation_ratio_me_365d": initiation_ratio_me_365d,
        "computed_at": now.isoformat(),
    }


def compute_all_profiles(messages: list[dict], *, now: datetime | None = None) -> list[dict]:
    # parse_messages produces naive datetimes (Apple epoch has no tz info),
    # so `now` must stay naive too or comparisons/subtraction will raise.
    now = now or datetime.now()

    by_thread = defaultdict(list)
    for m in messages:
        by_thread[m["thread_id"]].append(m)

    return [compute_profile(sorted(msgs, key=lambda m: m["timestamp"]), now=now)
            for msgs in by_thread.values()]


def _median_response_latency(messages: list[dict]) -> float | None:
    """Median seconds between the end of each incoming run and my next reply.

    A gap larger than CONVERSATION_GAP_HOURS means the next message from me
    is starting a new conversation, not replying to the old one — excluded
    so multi-day silences don't get counted as "response latency."
    """
    gap_threshold = timedelta(hours=CONVERSATION_GAP_HOURS)
    latencies = []
    incoming_run_end = None

    for m in messages:
        if not m["is_from_me"]:
            incoming_run_end = m["timestamp"]
        else:
            if incoming_run_end is not None:
                latency = m["timestamp"] - incoming_run_end
                if latency <= gap_threshold:
                    latencies.append(latency.total_seconds())
            incoming_run_end = None

    return statistics.median(latencies) if latencies else None


def _initiation_stats(messages: list[dict]) -> tuple[int, float | None]:
    """Count conversations (gap > CONVERSATION_GAP_HOURS starts a new one) and
    the fraction initiated by me."""
    if not messages:
        return 0, None

    gap = timedelta(hours=CONVERSATION_GAP_HOURS)
    conversation_count = 0
    me_initiated = 0
    prev_timestamp = None

    for m in messages:
        is_new_conversation = prev_timestamp is None or (m["timestamp"] - prev_timestamp) > gap
        if is_new_conversation:
            conversation_count += 1
            if m["is_from_me"]:
                me_initiated += 1
        prev_timestamp = m["timestamp"]

    initiation_ratio_me = me_initiated / conversation_count if conversation_count else None
    return conversation_count, initiation_ratio_me
