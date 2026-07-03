# Graph Report - .  (2026-07-03)

## Corpus Check
- Corpus is ~17,872 words - fits in a single context window. You may not need a graph.

## Summary
- 198 nodes · 382 edges · 15 communities
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.83)
- Token cost: 101,064 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Message Ingestion & Parsing|Message Ingestion & Parsing]]
- [[_COMMUNITY_Graphify Skill Reference|Graphify Skill Reference]]
- [[_COMMUNITY_Triage Store Tests|Triage Store Tests]]
- [[_COMMUNITY_Privacy & Triage Principles|Privacy & Triage Principles]]
- [[_COMMUNITY_Contact Profiles|Contact Profiles]]
- [[_COMMUNITY_Triage Agent & CLI|Triage Agent & CLI]]
- [[_COMMUNITY_Dashboard & Unanswered Detection|Dashboard & Unanswered Detection]]
- [[_COMMUNITY_Automated Message Prefilter|Automated Message Prefilter]]
- [[_COMMUNITY_Graph Query & Feedback Loops|Graph Query & Feedback Loops]]
- [[_COMMUNITY_Draft Message Policy|Draft Message Policy]]

## God Nodes (most connected - your core abstractions)
1. `Graphify Knowledge Graph Pipeline` - 20 edges
2. `parse_messages()` - 17 edges
3. `ephemeral_copy()` - 15 edges
4. `_run()` - 14 edges
5. `build_fixture_db()` - 14 edges
6. `copy_chat_db()` - 12 edges
7. `get_active_results()` - 12 edges
8. `is_likely_automated()` - 11 edges
9. `upsert_results()` - 11 edges
10. `get_last_triaged_timestamps()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Always Show Reasoning` --semantically_similar_to--> `Graphify Honesty Rules`  [INFERRED] [semantically similar]
  CLAUDE.md → .claude/skills/graphify/SKILL.md
- `Accept/Reject Feedback Loop` --semantically_similar_to--> `Work Memory save-result Feedback Loop`  [INFERRED] [semantically similar]
  PROJECT.md → .claude/skills/graphify/references/query.md
- `Draft Generation on Explicit Request` --conceptually_related_to--> `No Draft-Generation Scope Limit`  [AMBIGUOUS]
  CLAUDE.md → PROJECT.md
- `memory-wizard` --conceptually_related_to--> `Personal Triage Agent`  [INFERRED]
  README.md → PROJECT.md
- `pytest` --conceptually_related_to--> `Personal Triage Agent`  [INFERRED]
  requirements.txt → PROJECT.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Privacy Hard Constraints** — claude_source_immutability, claude_no_auto_send, claude_api_minimization, claude_show_reasoning, claude_retention_policy, claude_dashboard_review [EXTRACTED 1.00]
- **Graphify Build Pipeline Stages** — _claude_skills_graphify_skill_ast_extraction, _claude_skills_graphify_skill_semantic_extraction, _claude_skills_graphify_skill_extraction_cache, _claude_skills_graphify_skill_community_detection, _claude_skills_graphify_skill_graph_health_check, _claude_skills_graphify_skill_shrink_guard [EXTRACTED 1.00]
- **Screenshot Channel Pipeline** — project_screenshot_categorization, project_nl_search, project_expiry_surfacing, project_deletion_suggestions, project_feedback_loop [EXTRACTED 1.00]

## Communities (15 total, 0 thin omitted)

### Community 0 - "Message Ingestion & Parsing"
Cohesion: 0.11
Nodes (32): copy_chat_db(), ephemeral_copy(), Path, Read-only snapshot of the macOS Messages database.  Never opens the source for w, Copy chat.db to dest, yield the path, then delete the copy — so no     raw messa, _apple_date_to_datetime(), parse_messages(), datetime (+24 more)

### Community 1 - "Graphify Skill Reference"
Cohesion: 0.08
Nodes (34): URL Ingestion (/graphify add), Watch Mode Auto-Rebuild, FalkorDB Export, Graph MCP Server, Neo4j Cypher Export, Token Reduction Benchmark, Wiki Export, Discrete Confidence Rubric (+26 more)

