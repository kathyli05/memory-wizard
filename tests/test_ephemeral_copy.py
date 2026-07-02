"""Tests for ingestion.copy_chat_db.ephemeral_copy — the whole point is that
no raw message copy is left on disk after the caller is done with it, even
if the caller's code raises."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import ephemeral_copy
from tests.fixtures.make_fixture_db import build_fixture_db


def test_ephemeral_copy_is_deleted_after_the_with_block(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    with ephemeral_copy(source=source, dest=dest) as path:
        assert path == dest
        assert path.exists()

    assert not dest.exists()


def test_ephemeral_copy_is_deleted_even_if_the_block_raises(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    dest = tmp_path / "copy.db"

    try:
        with ephemeral_copy(source=source, dest=dest) as path:
            assert path.exists()
            raise RuntimeError("simulated failure inside the with block")
    except RuntimeError:
        pass

    assert not dest.exists()
