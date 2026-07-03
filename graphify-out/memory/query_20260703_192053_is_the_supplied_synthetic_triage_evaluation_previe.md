---
type: "query"
date: "2026-07-03T19:20:53.160677+00:00"
question: "Is the supplied synthetic triage evaluation preview legitimate?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Synthetic triage evaluations", "run_triage_eval.py", "prompt_fingerprint()", "write_report()"]
---

# Q: Is the supplied synthetic triage evaluation preview legitimate?

## Answer

Expanded from original query via graph vocab: [evaluation, synthetic, preview, cases, holdout, prompt, fingerprint, redacted, request, cost, pricing]. Yes, as a preview/provenance artifact: the timestamped JSON exists, contains 20 validated cases split 14/6, reports zero calls and tokens, and its triage-v3 fingerprint matches current code. Focused tests pass 9/9. It is not evidence of prediction accuracy or reasoning quality because no model was called. The README case-count prose is stale at 7/3 versus the current 14/6 suite.

## Outcome

- Signal: useful

## Source Nodes

- Synthetic triage evaluations
- run_triage_eval.py
- prompt_fingerprint()
- write_report()