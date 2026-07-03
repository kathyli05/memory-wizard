import copy
from types import SimpleNamespace

from triage import triage_agent


def test_prompt_fingerprint_is_deterministic_and_contains_no_runtime_data():
    assert triage_agent.PROMPT_VERSION == "triage-v3"
    first = triage_agent.prompt_fingerprint()
    second = triage_agent.prompt_fingerprint()
    assert first == second
    assert len(first) == 64
    assert "Private Person" not in first
    assert "private message" not in first


def test_prompt_fingerprint_changes_when_contract_changes(monkeypatch):
    original = triage_agent.prompt_fingerprint()
    changed_tool = copy.deepcopy(triage_agent.TRIAGE_TOOL)
    changed_tool["description"] += " Changed contract."
    monkeypatch.setattr(triage_agent, "TRIAGE_TOOL", changed_tool)
    assert triage_agent.prompt_fingerprint() != original


def test_run_triage_captures_realistic_usage_metadata():
    response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input={
            "urgency": "high", "reasoning": "A fictional deadline is today.",
            "action_required": True, "next_action": "Reply today.",
            "suggest_nudge": True, "needs_review": False,
        })],
        stop_reason="tool_use",
        usage=SimpleNamespace(
            input_tokens=321, output_tokens=45,
            cache_creation_input_tokens=100, cache_read_input_tokens=50,
        ),
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    profile = {
        "thread_id": 1, "thread_name": "Fictional Person",
        "median_response_latency_seconds_365d": None,
        "message_count_90d": 1, "messages_per_day_90d": 0.01,
        "initiation_ratio_me_365d": None,
    }
    message = {
        "thread_id": 1, "sender": "Fictional Person", "text": "Reply today.",
        "timestamp": __import__("datetime").datetime(2030, 1, 1),
        "is_from_me": False,
    }
    result = triage_agent.run_triage(client, profile, [message])
    assert result["action_required"] is True
    assert result["next_action"] == "Reply today."
    assert result["_usage"] == {
        "input_tokens": 321, "output_tokens": 45,
        "cache_creation_tokens": 100, "cache_read_tokens": 50,
    }
