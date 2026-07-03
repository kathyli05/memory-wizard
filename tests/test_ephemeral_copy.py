"""Tests for ingestion.copy_chat_db.ephemeral_copy — the whole point is that
no raw message copy is left on disk after the caller is done with it, even
if the caller's code raises. Copies also get unique per-run names so
concurrent runs (dashboard reload + scheduled triage) can never delete or
overwrite each other's copy, and debris from crashed runs is swept once
it's clearly stale."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import ephemeral_copy, sweep_stale_copies
from tests.fixtures.make_fixture_db import build_fixture_db


def test_ephemeral_copy_is_deleted_after_the_with_block(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    with ephemeral_copy(source=source, dest=dest) as path:
        # unique name derived from the base, never the base itself
        assert path.parent == dest.parent
        assert path.name.startswith("copy-") and path.suffix == ".db"
        assert path != dest
        assert path.exists()

    assert not path.exists()
    assert not list(tmp_path.glob("copy*.db"))


def test_ephemeral_copy_is_deleted_even_if_the_block_raises(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    try:
        with ephemeral_copy(source=source, dest=dest) as path:
            assert path.exists()
            raise RuntimeError("simulated failure inside the with block")
    except RuntimeError:
        pass

    assert not path.exists()


def test_concurrent_copies_get_distinct_paths(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    with ephemeral_copy(source=source, dest=dest) as first:
        with ephemeral_copy(source=source, dest=dest) as second:
            assert first != second
            assert first.exists() and second.exists()
        # inner cleanup must not touch the outer copy
        assert first.exists()


def test_stale_copies_are_swept_but_fresh_ones_are_not(tmp_path):
    dest = tmp_path / "copy.db"
    tmp_path.mkdir(exist_ok=True)

    stale = tmp_path / "copy-deadbeef.db"
    stale.write_bytes(b"orphaned snapshot from a crashed run")
    two_hours_ago = time.time() - 7200
    os.utime(stale, (two_hours_ago, two_hours_ago))

    fresh = tmp_path / "copy-cafef00d.db"
    fresh.write_bytes(b"copy belonging to a concurrently running process")

    removed = sweep_stale_copies(dest)

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()


def test_ephemeral_copy_sweeps_stale_debris_on_entry(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    stale = tmp_path / "copy-deadbeef.db"
    stale.write_bytes(b"orphaned snapshot from a crashed run")
    two_hours_ago = time.time() - 7200
    os.utime(stale, (two_hours_ago, two_hours_ago))

    with ephemeral_copy(source=source, dest=dest):
        assert not stale.exists()
