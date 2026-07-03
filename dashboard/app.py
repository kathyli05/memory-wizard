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
  never as live markup, so injected output can't create links or trigger
  image fetches (F2).
- Retention is enforced on every load, not only after triage runs (F4).

Theming: a self-contained "cosmic cozy" theme (no external font/asset
fetches — the localhost-only posture stays intact). Light and dark
variants follow the system setting via `prefers-color-scheme`, matching
Streamlit's default follow-system behavior. All injected HTML is built
from static strings and integers; untrusted text goes through
`html.escape` or `st.text` only.

Run with:
    streamlit run dashboard/app.py

Override data sources for testing via env vars:
    CHAT_DB_SOURCE=path/to/fixture.db TRIAGE_DB_PATH=path/to/scratch.db \
        streamlit run dashboard/app.py
"""

import html
import os
import sys
from collections import Counter
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
    record_feedback,
    snooze_result,
)

CHAT_DB_SOURCE = Path(os.environ.get("CHAT_DB_SOURCE", str(REAL_CHAT_DB_SOURCE)))
TRIAGE_DB_PATH = Path(os.environ.get("TRIAGE_DB_PATH", "./data/triage.db"))

LIVE_CHECK_TTL_SECONDS = 60

# Urgency display metadata. Keys double as CSS class suffixes, so any
# unexpected value from the DB is coerced to a known key before use.
URGENCY_META = {
    "high": {"emoji": "☄️", "label": "High"},
    "med": {"emoji": "🌟", "label": "Medium"},
    "low": {"emoji": "🌙", "label": "Low"},
}

# All colors below were contrast-checked (WCAG >= 4.5:1 for text on its
# surface, both modes). The starfield/nebula layers are decorative only;
# urgency is always emoji + label, never color alone.
THEME_CSS = """
<style>
:root {
  --mw-font: ui-rounded, "SF Pro Rounded", "Hiragino Maru Gothic ProN",
             "Arial Rounded MT Bold", "Trebuchet MS", system-ui, sans-serif;
  --mw-bg: #f7f3ff;
  --mw-glow-a: rgba(255, 158, 207, 0.22);
  --mw-glow-b: rgba(141, 107, 255, 0.16);
  --mw-card: #ffffff;
  --mw-card-border: #eae1fb;
  --mw-ink: #33254d;
  --mw-ink-soft: #7a6d99;
  --mw-star: rgba(141, 107, 255, 0.55);
  --mw-star-2: rgba(255, 143, 199, 0.55);
  --mw-high: #ff8fc7; --mw-high-ink: #c22a72; --mw-high-bg: #ffe3f1;
  --mw-med:  #f2b968; --mw-med-ink:  #96590a; --mw-med-bg:  #fff1d6;
  --mw-low:  #a9aeff; --mw-low-ink:  #5457c9; --mw-low-bg:  #e9e9ff;
  --mw-grad: linear-gradient(92deg, #8d6bff, #ff6fbf 55%, #ffb56b);
  --mw-shadow: 0 8px 24px rgba(120, 86, 255, 0.10);
  --mw-shadow-hover: 0 12px 30px rgba(120, 86, 255, 0.16);
  --mw-btn-hover-bg: #f3edff;
  --mw-code-bg: #efe8ff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --mw-bg: #120e24;
    --mw-glow-a: rgba(255, 111, 191, 0.14);
    --mw-glow-b: rgba(141, 107, 255, 0.14);
    --mw-card: #1b1633;
    --mw-card-border: #332a58;
    --mw-ink: #ece7ff;
    --mw-ink-soft: #a79ecf;
    --mw-star: rgba(236, 231, 255, 0.6);
    --mw-star-2: rgba(255, 158, 207, 0.6);
    --mw-high-ink: #ff9ecf; --mw-high-bg: #3b2748;
    --mw-med-ink:  #f2b968; --mw-med-bg:  #392d3a;
    --mw-low-ink:  #a9aeff; --mw-low-bg:  #2f2b50;
    --mw-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --mw-shadow-hover: 0 12px 30px rgba(0, 0, 0, 0.5);
    --mw-btn-hover-bg: #241d44;
    --mw-code-bg: #2a2250;
  }
}

