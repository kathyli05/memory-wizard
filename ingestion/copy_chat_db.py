"""Read-only snapshot of the macOS Messages database.

Never opens the source for writing and never touches sidecar files in
place — uses sqlite3's backup API against a read-only connection so any
data still sitting in chat.db-wal is captured correctly.
"""

import sqlite3
from pathlib import Path

DEFAULT_SOURCE = Path("~/Library/Messages/chat.db").expanduser()
DEFAULT_DEST = Path("./data/chat_copy.db")


def copy_chat_db(source: Path = DEFAULT_SOURCE, dest: Path = DEFAULT_DEST) -> Path:
    source = Path(source).expanduser()
    dest = Path(dest).expanduser()

    if not source.exists():
        raise FileNotFoundError(f"source chat.db not found: {source}")

    if dest.resolve() == source.resolve():
        raise ValueError(
            "refusing to copy chat.db onto itself — dest must not be the "
            "source path; the source is read-only and must never be written to"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()

    return dest
