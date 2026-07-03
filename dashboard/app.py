"""Streamlit dashboard for the Messages triage channel.

Read/action-only: this app never calls the Claude API. It only displays
results from triage runs kicked off separately (CLI or a scheduled job)
and lets you dismiss/snooze them. It re-derives "is this thread actually
still unanswered" from your current chat.db (deterministic, free) via the
same ephemeral-copy path the CLI scripts use — cached for a short TTL so
button clicks don't re-snapshot chat.db on every rerun; the Refresh
button clears the cache for an immediate re-check.

Security posture (see SECURITY_REVIEW.md):
- Serve on localhost only — enforced by .streamlit/config.toml (F1).
- `reasoning` and `thread_name` are influenced by untrusted third-party
  message content via the model; they are rendered as escaped/plain text,
  never as markdown, so injected output can't create links or trigger
  image fetches (F2).
- Retention is enforced on every load, not only after triage runs (F4).

Run with:
    streamlit run dashboard/app.py

Override data sources for testing via env vars:
    CHAT_DB_SOURCE=path/to/fixture.db TRIAGE_DB_PATH=path/to/scratch.db \
        streamlit run dashboard/app.py
"""

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import DEFAULT_SOURCE as REAL_CHAT_DB_SOURCE, ephemeral_copy
from ingestion.parse_messages import parse_messages
from contacts.macos_contacts import MacOSContactResolver
from contacts.name_resolver import NullContactResolver, resolved_thread_names
from triage.detect_unanswered import find_unanswered_threads
from triage.store_triage_results import (
    dismiss_result,
    enforce_retention,
    get_active_results,
    get_last_triaged_timestamps,
    snooze_result,
)

CHAT_DB_SOURCE = Path(os.environ.get("CHAT_DB_SOURCE", str(REAL_CHAT_DB_SOURCE)))
TRIAGE_DB_PATH = Path(os.environ.get("TRIAGE_DB_PATH", "./data/triage.db"))

LIVE_CHECK_TTL_SECONDS = 60

URGENCY_ALERT = {"high": st.error, "med": st.warning, "low": st.info}

# Streamlit renders alert/markdown text as markdown; thread names come from
# chat.db (group members can set them) so every markdown-active character
# gets backslash-escaped before display.
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!<>|~$:])")


def _escape_markdown(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", str(text))


def _format_hours(hours: float) -> str:
    if hours < 24:
        return f"{hours:.0f}h ago"
    return f"{hours / 24:.1f}d ago"


@st.cache_data(ttl=LIVE_CHECK_TTL_SECONDS, show_spinner=False)
def _live_unanswered_candidates():
    """Snapshot chat.db and detect unanswered threads. Cached so widget
    clicks (which rerun the whole script) don't re-copy chat.db each time;
    the raw message list never leaves this function."""
    with ephemeral_copy(source=CHAT_DB_SOURCE) as chat_copy_path:
        messages = parse_messages(chat_copy_path)
    return find_unanswered_threads(messages)


def load_dashboard_data(contact_resolver=None):
    """Live-recheck against current Messages, intersected with stored
    (non-dismissed/non-snoozed) triage results."""
    enforce_retention(TRIAGE_DB_PATH)

    candidates = _live_unanswered_candidates()
    resolver = contact_resolver or NullContactResolver()
    display_names = resolved_thread_names(candidates, resolver)
    live_unanswered_ids = {c["thread_id"] for c in candidates}
    hours_by_thread = {c["thread_id"]: c["hours_since_last_message"] for c in candidates}

    active_results = get_active_results(TRIAGE_DB_PATH)
    flagged = []
    for result in active_results:
        if result["thread_id"] in live_unanswered_ids:
            rendered = dict(result)
            rendered["thread_name"] = display_names[result["thread_id"]]
            flagged.append(rendered)

    all_triaged_ids = set(get_last_triaged_timestamps(TRIAGE_DB_PATH).keys())
    untriaged_count = len(live_unanswered_ids - all_triaged_ids)

    return flagged, hours_by_thread, untriaged_count


@st.cache_resource
def _contact_resolver():
    return MacOSContactResolver()


def contact_name_controls(resolver) -> bool:
    """Return whether local resolution is available; never expose contact data."""
    status = resolver.authorization_status()
    if status in {"authorized", "limited"}:
        return True
    if status == "not-determined":
        if st.button("Enable saved contact names"):
            return resolver.request_access() in {"authorized", "limited"}
    elif status in {"denied", "restricted"}:
        st.caption("Saved contact names are unavailable; showing message identifiers.")
    return False


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
        # thread_name is escaped and reasoning rendered as plain text — both
        # are untrusted-content-derived; markdown rendering would let an
        # injected message create links or exfiltrating image fetches (F2).
        alert(f"**{_escape_markdown(result['thread_name'])}** — {urgency.upper()} · unanswered {age_label}")

        if result["reasoning"]:
            st.text(result["reasoning"])
        else:
            st.caption("Reasoning no longer available — past the 14-day retention window.")
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
        _live_unanswered_candidates.clear()
        st.rerun()

    resolver = _contact_resolver()
    contacts_enabled = contact_name_controls(resolver)
    flagged, hours_by_thread, untriaged_count = load_dashboard_data(
        resolver if contacts_enabled else None
    )

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
