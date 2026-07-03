---
type: "query"
date: "2026-07-03T19:25:12.176077+00:00"
question: "Assess the attached 20-case paid synthetic triage evaluation"
contributor: "graphify"
outcome: "useful"
source_nodes: ["metrics()", "run_triage_eval.py", "build_request()", "prompt_fingerprint()"]
---

# Q: Assess the attached 20-case paid synthetic triage evaluation

## Answer

Expanded from original query via graph vocab: [paid, evaluation, synthetic, metrics, rationale, reasoning, review, holdout, cost, prompt, fingerprint]. The run is authentic: 20/20 successful calls, /bin/zsh.156111 estimated cost, matching triage-v3 fingerprint, exactly recomputable stored metrics, and 9/9 focused tests. Combined urgency agreement is 90%, but holdout urgency agreement is 83.3%, high recall 66.7%, and review agreement 50%. The payment false negative is consequential. Fixtures provide as_of but build_request does not send assessment time, causing unnecessary review flags. Sparse contact statistics are also being overused as scam evidence despite the content-first rubric. Fix those contract issues before testing five versus ten messages; use fresh holdouts after tuning.

## Outcome

- Signal: useful

## Source Nodes

- metrics()
- run_triage_eval.py
- build_request()
- prompt_fingerprint()