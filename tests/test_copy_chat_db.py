"""Guardrail tests: the source Messages database must never be mutated.

These exist because CLAUDE.md makes source immutability a hard constraint —
this test is what keeps that constraint true in code, not just in prose.
"""

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.copy_chat_db import copy_chat_db
from ingestion.parse_messages import parse_messages
from tests.fixtures.make_fixture_db import build_fixture_db


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copy_does_not_modify_source(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")
    before_hash = _sha256(source)
    before_mtime = source.stat().st_mtime_ns

    dest = tmp_path / "copy.db"
    copy_chat_db(source=source, dest=dest)

    assert _sha256(source) == before_hash
    assert source.stat().st_mtime_ns == before_mtime

    # sqlite's backup API rewrites pages, so the copy isn't byte-identical —
    # what matters is that its rows match the source's.
    assert parse_messages(source) == parse_messages(dest)


def test_copy_refuses_to_overwrite_source(tmp_path):
    source = build_fixture_db(tmp_path / "source_chat.db")

    with pytest.raises(ValueError):
        copy_chat_db(source=source, dest=source)

    # a symlink/relative-path route to the same file must be caught too
    alias = tmp_path / "alias.db"
    shutil.copy(source, alias)  # sanity file, not part of the assertion
    alias.unlink()
    alias.symlink_to(source)

    with pytest.raises(ValueError):
        copy_chat_db(source=source, dest=alias)
