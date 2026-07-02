"""CLI: build (and optionally send) triage requests for unanswered threads.

Usage:
    python scripts/run_triage.py [--source PATH] [--threshold-hours N] [--call]

Without --call, this only prints the exact request payload that would be
sent to the Claude API per candidate thread — no network call is made.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contacts.build_profiles import compute_all_profiles
from ingestion.parse_messages import parse_messages
from triage.detect_unanswered import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_THRESHOLD_HOURS,
    find_unanswered_threads,
)
from triage.triage_agent import build_request, last_n_messages, run_triage

DEFAULT_SOURCE = Path("./data/chat_copy.db")


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {obj!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--threshold-hours", type=float, default=DEFAULT_THRESHOLD_HOURS)
    parser.add_argument("--lookback-days", type=float, default=DEFAULT_LOOKBACK_DAYS,
                         help="ignore threads whose last message is older than this many "
                              "days; pass a very large value to disable")
    parser.add_argument("--call", action="store_true",
                         help="actually call the Claude API; omit to only preview requests")
    args = parser.parse_args()

    messages = parse_messages(args.source)
    candidates = find_unanswered_threads(
        messages, threshold_hours=args.threshold_hours, lookback_days=args.lookback_days
    )
    profiles_by_thread = {p["thread_id"]: p for p in compute_all_profiles(messages)}

    print(f"{len(candidates)} candidate thread(s) for triage "
          f"(last {args.lookback_days:.0f} days)\n")

    client = None
    if args.call:
        import anthropic
        client = anthropic.Anthropic()

    for candidate in candidates:
        thread_id = candidate["thread_id"]
        profile = profiles_by_thread[thread_id]
        thread_messages = last_n_messages(messages, thread_id, n=5)

        request = build_request(profile, thread_messages)
        print(f"=== thread_id={thread_id} ({profile['thread_name']}) ===")
        print(json.dumps(request, indent=2, default=_json_default))
        print()

        if args.call:
            result = run_triage(client, profile, thread_messages)
            print("result:", result)
            print()
        else:
            print("--call not passed: request not sent\n")


if __name__ == "__main__":
    main()
