# Project: Personal Message Triage Agent

## Purpose
A privacy-conscious agentic system that triages unanswered iMessages,
built to (a) help me manage ADHD-related response delay and (b) demonstrate
applied Socially Responsible Computing principles: privacy-by-design,
data minimization, user autonomy, and transparency.

## Architecture
1. Ingestion: read-only copy of ~/Library/Messages/chat.db, parsed via sqlite3
2. Contact profiles: derived signals only (response latency, frequency,
   initiation ratio) — stored in our own local SQLite DB, separate from Apple's
3. Triage agent: Claude API call per unanswered thread, structured JSON output
   (urgency, reasoning, suggest_nudge)
4. Draft agent: only invoked on user request, generates 2-3 reply options
   in user's own tone, never auto-sends
5. Dashboard: Streamlit, shows flagged threads + reasoning (transparency),
   buttons for draft/dismiss/snooze
6. Retention policy: raw message text auto-deleted from our DB after N days;
   only derived signals persist

## Hard constraints
- NEVER modify or write to the original chat.db — copy it first, work only
  on the copy
- NEVER auto-send messages — draft generation requires explicit user action
- Minimize what's sent to the Claude API per call — only relevant thread
  context, not full history
- All design decisions should be defensible from a privacy/ethics standpoint —
  flag any tradeoff you're not sure about rather than silently choosing

## Tech stack
Python 3, sqlite3 (stdlib), anthropic SDK, streamlit

## Channel 2 extension: Expiry detection + deletion suggestions

### Purpose
Surface time-sensitive screenshots (events, deadlines, tickets) before they're
stale, and suggest screenshot/junk deletion candidates on a recurring basis —
with an adaptive feedback loop, never auto-deleting.

### Expiry detection (deterministic, extends categorization step)
- During categorization (Prompt 9), also extract `expires_at` if the
  screenshot has an inherent date (event, sale, deadline, boarding pass)
- Weekly job surfaces items where expires_at has passed, flagged as
  "probably stale" in dashboard

### Deletion suggestions (screenshots/junk only, NOT full photo library)
- Candidates: duplicates/near-duplicate bursts, low-value categories
  (memes, expired flyers), old + never revisited
- NEVER auto-delete. Always surface in dashboard for accept/reject.
- Log every accept/reject decision with the features that drove the original
  suggestion (category, age, duplicate-of, expired-flag) to our local DB

### Feedback loop (prompt-conditioning, not model fine-tuning)
- Before generating new suggestions, pull a summary of past accept/reject
  rates per feature/category from our DB
- Include this summary in the prompt to Claude so it calibrates suggestions
  (e.g. "user rejects meme-category suggestions 80% of the time, be more
  conservative there") — this is in-context adaptation, explicitly NOT
  training a separate classifier. Document this distinction in the README.

### Scheduling
- Runs weekly via launchd (macOS scheduler), manually triggerable too
- Hard constraint: scope to screenshots/junk only. Do not extend deletion
  suggestions to general photo library (people/trips/events) without
  explicit redesign — too high-stakes for this pattern.
