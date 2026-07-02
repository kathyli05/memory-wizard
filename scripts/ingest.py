"""CLI: copy chat.db read-only, parse it, print a sample for sanity check.

Usage:
    python scripts/ingest.py [--source PATH] [--dest PATH] [--sample N]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import DEFAULT_DEST, DEFAULT_SOURCE, copy_chat_db
from ingestion.parse_messages import parse_messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    dest = copy_chat_db(args.source, args.dest)
    print(f"copied {args.source} -> {dest} (read-only source access)\n")

    messages = parse_messages(dest)
    print(f"parsed {len(messages)} messages across "
          f"{len({m['thread_id'] for m in messages})} threads\n")

    print(f"sample of {min(args.sample, len(messages))} messages:")
    for m in messages[: args.sample]:
        print(m)


if __name__ == "__main__":
    main()
