"""Claude API triage agent — structured urgency assessment per thread.

Sends only what the task needs: one thread's contact profile summary plus
its last 5 messages. Uses a forced tool call (strict schema) for structured
output rather than output_config.format, since that feature's documented
model support doesn't confirm claude-sonnet-4-6.
"""

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You help triage unanswered text message threads for someone \
managing ADHD-related response overload. You will be given a contact's \
derived behavior profile and the last 5 messages of one unanswered thread. \
Assess how urgent a reply is and whether the user should be nudged to \
respond. Base urgency on the actual content and context of the messages, \
not just the latency statistics. Always call the emit_triage_assessment \
tool with your assessment."""

TRIAGE_TOOL = {
    "name": "emit_triage_assessment",
    "description": "Record the triage assessment for this thread.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "urgency": {
                "type": "string",
                "enum": ["low", "med", "high"],
                "description": "How urgently this thread needs a reply.",
            },
            "reasoning": {
                "type": "string",
                "description": "1-2 sentence human-readable rationale for the urgency and nudge call.",
            },
            "suggest_nudge": {
                "type": "boolean",
                "description": "Whether to proactively suggest the user reply to this thread.",
            },
        },
        "required": ["urgency", "reasoning", "suggest_nudge"],
        "additionalProperties": False,
    },
}


def last_n_messages(messages: list[dict], thread_id, n: int = 5) -> list[dict]:
    thread_messages = [m for m in messages if m["thread_id"] == thread_id]
    thread_messages.sort(key=lambda m: m["timestamp"])
    return thread_messages[-n:]


def _format_duration(seconds: float) -> str:
    if seconds < 3600:
        return f"{seconds / 60:.0f} minutes"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} hours"
    return f"{seconds / 86400:.1f} days"


def _profile_summary(profile: dict) -> str:
    lines = [f"Contact: {profile['thread_name']}"]

    latency = profile.get("median_response_latency_seconds_365d")
    lines.append(
        f"Median response latency from me (last 365 days): "
        f"{_format_duration(latency) if latency is not None else 'no data'}"
    )

    lines.append(
        f"Message frequency (last 90 days): {profile['message_count_90d']} messages "
        f"({profile['messages_per_day_90d']:.2f}/day)"
    )

    ratio = profile.get("initiation_ratio_me_365d")
    if ratio is not None:
        lines.append(
            f"Who starts conversations (last 365 days): {ratio * 100:.0f}% me, "
            f"{(1 - ratio) * 100:.0f}% them"
        )
    else:
        lines.append("Who starts conversations: no data")

    return "\n".join(lines)


def _messages_block(thread_messages: list[dict]) -> str:
    lines = []
    for m in thread_messages:
        who = "Me" if m["is_from_me"] else m["sender"]
        ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {who}: {m['text']}")
    return "\n".join(lines)


def build_request(profile: dict, thread_messages: list[dict]) -> dict:
    """Pure function — no network call. Returns the exact kwargs for
    client.messages.create(**kwargs)."""
    user_content = (
        "CONTACT PROFILE\n"
        f"{_profile_summary(profile)}\n\n"
        "LAST 5 MESSAGES IN THIS THREAD\n"
        f"{_messages_block(thread_messages)}\n\n"
        "Assess this thread for triage."
    )

    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "tools": [TRIAGE_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_triage_assessment"},
        "messages": [{"role": "user", "content": user_content}],
    }


def run_triage(client, profile: dict, thread_messages: list[dict]) -> dict:
    request = build_request(profile, thread_messages)
    response = client.messages.create(**request)

    tool_use = next(b for b in response.content if b.type == "tool_use")
    result = dict(tool_use.input)
    result["thread_id"] = profile["thread_id"]
    return result
