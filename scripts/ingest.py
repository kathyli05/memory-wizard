"""CLI: copy chat.db read-only, parse it, print a sample for sanity check.

The copy is ephemeral — deleted as soon as this script is done with it, so
no raw message data lingers on disk. Pass --keep-copy to inspect the
intermediate file (an explicit opt-in, off by default).

Usage:
    python scripts/ingest.py [--source PATH] [--copy-dest PATH]
                              [--sample N] [--keep-copy]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import DEFAULT_DEST, DEFAULT_SOURCE, copy_chat_db, ephemeral_copy
from ingestion.parse_messages import parse_messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                         help="real chat.db to copy from")
    parser.add_argument("--copy-dest", type=Path, default=DEFAULT_DEST,
                         help="where the ephemeral copy briefly lives")
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--keep-copy", action="store_true",
                         help="don't delete the copy afterward (default: delete it)")
    args = parser.parse_args()

    if args.keep_copy:
        dest = copy_chat_db(args.source, args.copy_dest)
        print(f"copied {args.source} -> {dest} (read-only source access, kept)\n")
        _run(dest, args.sample)
    else:
        with ephemeral_copy(args.source, args.copy_dest) as dest:
            print(f"copied {args.source} -> {dest} (read-only source access, ephemeral)\n")
            _run(dest, args.sample)
        print(f"\ndeleted ephemeral copy at {dest}")


def _run(dest: Path, sample: int):
    messages = parse_messages(dest)
    print(f"parsed {len(messages)} messages across "
          f"{len({m['thread_id'] for m in messages})} threads\n")

    print(f"sample of {min(sample, len(messages))} messages:")
    for m in messages[:sample]:
        print(m)


if __name__ == "__main__":
    main()
