"""CLI: compute contact profiles and show the schema/sample before writing.

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
from ingestion.parse_messages import parse_messages

DEFAULT_SOURCE = Path("./data/chat_copy.db")
DEFAULT_DEST = Path("./data/triage.db")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                         help="parsed chat.db copy to read messages from")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                         help="triage.db path to write profiles to (only used with --write)")
    parser.add_argument("--write", action="store_true",
                         help="persist profiles to --dest; omit to only preview")
    args = parser.parse_args()

    messages = parse_messages(args.source)
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
