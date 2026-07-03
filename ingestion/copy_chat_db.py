"""Read-only snapshot of the macOS Messages database.

Never opens the source for writing and never touches sidecar files in
place — uses sqlite3's backup API against a read-only connection so any
data still sitting in chat.db-wal is captured correctly.

Ephemeral copies get a unique per-run filename so concurrent users of the
same base path (the dashboard reloading while a scheduled triage run is
mid-read) can never delete or overwrite each other's copy. Copies left
behind by a crashed run are swept on the next ephemeral_copy call once
they're clearly stale.
"""

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULT_SOURCE = Path("~/Library/Messages/chat.db").expanduser()
DEFAULT_DEST = Path("./data/chat_copy.db")

# An ephemeral copy lives for seconds; anything this old is debris from a
# crashed run, not a concurrent one.
STALE_COPY_MAX_AGE_SECONDS = 3600


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

    dest_dir_existed = dest.parent.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest_dir_existed:
        # data/ holds full message snapshots — owner-only, and only when we
        # created the directory (never tighten a pre-existing user dir)
        os.chmod(dest.parent, 0o700)

    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()

    os.chmod(dest, 0o600)
    return dest


def _unique_copy_path(base: Path) -> Path:
    return base.with_name(f"{base.stem}-{uuid.uuid4().hex}{base.suffix}")


def sweep_stale_copies(
    base: Path = DEFAULT_DEST, *, max_age_seconds: float = STALE_COPY_MAX_AGE_SECONDS
) -> int:
    """Delete leftover ephemeral copies (base's stem + unique suffix) older
    than max_age_seconds — snapshots orphaned by a crash/SIGKILL between
    copy and cleanup. Recent siblings are left alone: they may belong to a
    concurrently running process. Returns the number removed."""
    base = Path(base).expanduser()
    if not base.parent.exists():
        return 0

    cutoff = time.time() - max_age_seconds
    removed = 0
    for candidate in base.parent.glob(f"{base.stem}-*{base.suffix}"):
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
                removed += 1
        except FileNotFoundError:
            pass  # another process swept it first
    return removed


@contextmanager
def ephemeral_copy(source: Path = DEFAULT_SOURCE, dest: Path = DEFAULT_DEST):
    """Copy chat.db to a unique path derived from dest, yield the path, then
    delete the copy — so no raw message data lingers on disk longer than one
    pipeline run, and concurrent runs never share a file. Also sweeps stale
    copies a crashed earlier run may have left behind."""
    dest = Path(dest).expanduser()
    sweep_stale_copies(dest)
    path = copy_chat_db(source, _unique_copy_path(dest))
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
