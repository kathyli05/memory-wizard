"""Compute per-thread contact profiles from parsed messages.

Pure functions — take the message list from ingestion.parse_messages,
return derived-signal dicts only. No message text is read or retained
beyond this computation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

FREQUENCY_WINDOW_DAYS = 90
STATS_WINDOW_DAYS = 365
CONVERSATION_GAP_HOURS = 24
REPLY_OBSERVATION_DAYS = 7

_PLACEHOLDER_REPLY_RE = re.compile(
    r"\b(?:i(?:'ll| will|'m going to| am going to)|let me|will)\s+"
    r"(?:respond|reply|get back to you|circle back)\s*(?:later|soon)?\b",
    re.IGNORECASE,
)


def is_placeholder_reply(text: str) -> bool:
    """True for a deferral that promises a later substantive response."""
    return bool(_PLACEHOLDER_REPLY_RE.search(text or ""))


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

    reply_history = _reply_history(recent_365d, now=now)
    conversation_count_365d, initiation_ratio_me_365d = _initiation_stats(recent_365d)

    return {
        "thread_id": thread_id,
        "thread_name": thread_name,
        "message_count_90d": message_count_90d,
        "messages_per_day_90d": messages_per_day_90d,
        # Retained as an inert compatibility field for existing databases.
        "median_response_latency_seconds_365d": None,
        **reply_history,
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


def _reply_history(messages: list[dict], *, now: datetime) -> dict:
    """Count observable incoming opportunities and cumulative reply windows.

    Consecutive incoming messages within seven days are one waiting-for-reply
    run, measured from its latest message. A reply is observable immediately;
    an unanswered run enters the denominator only after all seven days pass.
    This avoids treating a recent message as a missed reply.
    """
    window = timedelta(days=REPLY_OBSERVATION_DAYS)
    latencies = []
    unanswered_observable = 0
    incoming_run_end = None

    for message in messages:
        timestamp = message["timestamp"]
        if not message["is_from_me"]:
            if incoming_run_end is not None and timestamp - incoming_run_end > window:
                unanswered_observable += 1
            incoming_run_end = timestamp
            continue

        if incoming_run_end is None:
            continue
        if is_placeholder_reply(message.get("text", "")):
            continue
        latency = timestamp - incoming_run_end
        if latency <= window:
            latencies.append(latency)
        else:
            unanswered_observable += 1
        incoming_run_end = None

    if incoming_run_end is not None and now - incoming_run_end >= window:
        unanswered_observable += 1

    opportunities = len(latencies) + unanswered_observable
    thresholds = {
        "replied_within_1h_count_365d": timedelta(hours=1),
        "replied_within_1d_count_365d": timedelta(days=1),
        "replied_within_3d_count_365d": timedelta(days=3),
        "replied_within_7d_count_365d": window,
    }
    return {
        "reply_opportunity_count_365d": opportunities,
        **{
            name: sum(latency <= threshold for latency in latencies)
            for name, threshold in thresholds.items()
        },
    }


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
