"""Deterministic unanswered-thread detection — no AI call.

A thread is a triage candidate if its most recent message is incoming
(is_from_me=False) and older than the configurable threshold. Candidates
carry timing/identity info only, not message text — Stage 4's triage
agent pulls the actual last-5-messages context per candidate, minimizing
what's held here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

DEFAULT_THRESHOLD_HOURS = 24


def find_unanswered_threads(
    messages: list[dict],
    *,
    threshold_hours: float = DEFAULT_THRESHOLD_HOURS,
    now: datetime | None = None,
) -> list[dict]:
    # parse_messages produces naive datetimes, so `now` must stay naive too.
    now = now or datetime.now()
    threshold = timedelta(hours=threshold_hours)

    by_thread = defaultdict(list)
    for m in messages:
        by_thread[m["thread_id"]].append(m)

    candidates = []
    for thread_messages in by_thread.values():
        last = max(thread_messages, key=lambda m: m["timestamp"])
        age = now - last["timestamp"]
        if not last["is_from_me"] and age >= threshold:
            candidates.append(
                {
                    "thread_id": last["thread_id"],
                    "thread_name": last["thread_name"],
                    "last_message_sender": last["sender"],
                    "last_message_timestamp": last["timestamp"],
                    "hours_since_last_message": age.total_seconds() / 3600,
                }
            )

    candidates.sort(key=lambda c: c["last_message_timestamp"])
    return candidates