.stApp {
  background:
    radial-gradient(60rem 40rem at 110% -10%, var(--mw-glow-a), transparent 60%),
    radial-gradient(50rem 35rem at -20% 110%, var(--mw-glow-b), transparent 60%),
    var(--mw-bg);
  background-attachment: fixed;
  font-family: var(--mw-font);
}
/* twinkling starfield, purely decorative */
.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image:
    radial-gradient(1.5px 1.5px at 25px 35px, var(--mw-star), transparent),
    radial-gradient(1px 1px at 120px 90px, var(--mw-star-2), transparent),
    radial-gradient(1.5px 1.5px at 200px 160px, var(--mw-star), transparent),
    radial-gradient(1px 1px at 70px 210px, var(--mw-star-2), transparent),
    radial-gradient(1px 1px at 180px 40px, var(--mw-star), transparent),
    radial-gradient(1.5px 1.5px at 240px 240px, var(--mw-star-2), transparent);
  background-size: 280px 280px;
  animation: mw-twinkle 7s ease-in-out infinite alternate;
}
@keyframes mw-twinkle {
  from { opacity: 0.5; }
  to   { opacity: 1; }
}
[data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { background: var(--mw-grad); }

.stApp p, .stApp div, .stApp span, .stApp label, .stApp button, .stApp input {
  font-family: var(--mw-font);
}
.stApp p, .stApp label { color: var(--mw-ink); }

/* hero */
.mw-hero { position: relative; text-align: center; padding: 0.8rem 0 0.2rem; }
.mw-hero-title { font-size: 2.4rem; font-weight: 800; margin: 0; line-height: 1.15; color: var(--mw-ink); }
.mw-hero-title .mw-grad {
  background: var(--mw-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}
.mw-hero-sub { color: var(--mw-ink-soft); letter-spacing: 0.08em; margin-top: 0.15rem; font-size: 0.95rem; }
.mw-spark { position: absolute; font-size: 0.9rem; color: var(--mw-star); animation: mw-float 5s ease-in-out infinite; }
.mw-spark-a { top: 0.2rem; left: 16%; }
.mw-spark-b { top: 2.1rem; right: 14%; animation-delay: 1.3s; font-size: 1.2rem; color: var(--mw-star-2); }
.mw-spark-c { bottom: 0.1rem; left: 26%; animation-delay: 2.6s; font-size: 0.7rem; }
@keyframes mw-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

/* stat tiles */
.mw-stats { display: flex; gap: 0.7rem; justify-content: center; flex-wrap: wrap; margin: 0.9rem 0 0.4rem; }
.mw-stat {
  background: var(--mw-card);
  border: 1px solid var(--mw-card-border);
  border-radius: 16px;
  padding: 0.5rem 1.15rem 0.55rem;
  text-align: center;
  box-shadow: var(--mw-shadow);
  min-width: 5.4rem;
}
.mw-stat-num { display: block; font-size: 1.45rem; font-weight: 800; color: var(--mw-ink); }
.mw-stat-high .mw-stat-num { color: var(--mw-high-ink); }
.mw-stat-med  .mw-stat-num { color: var(--mw-med-ink); }
.mw-stat-low  .mw-stat-num { color: var(--mw-low-ink); }
.mw-stat-label { font-size: 0.72rem; color: var(--mw-ink-soft); letter-spacing: 0.06em; }

/* triage cards (keyed containers: st-key-card-<urgency>-<id>) */
div[class*="st-key-card-"] {
  background: var(--mw-card);
  border: 1px solid var(--mw-card-border);
  border-left: 6px solid var(--mw-card-border);
  border-radius: 20px;
  padding: 1.1rem 1.3rem 1.2rem;
  margin-bottom: 0.4rem;
  box-shadow: var(--mw-shadow);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
div[class*="st-key-card-"]:hover { transform: translateY(-2px); box-shadow: var(--mw-shadow-hover); }
div[class*="st-key-card-high-"] { border-left-color: var(--mw-high); }
div[class*="st-key-card-med-"]  { border-left-color: var(--mw-med); }
div[class*="st-key-card-low-"]  { border-left-color: var(--mw-low); }

.mw-card-head { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; }
.mw-pill {
  display: inline-flex; align-items: center; gap: 0.32rem;
  padding: 0.16rem 0.75rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 700; letter-spacing: 0.03em;
}
.mw-pill-high { background: var(--mw-high-bg); color: var(--mw-high-ink); border: 1px solid var(--mw-high); }
.mw-pill-med  { background: var(--mw-med-bg);  color: var(--mw-med-ink);  border: 1px solid var(--mw-med); }
.mw-pill-low  { background: var(--mw-low-bg);  color: var(--mw-low-ink);  border: 1px solid var(--mw-low); }
.mw-age { color: var(--mw-ink-soft); font-size: 0.82rem; }
.mw-thread-name { font-size: 1.18rem; font-weight: 800; color: var(--mw-ink); margin-top: 0.55rem; }

/* reasoning text (st.text keeps it plain/escaped) */
[data-testid="stText"] {
  font-family: var(--mw-font) !important;
  white-space: pre-wrap !important;
  color: var(--mw-ink);
  font-size: 0.93rem;
  line-height: 1.55;
}
[data-testid="stCaptionContainer"] p { color: var(--mw-ink-soft) !important; }

/* buttons — pill-shaped, pastel hover */
button[data-testid^="stBaseButton"],
button[data-testid="stPopoverButton"] {
  border-radius: 999px !important;
  border: 1.5px solid var(--mw-card-border) !important;
  background: var(--mw-card) !important;
  color: var(--mw-ink) !important;
  font-weight: 600;
  transition: transform 0.12s ease, border-color 0.12s ease, background 0.12s ease;
}
button[data-testid^="stBaseButton"]:hover,
button[data-testid="stPopoverButton"]:hover {
  border-color: var(--mw-low) !important;
  background: var(--mw-btn-hover-bg) !important;
  color: var(--mw-ink) !important;
  transform: translateY(-1px);
}
button[data-testid^="stBaseButton"]:focus-visible,
button[data-testid="stPopoverButton"]:focus-visible {
  outline: 2px solid var(--mw-low) !important;
  outline-offset: 2px;
}

[data-testid="stPopoverBody"] {
  border-radius: 18px !important;
  border: 1px solid var(--mw-card-border) !important;
  background: var(--mw-card) !important;
  box-shadow: var(--mw-shadow-hover) !important;
}

/* untriaged banner */
.mw-banner {
  background: var(--mw-low-bg);
  border: 1.5px dashed var(--mw-low);
  border-radius: 16px;
  padding: 0.75rem 1.05rem;
  color: var(--mw-ink);
  font-size: 0.92rem;
  margin: 0.6rem 0 0.9rem;
}
.mw-banner code {
  background: var(--mw-code-bg);
  border-radius: 8px;
  padding: 0.08rem 0.4rem;
  font-size: 0.85em;
  color: var(--mw-ink);
}

/* empty state */
.mw-empty { text-align: center; padding: 2.6rem 1rem 3rem; }
.mw-empty-art { font-size: 3.4rem; line-height: 1; animation: mw-float 5s ease-in-out infinite; }
.mw-empty-title { font-size: 1.35rem; font-weight: 800; color: var(--mw-ink); margin-top: 1rem; }
.mw-empty-sub { color: var(--mw-ink-soft); margin-top: 0.3rem; letter-spacing: 0.04em; }

@media (prefers-reduced-motion: reduce) {
  .stApp::before, .mw-spark, .mw-empty-art,
  div[class*="st-key-card-"], button[data-testid^="stBaseButton"] {
    animation: none !important;
    transition: none !important;
  }
}
</style>
"""

HERO_HTML = """
<div class="mw-hero">
  <span class="mw-spark mw-spark-a">✦</span>
  <span class="mw-spark mw-spark-b">✧</span>
  <span class="mw-spark mw-spark-c">✦</span>
  <h1 class="mw-hero-title">📬 <span class="mw-grad">Message Triage</span></h1>
  <div class="mw-hero-sub">your cosmic inbox companion ✧˖ °</div>
</div>
"""

EMPTY_STATE_HTML = """
<div class="mw-empty">
  <div class="mw-empty-art">🐈‍⬛🪐</div>
  <div class="mw-empty-title">All clear — the cosmos is quiet</div>
  <div class="mw-empty-sub">nothing flagged right now · go touch some stardust ✧</div>
</div>
"""


def _escape(text) -> str:
    """HTML-escape untrusted text for embedding in our static markup.

    Escaping covers <, >, &, and quotes, so untrusted content can never
    form an element, attribute, or link — the F2 guarantee (no injected
    links or image fetches) holds even inside unsafe_allow_html blocks.
    """
    return html.escape(str(text), quote=True)


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


def render_stats(flagged: list[dict]):
    counts = Counter(r["urgency"] for r in flagged)
    st.markdown(
        '<div class="mw-stats">'
        f'<div class="mw-stat"><span class="mw-stat-num">{len(flagged)}</span>'
        '<span class="mw-stat-label">flagged</span></div>'
        f'<div class="mw-stat mw-stat-high"><span class="mw-stat-num">{counts.get("high", 0)}</span>'
        '<span class="mw-stat-label">☄️ high</span></div>'
        f'<div class="mw-stat mw-stat-med"><span class="mw-stat-num">{counts.get("med", 0)}</span>'
        '<span class="mw-stat-label">🌟 medium</span></div>'
        f'<div class="mw-stat mw-stat-low"><span class="mw-stat-num">{counts.get("low", 0)}</span>'
        '<span class="mw-stat-label">🌙 low</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_snooze_controls(thread_id: int):
    with st.popover("💤 Snooze"):
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


def render_feedback_controls(result: dict):
    """Collect derived quality feedback; never store message or reasoning text."""
    thread_id = result["thread_id"]
    common = {
        "db_path": TRIAGE_DB_PATH,
        "thread_id": thread_id,
        "result_computed_at": result["computed_at"],
        "model_urgency": result["urgency"],
    }

    st.caption("Was this assessment useful?")
    correct_col, wrong_col, irrelevant_col = st.columns(3)
    with correct_col:
        if st.button("Correct", key=f"feedback_correct_{thread_id}"):
            record_feedback(
                **common,
                urgency_correct=True,
                corrected_urgency=None,
                reply_worthy=True,
            )
            st.rerun()
    with wrong_col:
        with st.popover("Wrong urgency"):
            corrected = st.selectbox(
                "Correct urgency",
                ["low", "med", "high"],
                key=f"feedback_urgency_{thread_id}",
            )
            if st.button("Save correction", key=f"feedback_save_{thread_id}"):
                record_feedback(
                    **common,
                    urgency_correct=False,
                    corrected_urgency=corrected,
                    reply_worthy=True,
                )
                st.rerun()
    with irrelevant_col:
        if st.button("Not reply-worthy", key=f"feedback_irrelevant_{thread_id}"):
            record_feedback(
                **common,
                urgency_correct=None,
                corrected_urgency=None,
                reply_worthy=False,
            )
            st.rerun()


def render_card(result: dict, hours_by_thread: dict):
    thread_id = result["thread_id"]
    # Coerce to a known key: it feeds CSS class names and the keyed container.
    urgency = result["urgency"] if result["urgency"] in URGENCY_META else "low"
    meta = URGENCY_META[urgency]
    hours = hours_by_thread.get(thread_id)
    age_label = _format_hours(hours) if hours is not None else "unknown"

    with st.container(key=f"card-{urgency}-{thread_id}"):
        # thread_name is HTML-escaped and reasoning rendered as plain text —
        # both are untrusted-content-derived; live markup would let an
        # injected message create links or exfiltrating image fetches (F2).
        st.markdown(
            '<div class="mw-card-head">'
            f'<span class="mw-pill mw-pill-{urgency}">{meta["emoji"]} {meta["label"]}</span>'
            f'<span class="mw-age">unanswered {_escape(age_label)}</span>'
            "</div>"
            f'<div class="mw-thread-name">{_escape(result["thread_name"])}</div>',
            unsafe_allow_html=True,
        )

        if result["reasoning"]:
            st.text(result["reasoning"])
        else:
            st.caption("🛰️ Reasoning no longer available — past the 14-day retention window.")
        if result["suggest_nudge"]:
            st.caption("💫 Suggested: remind me to reply")
        if result["needs_review"]:
            st.caption("🔭 Needs review: the assessment was uncertain")

        render_feedback_controls(result)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Dismiss", key=f"dismiss_{thread_id}"):
                dismiss_result(TRIAGE_DB_PATH, thread_id)
                st.rerun()
        with col2:
            render_snooze_controls(thread_id)


def main():
    st.set_page_config(page_title="Message Triage", page_icon="🪐", layout="centered")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(HERO_HTML, unsafe_allow_html=True)

    if st.button("🔄 Refresh"):
        _live_unanswered_candidates.clear()
        st.rerun()

    resolver = _contact_resolver()
    contacts_enabled = contact_name_controls(resolver)
    flagged, hours_by_thread, untriaged_count = load_dashboard_data(
        resolver if contacts_enabled else None
    )

    if untriaged_count:
        st.markdown(
            f'<div class="mw-banner">🛰️ {untriaged_count} unanswered thread(s) '
            "haven't been triaged yet — run "
            "<code>python scripts/run_triage.py --call</code> to assess them.</div>",
            unsafe_allow_html=True,
        )

    if not flagged:
        st.markdown(EMPTY_STATE_HTML, unsafe_allow_html=True)
        return

    render_stats(flagged)

    for result in flagged:
        render_card(result, hours_by_thread)


if __name__ == "__main__":
    main()
