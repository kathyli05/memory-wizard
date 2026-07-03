---
type: "query"
date: "2026-07-03T19:19:33.884802+00:00"
question: "do you think it would be better to do this for the last 10 messages? is 5 too little? what are the pros and cons"
contributor: "graphify"
outcome: "useful"
source_nodes: ["last_n_messages()", "build_request()", "test_retriage_context_is_capped_at_last_five_messages()"]
---

# Q: do you think it would be better to do this for the last 10 messages? is 5 too little? what are the pros and cons

## Answer

Expanded from original query via graph vocab: [triage, messages, thread, context, five, last, prompt, history, retention]. Recommendation: keep five as the privacy-safe default until a paired synthetic evaluation shows that ten materially improves triage. Five minimizes private context, token cost, latency, and distraction; ten can recover setup and multi-turn nuance but doubles raw-message exposure and may add stale context. Prefer an ambiguity-triggered fallback to ten if evaluation supports it.

## Outcome

- Signal: useful

## Source Nodes

- last_n_messages()
- build_request()
- test_retriage_context_is_capped_at_last_five_messages()