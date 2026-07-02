"""CLI: compute contact profiles and show the schema/sample before writing.

Copies chat.db read-only, uses it, then deletes the copy — no raw message
data lingers on disk after this script exits. Pass --keep-copy to inspect
the intermediate file (an explicit opt-in, off by default).

Usage:
    python scripts/build_contact_profiles.py [--source PATH] [--write]

Without --write, this only prints the schema and computed profiles — no
database is touched. Pass --write to persist to ./data/triage.db (or
--dest to point elsewhere).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contacts.build_profiles import compute_all_profiles
from contacts.store_profiles import SCHEMA, upsert_profiles
from ingestion.copy_chat_db import (
    DEFAULT_DEST as DEFAULT_COPY_DEST,
    DEFAULT_SOURCE,
    copy_chat_db,
    ephemeral_copy,
)
from ingestion.parse_messages import parse_messages

DEFAULT_DEST = Path("./data/triage.db")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                         help="real chat.db to copy messages from")
    parser.add_argument("--copy-dest", type=Path, default=DEFAULT_COPY_DEST,
                         help="where the ephemeral copy briefly lives")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                         help="triage.db path to write profiles to (only used with --write)")
    parser.add_argument("--write", action="store_true",
                         help="persist profiles to --dest; omit to only preview")
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
    profiles = compute_all_profiles(messages)

    print("schema for contact_profiles table:")
    print(SCHEMA.strip())
    print()
    print(f"computed {len(profiles)} contact profiles from {len(messages)} messages:")
    for p in profiles:
        print(p)

    if args.write:
        upsert_profiles(args.dest, profiles)
        print(f"\nwrote {len(profiles)} profiles to {args.dest}")
    else:
        print(f"\n--write not passed: nothing written to {args.dest}")


if __name__ == "__main__":
    main()
