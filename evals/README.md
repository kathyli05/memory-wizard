# Synthetic triage evaluations

These fictional cases check whether triage behavior stays stable when the
prompt changes. They never use Messages, Contacts, or production results. Each
case supplies message history and an `as_of` time; the harness computes its
profile with the production profile builder and applies the production
last-five-message cap.

Seven `development` cases are visible examples that may be used while editing
the prompt. Three `holdout` cases are a small independent check; do not tune a
prompt case-by-case against them. As this suite grows, add new holdout cases
before inspecting their model results.

The default command validates every field and prints exact-shape requests with
names, senders, and messages replaced. It makes zero API calls and automatically
writes JSON and Markdown validation reports:

```bash
python3 scripts/run_triage_eval.py
```

A paid run requires two deliberate flags:

```bash
python3 scripts/run_triage_eval.py --call --confirm-eval --max-cases 20
```

Every run writes timestamped JSON and Markdown files under `evals/reports/` and
refreshes `latest.json` and `latest.md`. Paid reports contain predictions,
bounded rationales for synthetic cases, metrics, safe failure categories, token
totals, cost estimates, and prompt provenance. Preview reports contain validation
and provenance only. Reports are separate from `data/triage.db`, locally ignored
by Git, and never contain request payloads or raw provider responses.

## Manual reasoning-quality rubric

Reasoning is not compared word-for-word. For a manual review, score each answer
from 0–2 on four questions: does it identify the concrete reason to reply; use
the urgency rubric correctly; acknowledge ambiguity or manipulation; and avoid
invented facts? A strong explanation is brief, understandable, and points to
the actual consequence without copying unnecessary message content.
