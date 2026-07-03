"""CLI: build (and optionally send) triage requests for unanswered threads.

Usage:
    python scripts/run_triage.py [--source PATH] [--threshold-hours N]
                                  [--lookback-days N] [--dest PATH]
                                  [--retriage-one | --retriage-all]
                                  [--confirm-retriage-all] [--call] [--keep-copy]
                                  [--max-calls N]

Copies chat.db read-only, uses it, then deletes the copy — no raw message
data lingers on disk after this script exits. Pass --keep-copy to inspect
the intermediate file (an explicit opt-in, off by default).

Without --call, this prints a redacted exact-shape request preview — no
network call is made and no storage is touched. Message text, contact names,
phone numbers, email addresses, and senders are never printed. Real runs log
thread ids, counts, and scores only. Two kinds of candidates never reach a request, both
listed separately so nothing is silently dropped:
  - flagged as automated notifications (OTP codes, shortcode senders) —
    see triage.prefilter
  - already triaged with no new message since (checked against --dest,
    even without --call, since it's a local read) — see
    triage.store_triage_results.get_last_triaged_timestamps

With --call: results are collected, written to --dest (default
./data/triage.db), and the retention policy is enforced immediately after.

--retriage-one selects the oldest still-unanswered, previously triaged,
non-automated candidate and bypasses the unchanged-result dedup for that one
thread only. It therefore previews at most one request and, with --call, makes
at most one API call and replaces only that thread's stored triage result.

--retriage-all applies the same eligibility rules to every previously triaged
candidate in the configured lookback window. Calling the API in this mode also
requires --confirm-retriage-all.
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
from triage.prefilter import automated_filter_reason
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


def _positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _apply_max_calls(to_triage, max_calls):
    """Apply the same deterministic cap to previews and real calls."""
    return to_triage if max_calls is None else to_triage[:max_calls]


def _create_anthropic_client():
    import anthropic

    return anthropic.Anthropic()


def _partition_candidates(
    messages,
    candidates,
    last_triaged,
    *,
    retriage_one=False,
    retriage_all=False,
):
    """Return (to_triage, filtered, unchanged) for the selected triage mode."""
    to_triage = []
    filtered = []
    unchanged = []

    for candidate in candidates:
        thread_id = candidate["thread_id"]
        thread_messages = last_n_messages(messages, thread_id, n=5)
        last_message = thread_messages[-1]
        previously_triaged_at = last_triaged.get(thread_id)

        if retriage_one or retriage_all:
            if previously_triaged_at is None:
                continue
            filter_reason = automated_filter_reason(
                last_message["sender"], last_message["text"]
            )
            if filter_reason:
                filtered.append((candidate, filter_reason))
                continue
            to_triage.append((candidate, thread_messages))
            if retriage_one:
                break
            continue

        if (previously_triaged_at is not None
                and candidate["last_message_timestamp"].isoformat()
                <= previously_triaged_at):
            unchanged.append(candidate)
        else:
            filter_reason = automated_filter_reason(
                last_message["sender"], last_message["text"]
            )
            if filter_reason:
                filtered.append((candidate, filter_reason))
                continue
            to_triage.append((candidate, thread_messages))

    return to_triage, filtered, unchanged


def _redacted_request(profile, thread_messages):
    """Build the real request shape with every private string replaced."""
    redacted_profile = dict(profile)
    redacted_profile["thread_name"] = "[REDACTED THREAD]"

    redacted_messages = []
    for index, message in enumerate(thread_messages, start=1):
        redacted = dict(message)
        if not message["is_from_me"]:
            redacted["sender"] = "[REDACTED SENDER]"
        redacted["text"] = f"[REDACTED readable message {index}]"
        redacted_messages.append(redacted)
    return build_request(redacted_profile, redacted_messages)


def _build_parser():
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
    parser.add_argument(
        "--max-calls",
        type=_positive_int,
        help="cap both previews and API calls to the first N eligible threads",
    )
    retriage_group = parser.add_mutually_exclusive_group()
    retriage_group.add_argument(
        "--retriage-one",
        action="store_true",
        help="reassess exactly one previously triaged, still-unanswered thread",
    )
    retriage_group.add_argument(
        "--retriage-all",
        action="store_true",
        help="reassess all previously triaged, still-unanswered eligible threads",
    )
    parser.add_argument(
        "--confirm-retriage-all",
        action="store_true",
        help="required confirmation when combining --retriage-all with --call",
    )
    parser.add_argument("--keep-copy", action="store_true",
                         help="don't delete the chat.db copy afterward (default: delete it)")
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.call and args.retriage_all and not args.confirm_retriage_all:
        parser.error(
            "--call --retriage-all requires explicit --confirm-retriage-all"
        )

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

    to_triage, filtered, unchanged = _partition_candidates(
        messages,
        candidates,
        last_triaged,
        retriage_one=args.retriage_one,
        retriage_all=args.retriage_all,
    )
    eligible_count = len(to_triage)
    to_triage = _apply_max_calls(to_triage, args.max_calls)

    if unchanged:
        print(f"{len(unchanged)} already triaged with no new message since — skipped:")
        for candidate in unchanged:
            print(f"  thread_id={candidate['thread_id']}")
        print()

    if filtered:
        print(f"{len(filtered)} filtered as likely automated (not sent to triage):")
        for candidate, filter_reason in filtered:
            print(f"  thread_id={candidate['thread_id']} — {filter_reason}")
        print()

    if args.retriage_one:
        print("retriage-one mode: at most one API request and one stored-result replacement")
    elif args.retriage_all:
        print("retriage-all mode: all eligible prior results will be reassessed")
    if len(to_triage) < eligible_count:
        print(
            f"max-calls cap applied: {len(to_triage)} of {eligible_count} "
            "eligible candidate(s) will be processed"
        )
    print(f"{len(to_triage)} candidate(s) proceeding to triage\n")

    client = None
    if args.call:
        print(f"API calls about to be made: {len(to_triage)}")
        if to_triage:
            client = _create_anthropic_client()

    succeeded = 0
    failed = 0
    try:
        for candidate, thread_messages in to_triage:
            thread_id = candidate["thread_id"]
            profile = profiles_by_thread[thread_id]

            print(f"=== thread_id={thread_id} ===")

            if args.call:
                # No payload/reasoning echo on real runs — see module docstring.
                print(f"sending triage request ({len(thread_messages)} messages in context)")
                try:
                    result = run_triage(client, profile, thread_messages)
                except Exception as exc:
                    failed += 1
                    print(f"request failed safely: {type(exc).__name__}\n")
                    continue

                result["thread_name"] = profile["thread_name"]
                result["last_message_timestamp"] = (
                    candidate["last_message_timestamp"].isoformat()
                )
                result["computed_at"] = datetime.now().isoformat()
                upsert_results(args.dest, [result])
                succeeded += 1
                print(
                    f"result: urgency={result['urgency']} "
                    f"suggest_nudge={result['suggest_nudge']} "
                    f"needs_review={result['needs_review']}"
                )
                print()
            else:
                request = _redacted_request(profile, thread_messages)
                print(json.dumps(request, indent=2, default=_json_default))
                print("\nredacted preview only — --call not passed; request not sent\n")
    finally:
        if args.call:
            scrubbed = enforce_retention(args.dest)
            print(f"stored {succeeded} successful result(s); {failed} request(s) failed")
            print(f"retention enforced: {scrubbed} row(s) past the "
                  f"{RETENTION_DAYS}-day window had reasoning cleared")


if __name__ == "__main__":
    main()
