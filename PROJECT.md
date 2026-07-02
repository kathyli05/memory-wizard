# Project: Personal Triage Agent

## Purpose
A privacy-conscious agentic system that triages unanswered messages and
organizes screenshots, built to (a) help manage ADHD-related friction around
responsiveness and information overload, and (b) demonstrate applied
Socially Responsible Computing principles: privacy-by-design, data
minimization, user autonomy, and transparency.

## Thesis
An agent architecture for externalized attention and memory — two intake
channels (messages, screenshots) feeding a shared triage/categorization
core, governed by consistent privacy and transparency principles. Core
design question: how do you let an agent make judgment calls on someone's
behalf (what's urgent, what's worth keeping) without being either useless
(too conservative) or paternalistic (silently deciding for them)?

## Shared architecture (both channels use this)
- Local SQLite DB (`./data/triage.db`) for derived signals/metadata only
- Claude API for triage/categorization judgment calls, structured JSON output
- Streamlit dashboard, single app with tabs per channel
- Retention/deletion policy for raw content
- Transparency layer: always show reasoning for any suggestion

## Hard constraints (apply everywhere)
- NEVER modify, write to, delete from, move, or rename original data
  sources (`chat.db` and its `-wal`/`-shm` sidecars, the Photos library) —
  read-only access to the source only, with all real work done on a copy.
  This applies even if a request seems to call for it "just this once."
- NEVER auto-send messages or auto-delete photos — all actions require
  explicit user confirmation
- Minimize what's sent to the Claude API per call — only relevant context,
  not full history/full-res duplicates
- Flag ambiguous decisions rather than silently choosing
- Tech stack: Python 3, sqlite3 (stdlib), anthropic SDK, streamlit, osxphotos

---

## Channel 1: Messages

### Pipeline
1. Ingestion: copy `~/Library/Messages/chat.db` to `./data/chat_copy.db`,
   parse via sqlite3 (timestamps are nanoseconds since 2001 epoch — convert)
2. Contact profiles: per-thread median response latency, message frequency
   (90 days), initiation ratio — stored as derived signals only
3. Unanswered thread detection: deterministic, no AI — last message
   is_from_me=0 and older than configurable threshold (default 24h)
4. Triage agent: Claude API call per candidate thread, sending contact
   profile + last 5 messages only. Structured output: urgency (low/med/high),
   reasoning, suggest_nudge (bool). Model: claude-sonnet-4-6
5. Dashboard tab: flagged threads sorted by urgency, reasoning shown,
   buttons for dismiss/snooze
6. Retention: raw message text deleted from our DB after 14 days
   (configurable), only derived signals persist

### Explicit scope limit
No draft-generation agent — drafting replies on someone's behalf reads as
impersonal and disrespectful to the relationship. Triage surfaces urgency
and reasoning; the user writes their own replies.

---

## Channel 2: Screenshots

### Pipeline
1. Ingestion: osxphotos pulls screenshots + timestamps + asset IDs from
   Photos library (read-only)
2. Categorization: each image → Claude vision call → structured output:
   category (place/product/quote/event/recipe/article/other), extracted_text,
   description, tags, expires_at (nullable — event/deadline/ticket dates)
3. Storage: derived metadata only (category, tags, description, expires_at,
   Photos asset reference) — never duplicate full-res images
4. Search: natural language query → Claude ranks against stored
   descriptions/tags → top 5 matches with reasoning
5. Expiry surfacing: weekly job flags items past expires_at as "probably stale"
6. Deletion suggestions (screenshots/junk ONLY, not general photo library):
   - Candidates: near-duplicate bursts, expired items, old+low-value
     categories never revisited
   - NEVER auto-delete — dashboard shows candidate + reasoning, user
     accepts/rejects, deletion itself is manual (dashboard points to asset)
7. Feedback loop: every accept/reject logged with the suggestion's features
   (category, reason, age). Before generating new suggestions, pull past
   accept/reject rates per category and include as context so Claude
   calibrates. This is prompt-conditioning on aggregated history, NOT model
   fine-tuning — document this distinction explicitly in the README.
8. Scheduling: weekly via launchd, manually triggerable
9. Dashboard tab: browse-by-category, search bar, stale/expiring section,
   cleanup suggestions section with accept/reject buttons

### Explicit scope limit
Deletion suggestions apply to screenshots/junk only. Do NOT extend to
general photo library (people/trips/memories) without deliberate redesign —
too emotionally high-stakes for an automated suggestion pattern.
