"""CLI: build (and optionally send) triage requests for unanswered threads.

Usage:
    python scripts/run_triage.py [--source PATH] [--threshold-hours N]
                                  [--lookback-days N] [--dest PATH]
                                  [--call] [--keep-copy]

Copies chat.db read-only, uses it, then deletes the copy — no raw message
data lingers on disk after this script exits. Pass --keep-copy to inspect
the intermediate file (an explicit opt-in, off by default).

Without --call, this only prints the exact request payload that would be
sent to the Claude API per candidate thread — no network call is made and
no storage is touched. Two kinds of candidates never reach a request, both
listed separately so nothing is silently dropped:
  - flagged as automated notifications (OTP codes, shortcode senders) —
    see triage.prefilter
  - already triaged with no new message since (checked against --dest,
    even without --call, since it's a local read) — see
    triage.store_triage_results.get_last_triaged_timestamps

With --call: results are collected, written to --dest (default
./data/triage.db), and the retention policy is enforced immediately after.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contacts.build_profiles import compute_all_profiles
from ingestion.copy_chat_db import (
    DEFAULT_DEST as DEFAULT_COPY_DEST,
    DEFAULT_SOURCE,
    copy_chat_db,
    ephemeral_copy,
)
from ingestion.parse_messages import parse_messages
from triage.detect_unanswered import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_THRESHOLD_HOURS,
    find_unanswered_threads,
)
from triage.prefilter import is_likely_automated
from triage.store_triage_results import (
    RETENTION_DAYS,
    enforce_retention,
    get_last_triaged_timestamps,
    upsert_results,
)
from triage.triage_agent import build_request, last_n_messages, run_triage

DEFAULT_DEST = Path("./data/triage.db")


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {obj!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                         help="real chat.db to copy messages from")
    parser.add_argument("--copy-dest", type=Path, default=DEFAULT_COPY_DEST,
                         help="where the ephemeral copy briefly lives")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                         help="triage.db path to read prior results from / write results to")
    parser.add_argument("--threshold-hours", type=float, default=DEFAULT_THRESHOLD_HOURS)
    parser.add_argument("--lookback-days", type=float, default=DEFAULT_LOOKBACK_DAYS,
                         help="ignore threads whose last message is older than this many "
                              "days; pass a very large value to disable")
    parser.add_argument("--call", action="store_true",
                         help="actually call the Claude API; omit to only preview requests")
    parser.add_argument("--keep-copy", action="store_true",
                         help="don't delete the chat.db copy afterward (default: delete it)")
    args = parser.parse_args()

    if args.keep_copy:
        chat_copy_path = copy_chat_db(args.source, args.copy_dest)
        _run(chat_copy_path, args)
    else:
        with ephemeral_copy(args.source, args.copy_dest) as chat_copy_path:
            _run(chat_copy_path, args)


def _run(chat_copy_path: Path, args):
    messages = parse_messages(chat_copy_path)
    candidates = find_unanswered_threads(
        messages, threshold_hours=args.threshold_hours, lookback_days=args.lookback_days
    )
    profiles_by_thread = {p["thread_id"]: p for p in compute_all_profiles(messages)}
    last_triaged = get_last_triaged_timestamps(args.dest)

    print(f"{len(candidates)} candidate thread(s) found "
          f"(last {args.lookback_days:.0f} days)\n")

    to_triage = []
    filtered = []
    unchanged = []
    for candidate in candidates:
        thread_id = candidate["thread_id"]
        thread_messages = last_n_messages(messages, thread_id, n=5)
        last_message = thread_messages[-1]

        previously_triaged_at = last_triaged.get(thread_id)
        if (previously_triaged_at is not None
                and candidate["last_message_timestamp"].isoformat() <= previously_triaged_at):
            unchanged.append(candidate)
        elif is_likely_automated(last_message["sender"], last_message["text"]):
            filtered.append((candidate, last_message))
        else:
            to_triage.append((candidate, thread_messages))

    if unchanged:
        print(f"{len(unchanged)} already triaged with no new message since — skipped:")
        for candidate in unchanged:
            print(f"  thread_id={candidate['thread_id']} "
                  f"({candidate['thread_name']})")
        print()

    if filtered:
        print(f"{len(filtered)} filtered as likely automated (not sent to triage):")
        for candidate, last_message in filtered:
            snippet = last_message["text"][:80]
            print(f"  thread_id={candidate['thread_id']} "
                  f"sender={last_message['sender']!r} text={snippet!r}")
        print()

    print(f"{len(to_triage)} candidate(s) proceeding to triage\n")

    client = None
    if args.call:
        import anthropic
        client = anthropic.Anthropic()

    results = []
    for candidate, thread_messages in to_triage:
        thread_id = candidate["thread_id"]
        profile = profiles_by_thread[thread_id]

        request = build_request(profile, thread_messages)
        print(f"=== thread_id={thread_id} ({profile['thread_name']}) ===")
        print(json.dumps(request, indent=2, default=_json_default))
        print()

        if args.call:
            result = run_triage(client, profile, thread_messages)
            result["thread_name"] = profile["thread_name"]
            result["last_message_timestamp"] = candidate["last_message_timestamp"].isoformat()
            result["computed_at"] = datetime.now().isoformat()
            print("result:", result)
            print()
            results.append(result)
        else:
            print("--call not passed: request not sent\n")

    if args.call:
        upsert_results(args.dest, results)
        scrubbed = enforce_retention(args.dest)
        print(f"wrote {len(results)} result(s) to {args.dest}")
        print(f"retention enforced: {scrubbed} row(s) past the "
              f"{RETENTION_DAYS}-day window had reasoning cleared")


if __name__ == "__main__":
    main()
