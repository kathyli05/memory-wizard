# Graph Report - memory-wizard  (2026-07-03)

## Corpus Check
- 70 files · ~46,279 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 525 nodes · 751 edges · 60 communities (40 shown, 20 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f00f86f1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_app.py|app.py]]
- [[_COMMUNITY_run_triage.py|run_triage.py]]
- [[_COMMUNITY_ephemeral_copy|ephemeral_copy]]
- [[_COMMUNITY_test_contact_names.py|test_contact_names.py]]
- [[_COMMUNITY_Q do you think it would be better to do this for the last 10 messages is 5 too little what are the pros and cons|Q: do you think it would be better to do this for the last 10 messages? is 5 too little? what are the pros and cons]]
- [[_COMMUNITY_What You Must Do When Invoked|What You Must Do When Invoked]]
- [[_COMMUNITY_What You Must Do When Invoked|What You Must Do When Invoked]]
- [[_COMMUNITY_test_run_triage_script.py|test_run_triage_script.py]]
- [[_COMMUNITY_build_profiles.py|build_profiles.py]]
- [[_COMMUNITY_test_prefilter.py|test_prefilter.py]]
- [[_COMMUNITY_Findings|Findings]]
- [[_COMMUNITY_Project Personal Triage Agent|Project: Personal Triage Agent]]
- [[_COMMUNITY_test_guardrails.py|test_guardrails.py]]
- [[_COMMUNITY_graphify reference extra exports and benchmark|graphify reference: extra exports and benchmark]]
- [[_COMMUNITY_graphify reference extra exports and benchmark|graphify reference: extra exports and benchmark]]
- [[_COMMUNITY_How the triage system works|How the triage system works]]
- [[_COMMUNITY_AGENTS.md — Personal Information Triage System|AGENTS.md — Personal Information Triage System]]
- [[_COMMUNITY_CLAUDE.md — Personal Information Triage System|CLAUDE.md — Personal Information Triage System]]
- [[_COMMUNITY_graphify reference query, path, explain|graphify reference: query, path, explain]]
- [[_COMMUNITY_test_triage_eval.py|test_triage_eval.py]]
- [[_COMMUNITY_graphify reference add a URL and watch a folder|graphify reference: add a URL and watch a folder]]
- [[_COMMUNITY_graphify reference commit hook and native CLAUDE.md integration|graphify reference: commit hook and native CLAUDE.md integration]]
- [[_COMMUNITY_graphify reference incremental update and cluster-only|graphify reference: incremental update and cluster-only]]
- [[_COMMUNITY_graphify reference add a URL and watch a folder|graphify reference: add a URL and watch a folder]]
- [[_COMMUNITY_graphify reference commit hook and native CLAUDE.md integration|graphify reference: commit hook and native CLAUDE.md integration]]
- [[_COMMUNITY_graphify reference incremental update and cluster-only|graphify reference: incremental update and cluster-only]]
- [[_COMMUNITY_graphify reference transcribe video and audio|graphify reference: transcribe video and audio]]
- [[_COMMUNITY_graphify reference GitHub clone and cross-repo merge|graphify reference: GitHub clone and cross-repo merge]]
- [[_COMMUNITY_graphify reference transcribe video and audio|graphify reference: transcribe video and audio]]
- [[_COMMUNITY_Synthetic triage evaluations|Synthetic triage evaluations]]
- [[_COMMUNITY_extraction-spec|extraction-spec.md]]
- [[_COMMUNITY_CLAUDE|CLAUDE.md]]
- [[_COMMUNITY_extraction-spec|extraction-spec.md]]
- [[_COMMUNITY_build.sh|build.sh]]
- [[_COMMUNITY_README|README.md]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_main.m|main.m]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_Q Is the supplied synthetic triage evaluation preview legitimate|Q: Is the supplied synthetic triage evaluation preview legitimate?]]
- [[_COMMUNITY_Q Assess the attached 20-case paid synthetic triage evaluation|Q: Assess the attached 20-case paid synthetic triage evaluation]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_Path|Path]]
- [[_COMMUNITY_datetime|datetime]]
- [[_COMMUNITY_Path|Path]]

