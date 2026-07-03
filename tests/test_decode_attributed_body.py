"""Tests for ingestion.decode_attributed_body.

This is a heuristic ported from a trusted reference implementation
(ReagentX/imessage-exporter), not verified against real Apple-produced
blobs — there's no macOS environment or real Messages data available here.
These tests are a faithful check of the actual logic (it only ever looks
at the two marker bytes, never the surrounding archive structure), but
real-world compatibility can only be confirmed against real data, which
the user does locally via a free preview run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.decode_attributed_body import decode_attributed_body


def _wrap(prefix: bytes, text: str) -> bytes:
    return b"\x01\x2b" + prefix + text.encode("utf-8") + b"\x86\x84"


def test_decodes_text_between_markers():
    # single-byte length-prefix ("\x02" = length 2), as a real typedstream
    # counted string under 128 chars would carry
    blob = _wrap(b"\x02", "hi")
    assert decode_attributed_body(blob) == "hi"


def test_decodes_longer_text():
    text = "hey, are we still on for saturday?"
    blob = _wrap(bytes([len(text)]), text)
    assert decode_attributed_body(blob) == text


def test_missing_start_marker_returns_none():
    assert decode_attributed_body(b"\x02hi\x86\x84") is None


def test_missing_end_marker_returns_none():
    assert decode_attributed_body(b"\x01\x2b\x02hi") is None


def test_empty_blob_returns_none():
    assert decode_attributed_body(b"") is None


def test_garbage_bytes_do_not_raise():
    assert decode_attributed_body(b"\x00\x01\x02\xff\xfe not real typedstream data") is None


def test_lossy_decode_path_does_not_raise():
    # invalid utf-8 between the markers should fall back to lossy decoding
    # rather than raising
    blob = b"\x01\x2b" + b"\xff\xfe\xfd" + b"\x86\x84"
    result = decode_attributed_body(blob)
    assert result is None or isinstance(result, str)
