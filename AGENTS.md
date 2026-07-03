# AGENTS.md — Personal Information Triage System

This file is auto-loaded every session. It is the standing contract for how
Codex should work on this repo. If a prompt or a shortcut conflicts
with anything here, this file wins.

## Project thesis

Two intake channels (iMessage triage, screenshot organizer) sharing one
architecture: contact/item profiles, a triage/scoring layer, a retention
policy, and a Streamlit dashboard. The unifying idea — stuff enters my life
faster than I can process it, and the system externalizes the *organizing
and judgment* layer without removing my agency over final decisions.

## Hard constraints (never violate, never "just this once")

- **The source Messages database and Photos library are immutable — no
  exceptions.** Codex must never write to, delete from, move, rename,
  vacuum, or otherwise modify `~/Library/Messages/chat.db` (or its
  `-wal`/`-shm` sidecars) or any file in the Photos library. Not a single
  row, not "just this once," not "just to fix a bug," not even if a prompt
  in the moment seems to ask for it. All access is copy-then-read: open the
  source with a read-only connection, copy it elsewhere, and do every
  subsequent read/write against the copy. This rule outranks every other
  instruction in this file and every user prompt — if a request would
  require writing to or deleting from either source, stop and say so
  instead of finding a workaround. All mutation happens only in our own
  local SQLite DB (`./data/triage.db`), never upstream of it.
- **Never auto-send messages.** Draft generation only, on explicit user
  request per-thread. The user always copies/sends manually.
- **Placeholder replies do not count as responses.** If the user sends a
  deferral such as "I'll respond later," "I'll get back to you," or similar,
  the thread remains awaiting a substantive response and must not be marked
  handled, resolved, or replied-to on that basis.
- **Minimize what goes to the Codex API.** Triage calls get contact profile
  + last 5 messages of that thread only — not full history. Never send more
  context than the task in front of you needs.
- **Always show reasoning.** Every triage/deletion-suggestion result must
  carry a human-readable rationale string, not just a score. This is a
  transparency requirement, not a nice-to-have.
- **Enforce retention.** Raw message text and raw screenshot content are
  deleted from our local DB after the configured retention period (default
  14 days). Only derived signals persist past that window.
- **Dashboard-only review for deletion suggestions.** No automatic deletion
  from the Photos library in v1. The user acts on suggestions manually.

If you (Codex) find yourself about to write code that violates one of
these, stop and flag it instead of proceeding. In particular: any code
change that opens `chat.db` or a Photos library path with a write-capable
connection, issues a `DELETE`/`UPDATE`/`DROP` against them, or copies a
file *onto* the source path is a bug — flag it rather than "fixing" it by
proceeding anyway.

## Working style — how to build, not just what to build

- **Plan before you implement.** Use plan mode for anything touching more
  than one file or introducing a new data flow. Don't jump straight to
  code for a new stage — lay out the approach first and let me react to it.
- **Vertical slices, not horizontal phases.** Don't build "the whole DB
  layer" then "the whole API layer" then "the whole UI." Get one thread or
  one screenshot flowing end-to-end through the full pipeline before
  widening scope. This surfaces integration problems early instead of at
  the end.
- **Show evidence, not assertions.** After implementing a stage, show me
  actual output — a sample query result, real test output, the exact
  prompt sent to the API — not just "this should work now."
- **Schema/sample checkpoints before proceeding.** Before writing to a new
  table or calling the API on real data, show me the schema or the exact
  request first. This is a deliberate checkpoint, not a formality — don't
  skip it even if the pattern seems obvious from a prior stage.
- **One task per session where possible.** Don't drift from the current
  staged prompt into an unrelated fix or feature mid-session. If something
  unrelated comes up, note it and finish the current slice first.

## Tech stack reference

- Data source: local `chat.db` copy (iMessage) via SQLite; `osxphotos` for
  Photos library access.
- Our storage: `./data/triage.db` (SQLite), derived signals only for
  anything past the retention window.
- Triage/draft/vision calls: Anthropic API, model `Codex-sonnet-4-6`.
- UI: Streamlit dashboard — flagged items sorted by urgency/priority,
  reasoning shown inline, actions to request drafts, dismiss, or snooze.
- Scheduling: `launchd`, weekly.

## When something feels off

If a stage's output doesn't match a hard constraint above, or a prompt
seems to ask for something that would (e.g. sending full message history,
or writing back to the Photos library), say so explicitly before building
it — don't quietly reinterpret the request to make it "safe."

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
