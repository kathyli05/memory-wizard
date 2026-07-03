"""Deterministic unanswered-thread detection — no AI call.

A thread is a triage candidate if its most recent message is incoming
(is_from_me=False), older than the configurable threshold, and not older
than the configurable lookback window (so threads that have sat
unanswered for years don't become candidates — and don't burn triage API
calls — ahead of recent ones). Candidates carry timing/identity info
only, not message text — Stage 4's triage agent pulls the actual
last-5-messages context per candidate, minimizing what's held here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

DEFAULT_THRESHOLD_HOURS = 24
DEFAULT_LOOKBACK_DAYS = 150


def find_unanswered_threads(
    messages: list[dict],
    *,
    threshold_hours: float = DEFAULT_THRESHOLD_HOURS,
    lookback_days: float | None = DEFAULT_LOOKBACK_DAYS,
    now: datetime | None = None,
) -> list[dict]:
    # parse_messages produces naive datetimes, so `now` must stay naive too.
    now = now or datetime.now()
    threshold = timedelta(hours=threshold_hours)
    cutoff = now - timedelta(days=lookback_days) if lookback_days is not None else None

    by_thread = defaultdict(list)
    for m in messages:
        by_thread[m["thread_id"]].append(m)

    candidates = []
    for thread_messages in by_thread.values():
        last = max(thread_messages, key=lambda m: m["timestamp"])
        age = now - last["timestamp"]
        in_lookback_window = cutoff is None or last["timestamp"] >= cutoff
        if not last["is_from_me"] and age >= threshold and in_lookback_window:
            candidates.append(
                {
                    "thread_id": last["thread_id"],
                    "thread_name": last["thread_name"],
                    "thread_display_name": last.get("thread_display_name"),
                    "thread_identifier": last.get("thread_identifier"),
                    "last_message_sender": last["sender"],
                    "last_message_timestamp": last["timestamp"],
                    "hours_since_last_message": age.total_seconds() / 3600,
                }
            )

    candidates.sort(key=lambda c: c["last_message_timestamp"])
    return candidates