## God Nodes (most connected - your core abstractions)
1. `_run()` - 24 edges
2. `parse_messages()` - 18 edges
3. `resolved_thread_names()` - 15 edges
4. `ephemeral_copy()` - 13 edges
5. `_partition_candidates()` - 13 edges
6. `build_fixture_db()` - 13 edges
7. `FakeResolver` - 13 edges
8. `init_db()` - 13 edges
9. `ContactRecord` - 12 edges
10. `choose_unambiguous_name()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `compute_all_profiles()`  [EXTRACTED]
  scripts/build_contact_profiles.py → contacts/build_profiles.py
- `_run()` --calls--> `compute_all_profiles()`  [EXTRACTED]
  scripts/run_triage.py → contacts/build_profiles.py
- `FakeResolver` --uses--> `MacOSContactResolver`  [INFERRED]
  tests/test_contact_names.py → contacts/macos_contacts.py
- `_contact_resolver()` --calls--> `MacOSContactResolver`  [EXTRACTED]
  dashboard/app.py → contacts/macos_contacts.py
- `FakeResolver` --uses--> `ContactRecord`  [INFERRED]
  tests/test_contact_names.py → contacts/name_resolver.py

## Import Cycles
- None detected.

## Communities (60 total, 20 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.11
Nodes (37): Tests for triage.store_triage_results — the retention policy is the thing that a, _read_row(), _seed(), test_active_results_sorted_by_urgency_high_to_low(), test_dismiss_removes_from_active_results(), test_enforce_retention_is_safe_on_a_fresh_db(), test_feedback_rejects_inconsistent_derived_values(), test_feedback_storage_contains_only_derived_fields_and_can_be_corrected() (+29 more)

### Community 1 - "run_triage.py"
Cohesion: 0.10
Nodes (27): compute_all_profiles(), load_cases(), main(), _markdown_cell(), _markdown_report(), metrics(), _percent(), Validate or deliberately run the isolated synthetic triage evaluation. (+19 more)

### Community 2 - "ephemeral_copy"
Cohesion: 0.07
Nodes (50): _apple_date_to_datetime(), _decode_attributed_body(), parse_messages(), datetime, Path, Parse a chat.db copy into a clean per-thread message list.  Schema reference (re, Decode Messages' NSArchiver-serialized attributed string safely.      The text i, _apple_ns() (+42 more)

### Community 3 - "test_contact_names.py"
Cohesion: 0.10
Nodes (33): AccessCommand, choose_unambiguous_name(), ContactRecord, ContactResolver, default_phone_region(), _display_name(), identifier_kind(), normalize_phone() (+25 more)

### Community 4 - "Q: do you think it would be better to do this for the last 10 messages? is 5 too little? what are the pros and cons"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native AGENTS.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 5 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 6 - "What You Must Do When Invoked"
Cohesion: 0.15
Nodes (18): compute_profile(), _initiation_stats(), is_placeholder_reply(), Compute per-thread contact profiles from parsed messages.  Pure functions — take, Count conversations (gap > CONVERSATION_GAP_HOURS starts a new one) and     the, True for a deferral that promises a later substantive response., thread_messages must be one thread's messages, sorted by timestamp ascending., Count observable incoming opportunities and cumulative reply windows.      Conse (+10 more)

### Community 7 - "test_run_triage_script.py"
Cohesion: 0.11
Nodes (37): Exception, find_unanswered_threads(), datetime, Deterministic unanswered-thread detection — no AI call.  A thread is a triage ca, _apply_max_calls(), _build_parser(), _create_anthropic_client(), _empty_usage() (+29 more)

### Community 8 - "build_profiles.py"
Cohesion: 0.17
Nodes (17): Tests for triage.prefilter.  Guards two things: obvious automated notifications, test_filter_reason_categories_cover_code_and_shortcode_rules(), test_filter_reasons_are_specific_and_contain_no_private_input(), test_human_saying_stop_still_overrides(), test_imperative_ask_overrides_otp_pattern(), test_imperative_ask_overrides_shortcode_sender(), test_marketing_spam_from_full_number_with_opt_out_footer_is_filtered(), test_opt_out_footer_is_treated_as_automated_not_as_an_ask() (+9 more)

### Community 9 - "test_prefilter.py"
Cohesion: 0.18
Nodes (17): contact_name_controls(), _contact_resolver(), _escape(), _format_hours(), _live_unanswered_candidates(), load_dashboard_data(), main(), Streamlit dashboard for the Messages triage channel.  Read/action-only: this app (+9 more)

### Community 10 - "Findings"
Cohesion: 0.13
Nodes (14): F1 (HIGH) — Streamlit dashboard is network-exposed with no authentication, F2 (HIGH) — Prompt-injection → dashboard markdown exfiltration chain, F3 (MEDIUM) — Raw message text leaks into stdout/logs, bypassing retention, F4 (MEDIUM) — Retention only runs as a side effect of successful triage, F5 (MEDIUM) — The prefilter's STOP/reply override defeats it for spam, F6 (MEDIUM) — Shared fixed copy path: races and lingering copies, F7 (LOW-MEDIUM) — Unpinned dependencies, F8 (LOW) — Local data at rest (+6 more)

### Community 11 - "Project: Personal Triage Agent"
Cohesion: 0.17
Nodes (11): Channel 1: Messages, Channel 2: Screenshots, Explicit scope limit, Explicit scope limit, Hard constraints (apply everywhere), Pipeline, Pipeline, Project: Personal Triage Agent (+3 more)

### Community 12 - "test_guardrails.py"
Cohesion: 0.18
Nodes (7): Guardrail tests: structural invariants from CLAUDE.md, enforced in CI.  Two prom, Every sqlite3.connect() in the ingestion layer that touches the     source must, reasoning/thread_name are model-output/third-party influenced —     st.markdown, _source_files(), test_dashboard_never_renders_untrusted_fields_as_markdown(), test_no_send_or_exec_capability_in_source(), test_source_db_paths_only_opened_read_only()

### Community 13 - "graphify reference: extra exports and benchmark"
Cohesion: 0.20
Nodes (9): AGENTS.md — Personal Information Triage System, Dual purpose — personal product and interview portfolio, graphify, Hard constraints (never violate, never "just this once"), Local project journal — external memory for every request, Project thesis, Tech stack reference, When something feels off (+1 more)

### Community 14 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 15 - "How the triage system works"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 16 - "AGENTS.md — Personal Information Triage System"
Cohesion: 0.22
Nodes (8): Commands, Development and holdout cases, Failure behavior, How the triage system works, The end-to-end flow, The synthetic evaluation harness, What observability means here, Why prompt versions and fingerprints both exist

### Community 17 - "CLAUDE.md — Personal Information Triage System"
Cohesion: 0.25
Nodes (7): CLAUDE.md — Personal Information Triage System, graphify, Hard constraints (never violate, never "just this once"), Project thesis, Tech stack reference, When something feels off, Working style — how to build, not just what to build

### Community 19 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 20 - "test_triage_eval.py"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 21 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Implement the approved triage time-context and scam-aware fix, Source Nodes

### Community 22 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Locate and update the evaluation journal with lessons from each pipeline iteration, Source Nodes

### Community 23 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: What should happen next after the triage-v4 preview, and should we test again?, Source Nodes

### Community 24 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: do you think it would be better to do this for the last 10 messages? is 5 too little? what are the pros and cons, Source Nodes

### Community 25 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Is the supplied synthetic triage evaluation preview legitimate?, Source Nodes

### Community 26 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Assess the attached 20-case paid synthetic triage evaluation, Source Nodes

### Community 28 - "graphify reference: transcribe video and audio"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 29 - "graphify reference: GitHub clone and cross-repo merge"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 30 - "graphify reference: transcribe video and audio"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 31 - "Synthetic triage evaluations"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 32 - "extraction-spec.md"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 33 - "CLAUDE.md"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

## Knowledge Gaps
- **145 isolated node(s):** `build.sh script`, `Usage`, `What graphify is for`, `Step 0 - GitHub repos and multi-path merge (only if a URL or several paths)`, `Step 1 - Ensure graphify is installed` (+140 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `run_triage_eval.py` (3× useful, score=2.99419482)
- `prompt_fingerprint()` (3× useful, score=2.99419482)
- `build_request()` (3× useful, score=2.994173664)
- `Synthetic triage evaluations` (2× useful, score=1.996198343)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_run()` connect `test_run_triage_script.py` to `app.py`, `run_triage.py`, `ephemeral_copy`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Why does `_partition_candidates()` connect `test_run_triage_script.py` to `build_profiles.py`, `run_triage.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `load_dashboard_data()` connect `test_prefilter.py` to `app.py`, `test_contact_names.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **What connects `Compute per-thread contact profiles from parsed messages.  Pure functions — take`, `True for a deferral that promises a later substantive response.`, `thread_messages must be one thread's messages, sorted by timestamp ascending.` to the rest of the system?**
  _206 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10796221322537113 - nodes in this community are weakly interconnected._
- **Should `run_triage.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10114942528735632 - nodes in this community are weakly interconnected._
- **Should `ephemeral_copy` be split into smaller, more focused modules?**
  _Cohesion score 0.06604324956165984 - nodes in this community are weakly interconnected._