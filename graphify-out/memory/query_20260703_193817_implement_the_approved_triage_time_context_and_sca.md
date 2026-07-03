---
type: "query"
date: "2026-07-03T19:38:17.920339+00:00"
question: "Implement the approved triage time-context and scam-aware fix"
contributor: "graphify"
outcome: "useful"
source_nodes: ["build_request()", "run_triage()", "run_triage_eval.py", "prompt_fingerprint()"]
---

# Q: Implement the approved triage time-context and scam-aware fix

## Answer

Expanded from graph vocabulary: [assessment, context, request, prompt, triage, urgency, review, profile, evaluation, synthetic]. Implemented triage-v4 with runtime assessment_time passed through production and evaluation, scam-aware separation using urgency, needs_review, suggest_nudge, and next_action, an observed payment-case correction, regression tests, documentation, and graph refresh. Verification: 26 focused tests and 86 full tests passed; free preview validated 20 cases with zero calls/tokens/cost; fingerprint 9604d1b9c5617816cd6b2ef828b30133b1f747a3cb5eff439568cffb52f596d6; graph rebuilt to 502 nodes and 857 edges. Fresh holdouts are required before a paid comparison.

## Outcome

- Signal: useful

## Source Nodes

- build_request()
- run_triage()
- run_triage_eval.py
- prompt_fingerprint()