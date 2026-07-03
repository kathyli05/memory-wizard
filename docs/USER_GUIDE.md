# Triage System — User Guide

Everything you can run, in plain English. Four small scripts and one dashboard.

**Safe by default:** nothing touches the Claude API or writes results unless a
specific flag says so. Without `--call` (or `--write` for profiles), every
command is a preview — no cost, nothing sent, nothing saved.

---

## How the pieces fit

Your messages flow left to right; each script owns one step.

1. **Read** — copy `chat.db` read-only and parse messages (`scripts/ingest.py`)
2. **Profiles** — build a profile per contact/thread (`scripts/build_contact_profiles.py`)
3. **Triage** — find who needs a reply and score urgency (`scripts/run_triage.py`)
4. **Review** — act on it in the dashboard (`dashboard/app.py`)

Your real Messages database is never modified — the system copies it first and
reads the copy. Results live in `./data/triage.db`. Raw message text is
auto-deleted after 14 days; only scores and reasoning persist.

---

## Just tell me what to run

The five things you'll actually do, most common first.
🟢 = free & offline · 🟡 = sends the last 5 messages of a thread to Claude and costs money.

**See who I still owe a reply — without spending anything** 🟢

```
python3 scripts/run_triage.py --lookback-days 5
```

**Actually triage new threads (the real run)** 🟡

```
python3 scripts/run_triage.py --lookback-days 5 --call
```

Picks up brand-new threads and writes results to `triage.db`.

**Re-score threads I've triaged before (does *not* add new ones)** 🟡

```
python3 scripts/run_triage.py --lookback-days 5 --retriage-all --call --confirm-retriage-all
```

**Refresh contact profiles** 🟢

```
python3 scripts/build_contact_profiles.py --write
```

**Open the dashboard to review, snooze, or draft replies** 🟢

```
streamlit run dashboard/app.py
```

> **To see conversations you haven't replied to at all — even ones under 24
> hours old — use the plain `--call` run (second recipe).** The
> `--retriage-all` command deliberately skips any thread that was never triaged
> before, which is why fresh messages don't show up in that mode.

---

## Full command reference

Defaults are noted per flag. You only pass a flag when you want to change the
default.

### `scripts/run_triage.py`

The main event: find unanswered threads and score how urgently each needs a
reply. Runs a free redacted preview unless you add `--call`.

| Flag | What it does |
|---|---|
| `--call` | Actually contact Claude and save results. Omit it and nothing is sent, nothing is stored — you just see a preview. *(default: preview only)* |
| `--lookback-days N` | Ignore threads whose last message is *older* than N days. An age **ceiling**, not a floor — recent messages always pass. Pass a big number to include ancient threads. *(default: 150)* |
| `--threshold-hours N` | Only flag a thread once it's gone unanswered at least N hours. *(default: 0 — even a 5-minute-old unread reply counts; this is already the "show everything I haven't answered" behavior)* |
| `--retriage-all` | Re-score *every* thread you've triaged before. Skips threads never triaged, so it won't surface new conversations. With `--call` it also requires `--confirm-retriage-all`. |
| `--retriage-one` | Same idea, but only the single oldest previously-triaged thread — one API call at most. A cheap spot-check. |
| `--confirm-retriage-all` | Safety confirmation. Required only when combining `--retriage-all` with `--call`. |
| `--max-calls N` | Hard cap on how many threads get processed — a budget guard for previews and real calls. *(default: no cap)* |
| `--dest PATH` | Which results database to read from and write to. *(default: ./data/triage.db)* |
| `--source PATH` | The Messages database to copy from. *(default: ~/Library/Messages/chat.db)* |
| `--copy-dest PATH` | Where the temporary read-only copy briefly lives. *(default: ./data/chat_copy.db)* |
| `--keep-copy` | Don't delete that temporary copy afterward. *(default: copy is deleted)* |

**Three modes, one script.** With no re-triage flag it's a *regular run* —
anything new or changed since last time. `--retriage-one` and `--retriage-all`
instead revisit threads already in the database.

### `scripts/build_contact_profiles.py`

Compute one profile per contact/thread. Previews by default; add `--write` to
save. Never calls the API.

| Flag | What it does |
|---|---|
| `--write` | Save the profiles to the database. *(default: preview only, nothing written)* |
| `--dest PATH` | Where to write profiles (only used with `--write`). *(default: ./data/triage.db)* |
| `--source PATH` | Messages database to copy from. *(default: ~/Library/Messages/chat.db)* |
| `--copy-dest PATH` | Temporary copy location. *(default: ./data/chat_copy.db)* |
| `--keep-copy` | Keep the temporary copy afterward. *(default: deleted)* |

### `scripts/ingest.py`

A sanity check: copy `chat.db`, parse it, print a few messages so you can
confirm reading works. No API, saves nothing.

| Flag | What it does |
|---|---|
| `--sample N` | How many parsed messages to print. *(default: 10)* |
| `--source PATH` | Messages database to copy from. *(default: ~/Library/Messages/chat.db)* |
| `--copy-dest PATH` | Temporary copy location. *(default: ./data/chat_copy.db)* |
| `--keep-copy` | Keep the temporary copy afterward. *(default: deleted)* |

### `scripts/run_triage_eval.py`

Quality check for the triage model, run against **synthetic test cases only** —
never your real messages. Validates for free; add `--call` to score them for
real.

| Flag | What it does |
|---|---|
| `--call` | Run the synthetic cases through Claude and produce accuracy metrics. Requires `--confirm-eval`. *(default: free validation + redacted preview)* |
| `--confirm-eval` | Required confirmation when using `--call`. |
| `--max-cases N` | Only run the first N test cases. *(default: all of them)* |
| `--cases PATH` | The test-case file. *(default: evals/triage_cases.jsonl)* |
| `--report-dir PATH` | Where reports are written. *(default: evals/reports)* |

---

## Good to know

- **Safe by default.** No script sends data to Claude or writes results unless
  you pass `--call` (or `--write` for profiles). Without them you only ever get
  a preview.
- **Nothing is auto-sent.** The dashboard can draft replies on request, but you
  always copy and send them yourself.
- **Minimal data leaves your machine.** A triage call includes the contact's
  profile and only the last 5 messages of that one thread — never full history.
- **Your Messages are read-only.** The real `chat.db` is copied first and never
  modified.
- **Results expire.** Raw message text is scrubbed from `triage.db` after 14
  days; scores and reasoning stay.
- **Model:** `claude-sonnet-4-6`. Every triage result comes with a written
  rationale, not just a number.

> **Tip:** whenever you're unsure what a command will do, run it without
> `--call` first. That always shows a safe preview of exactly what would happen.