### Community 2 - "Triage Store Tests"
Cohesion: 0.20
Nodes (26): Tests for triage.store_triage_results — the retention policy is the thing that a, _read_row(), _seed(), test_active_results_sorted_by_urgency_high_to_low(), test_dismiss_removes_from_active_results(), test_fresh_result_defaults_to_pending(), test_get_last_triaged_timestamps_empty_on_fresh_db(), test_get_last_triaged_timestamps_returns_stored_values() (+18 more)

### Community 3 - "Privacy & Triage Principles"
Cohesion: 0.11
Nodes (24): API Context Minimization, Dashboard-Only Deletion Review, Retention Policy (14-Day Raw Content Deletion), Always Show Reasoning, Source Data Immutability Constraint, Streamlit Dashboard, Local Triage DB (./data/triage.db), Personal Information Triage System (+16 more)

### Community 4 - "Contact Profiles"
Cohesion: 0.16
Nodes (17): compute_all_profiles(), compute_profile(), _initiation_stats(), _median_response_latency(), datetime, Compute per-thread contact profiles from parsed messages.  Pure functions — take, thread_messages must be one thread's messages, sorted by timestamp ascending., Median seconds between the end of each incoming run and my next reply.      A ga (+9 more)

### Community 5 - "Triage Agent & CLI"
Cohesion: 0.25
Nodes (13): _json_default(), main(), Path, CLI: build (and optionally send) triage requests for unanswered threads.  Usage:, _run(), build_request(), _format_duration(), last_n_messages() (+5 more)

### Community 6 - "Dashboard & Unanswered Detection"
Cohesion: 0.27
Nodes (10): _format_hours(), load_dashboard_data(), main(), Streamlit dashboard for the Messages triage channel.  Read/action-only: this app, Live-recheck against current Messages, intersected with stored     (non-dismisse, render_card(), render_snooze_controls(), find_unanswered_threads() (+2 more)

### Community 7 - "Automated Message Prefilter"
Cohesion: 0.27
Nodes (10): Tests for triage.prefilter.  Guards two things: obvious automated notifications, test_imperative_ask_overrides_otp_pattern(), test_imperative_ask_overrides_shortcode_sender(), test_otp_from_shortcode_is_filtered(), test_personal_contact_is_not_filtered(), test_shortcode_sender_alone_is_filtered(), test_stop_keyword_overrides_filter(), is_likely_automated() (+2 more)

### Community 8 - "Graph Query & Feedback Loops"
Cohesion: 0.33
Nodes (6): BFS/DFS Graph Traversal, Node Explain Query, Shortest Path Query, Constrained Query Vocabulary Expansion, Work Memory save-result Feedback Loop, Accept/Reject Feedback Loop

### Community 9 - "Draft Message Policy"
Cohesion: 0.67
Nodes (3): Draft Generation on Explicit Request, Never Auto-Send Messages, No Draft-Generation Scope Limit

## Ambiguous Edges - Review These
- `Draft Generation on Explicit Request` → `No Draft-Generation Scope Limit`  [AMBIGUOUS]
  CLAUDE.md · relation: conceptually_related_to

## Knowledge Gaps
- **19 isolated node(s):** `Graphify Skill Trigger`, `Semantic Extraction Cache`, `Graph Shrink Guard (#479)`, `Hyperedges`, `Semantic Similarity Edges` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Draft Generation on Explicit Request` and `No Draft-Generation Scope Limit`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `parse_messages()` connect `Message Ingestion & Parsing` to `Contact Profiles`, `Triage Agent & CLI`, `Dashboard & Unanswered Detection`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `is_likely_automated()` connect `Automated Message Prefilter` to `Triage Agent & CLI`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **What connects `Compute per-thread contact profiles from parsed messages.  Pure functions — take`, `thread_messages must be one thread's messages, sorted by timestamp ascending.`, `Median seconds between the end of each incoming run and my next reply.      A ga` to the rest of the system?**
  _51 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Message Ingestion & Parsing` be split into smaller, more focused modules?**
  _Cohesion score 0.10931174089068826 - nodes in this community are weakly interconnected._
- **Should `Graphify Skill Reference` be split into smaller, more focused modules?**
  _Cohesion score 0.0766488413547237 - nodes in this community are weakly interconnected._
- **Should `Privacy & Triage Principles` be split into smaller, more focused modules?**
  _Cohesion score 0.11231884057971014 - nodes in this community are weakly interconnected._