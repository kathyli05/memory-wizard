"""Best-effort decoder for iMessage's attributedBody column.

On modern macOS, message text is usually stored as an archived
NSAttributedString blob (Apple's "typedstream" binary format) instead of
the plain `text` column, and `text` is NULL. This is Apple's undocumented
internal serialization format — there is no first-party spec.

Ported from the streamtyped parser in ReagentX/imessage-exporter
(https://github.com/ReagentX/imessage-exporter), a real, actively
maintained tool built for exactly this problem: the message text in a
typedstream-encoded NSAttributedString is bracketed by a fixed start
marker (0x01 0x2b) and end marker (0x86 0x84), with a small fixed-width
junk prefix in front of the actual text.

This is a heuristic, not a full archive parser — it only looks for those
two byte markers and never inspects the surrounding structure. Returns
None (never raises) on anything that doesn't match, so callers can fall
back to an explicit "unsupported" placeholder instead of losing the
message silently or crashing the pipeline on one bad blob.
"""

from __future__ import annotations

_START_MARKER = b"\x01\x2b"
_END_MARKER = b"\x86\x84"


def decode_attributed_body(blob: bytes) -> str | None:
    if not blob:
        return None

    start_idx = blob.find(_START_MARKER)
    if start_idx == -1:
        return None
    remainder = blob[start_idx + len(_START_MARKER):]

    end_idx = remainder.find(_END_MARKER, 1)
    if end_idx == -1:
        return None
    text_bytes = remainder[:end_idx]

    try:
        text = text_bytes.decode("utf-8")
        prefix_len = 1
    except UnicodeDecodeError:
        text = text_bytes.decode("utf-8", errors="replace")
        prefix_len = 3

    text = text[prefix_len:]
    return text or None
