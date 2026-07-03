# How the triage system works

The system finds unanswered conversations, sends only a small amount of
relevant context for assessment, records useful operational numbers without
keeping private request data, and has a fictional test set for checking behavior
before spending money or touching real conversations.

## The end-to-end flow

1. The program opens the real Messages database read-only and makes a temporary
   working copy. All parsing happens against that copy. The copy is deleted when
   the run finishes.
2. It finds conversations where someone else sent the latest message and the
   user has not answered within the configured time window.
3. It filters obvious automated messages, such as one-time codes, and skips
   conversations that have not changed since their last assessment.
4. For each remaining conversation, it builds a small contact behavior summary
   and selects no more than the last five messages.
5. Preview mode replaces names, senders, and message bodies with placeholders.
   It shows the exact request structure but does not create an API client, spend
   tokens, or write call records.
6. In call mode, each conversation is assessed independently. A failure for one
   conversation does not discard successful results for the others.
7. Successful assessments are saved for the dashboard. The dashboard shows the
   urgency, whether a reminder may help, whether a person should review an
   ambiguous result, and a plain-English explanation.
8. Explanation text is cleared after 14 days because it may paraphrase a private
   message. Longer-lived fields are limited to derived labels and operational
   counts.

The system never writes back to Messages, accesses Contacts in this flow,
automatically sends a reply, or deletes a photo.

## Why prompt versions and fingerprints both exist

The **prompt version** is a readable label such as `triage-v2`. It is useful in
conversation, release notes, and dashboards.

The **fingerprint** is a SHA-256 checksum calculated from the parts that define
the assessment contract:

- the fixed instructions;
- the required response fields and allowed values;
- the model name;
- fixed request settings such as the output limit and required tool choice.

Runtime data is deliberately excluded. Names, contact summaries, senders, and
messages cannot affect the fingerprint. This means two runs using the same
contract have the same fingerprint, while even a small contract change creates
a different one.

The model and prompt version are separate because changing the model is not the
same experiment as changing the instructions. Each successful result records
the run ID, readable prompt version, fingerprint, and model, so its behavior can
be traced to the exact contract that produced it.

## What observability means here

Observability answers operational questions such as:

- How many conversations were eligible and attempted?
- How many succeeded or failed?
- How long did each attempt take?
- How many input, output, cache-write, and cache-read tokens were used?
- What was the estimated cost under the pricing table used at that time?
- Which prompt contract and model produced the result?

It does **not** mean recording everything. The call log excludes request bodies,
messages, names, senders, explanations, model responses, and raw provider error
messages. A failed call stores only a category such as `timeout`, `rate_limit`,
or `invalid_response`.

There are two derived-only tables:

- `triage_runs` contains one summary row for an intentional call-mode run,
  including zero-candidate runs.
- `triage_call_log` contains one row for each API attempt. Preview requests do
  not appear here because no API attempt occurred.

Raw token counts are the durable facts. Dollar cost is an estimate calculated
from a separately versioned pricing configuration. Keeping the pricing version
means an old estimate can still be understood after prices change.

## Failure behavior

Each thread is its own unit of work. If the second of five calls fails, the
first, third, fourth, and fifth may still succeed and be saved. The run summary
will show five attempts, four successes, and one failure. The failed row gets a
safe error category but no sensitive exception message.

Only successful assessments enter `triage_results`. This preserves the previous
behavior: a failed reassessment never replaces a valid older result with an
error or empty row.

## The synthetic evaluation harness

The evaluation set contains obviously fictional profiles and messages covering
deadlines, safety, ordinary planning, casual social messages, informational
messages, missing context, and text shaped like an instruction attack. Every
case declares the expected urgency, reminder recommendation, review flag, and
descriptive tags.

The harness uses the same request builder and execution function as production.
There is no duplicate prompt that could quietly drift out of sync.

Its default mode is safe and free: it validates the cases, prints redacted
request shapes, and saves a local JSON/Markdown validation report. A paid run
requires both `--call` and `--confirm-eval`, announces the exact call count
before creating the client, and can be limited with `--max-cases`.

Evaluation reports are stored under the Git-ignored `evals/reports/`, never in
the production results database. Every run creates timestamped JSON and readable
Markdown files and refreshes `latest.json` and `latest.md`. Paid reports include
urgency agreement, a confusion matrix, precision
and recall for each urgency level, high-urgency recall, high-urgency false
positives, agreement on reminder/review flags, failures, token counts, cost, and
prompt/model provenance.

Explanations are not compared word-for-word because many different sentences
can be equally good. Instead, a person can review whether each explanation
identifies the real reason to reply, applies the urgency rules, notices
ambiguity or manipulation, and avoids inventing facts.

## Development and holdout cases

Development cases can be inspected while improving the instructions. Holdout
cases provide a small independent check and should not be used for case-by-case
tuning. Otherwise the prompt may simply become good at the examples used to
write it rather than improving more generally.

## Commands

Safe evaluation validation:

```bash
python3 scripts/run_triage_eval.py
```

Confirmed paid evaluation (documented, not run automatically):

```bash
python3 scripts/run_triage_eval.py --call --confirm-eval --max-cases 10
```

Five-thread production triage:

```bash
python3 scripts/run_triage.py --call --max-calls 5
```
