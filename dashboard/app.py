"""Streamlit dashboard for the Messages triage channel.

Read/action-only: this app never calls the Claude API. It only displays
results from triage runs kicked off separately (CLI or a scheduled job)
and lets you dismiss/snooze them. On every load it re-derives "is this
thread actually still unanswered" from your current chat.db (deterministic,
free) via the same ephemeral-copy path the CLI scripts use, so a thread
you've already replied to in Messages disappears immediately rather than
waiting for the next triage run to catch up.

Run with:
    streamlit run dashboard/app.py

Override data sources for testing via env vars:
    CHAT_DB_SOURCE=path/to/fixture.db TRIAGE_DB_PATH=path/to/scratch.db \
        streamlit run dashboard/app.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import DEFAULT_SOURCE as REAL_CHAT_DB_SOURCE, ephemeral_copy
from ingestion.parse_messages import parse_messages
from triage.detect_unanswered import find_unanswered_threads
from triage.store_triage_results import (
    dismiss_result,
    get_active_results,
    get_last_triaged_timestamps,
    snooze_result,
)

CHAT_DB_SOURCE = Path(os.environ.get("CHAT_DB_SOURCE", str(REAL_CHAT_DB_SOURCE)))
TRIAGE_DB_PATH = Path(os.environ.get("TRIAGE_DB_PATH", "./data/triage.db"))

URGENCY_ALERT = {"high": st.error, "med": st.warning, "low": st.info}


def _format_hours(hours: float) -> str:
    if hours < 24:
        return f"{hours:.0f}h ago"
    return f"{hours / 24:.1f}d ago"


def load_dashboard_data():
    """Live-recheck against current Messages, intersected with stored
    (non-dismissed/non-snoozed) triage results."""
    with ephemeral_copy(source=CHAT_DB_SOURCE) as chat_copy_path:
        messages = parse_messages(chat_copy_path)

    candidates = find_unanswered_threads(messages)
    live_unanswered_ids = {c["thread_id"] for c in candidates}
    hours_by_thread = {c["thread_id"]: c["hours_since_last_message"] for c in candidates}

    active_results = get_active_results(TRIAGE_DB_PATH)
    flagged = [r for r in active_results if r["thread_id"] in live_unanswered_ids]

    all_triaged_ids = set(get_last_triaged_timestamps(TRIAGE_DB_PATH).keys())
    untriaged_count = len(live_unanswered_ids - all_triaged_ids)

    return flagged, hours_by_thread, untriaged_count


def render_snooze_controls(thread_id: int):
    with st.popover("Snooze"):
        st.caption("Hide until:")
        cols = st.columns(3)
        presets = [("1 day", 1), ("3 days", 3), ("1 week", 7)]
        for col, (label, days) in zip(cols, presets):
            if col.button(label, key=f"snooze_{thread_id}_{days}d"):
                snooze_result(TRIAGE_DB_PATH, thread_id, until=datetime.now() + timedelta(days=days))
                st.rerun()

        custom_date = st.date_input("Custom date", key=f"snooze_date_{thread_id}")
        if st.button("Snooze until then", key=f"snooze_custom_{thread_id}"):
            until = datetime.combine(custom_date, datetime.min.time())
            snooze_result(TRIAGE_DB_PATH, thread_id, until=until)
            st.rerun()


def render_card(result: dict, hours_by_thread: dict):
    thread_id = result["thread_id"]
    urgency = result["urgency"]
    alert = URGENCY_ALERT.get(urgency, st.info)
    hours = hours_by_thread.get(thread_id)
    age_label = _format_hours(hours) if hours is not None else "unknown"

    with st.container(border=True):
        alert(f"**{result['thread_name']}** — {urgency.upper()} · unanswered {age_label}")

        reasoning = result["reasoning"] or "_(reasoning no longer available — past the 14-day retention window)_"
        st.markdown(reasoning)
        if result["suggest_nudge"]:
            st.caption("💡 Suggested: consider sending a nudge")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Dismiss", key=f"dismiss_{thread_id}"):
                dismiss_result(TRIAGE_DB_PATH, thread_id)
                st.rerun()
        with col2:
            render_snooze_controls(thread_id)


def main():
    st.set_page_config(page_title="Message Triage", page_icon="📬", layout="centered")
    st.title("📬 Message Triage")

    if st.button("🔄 Refresh"):
        st.rerun()

    flagged, hours_by_thread, untriaged_count = load_dashboard_data()

    if untriaged_count:
        st.info(
            f"{untriaged_count} unanswered thread(s) haven't been triaged yet — "
            f"run `python scripts/run_triage.py --call` to assess them."
        )

    if not flagged:
        st.success("Nothing flagged right now.")
        return

    for result in flagged:
        render_card(result, hours_by_thread)


if __name__ == "__main__":
    main()
