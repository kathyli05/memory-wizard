"""Regression coverage for modern Messages attributed bodies and chat names."""

import base64
import sqlite3
from datetime import datetime

from ingestion.parse_messages import (
    MALFORMED_ATTRIBUTED_BODY,
    NON_TEXT_MESSAGE,
    parse_messages,
)


# Sanitized from a real NSAttributedString typedstream. It contains exactly one
# NSString value ("fixture-message") plus ordinary iMessage attribute metadata.
_ATTRIBUTED_TEMPLATE = base64.b64decode(
    "BAtzdHJlYW10eXBlZIHoA4QBQISEhBJOU0F0dHJpYnV0ZWRTdHJpbmcAhIQI"
    "TlNPYmplY3QAhZKEhIQITlNTdHJpbmcBlIQBKw9maXh0dXJlLW1lc3NhZ2WG"
    "hAJpSQEDkoSEhAxOU0RpY3Rpb25hcnkAlIQBaQGShJaWHV9fa0lNTWVzc2Fn"
    "ZVBhcnRBdHRyaWJ1dGVOYW1lhpKEhIQITlNOdW1iZXIAhIQHTlNWYWx1ZQCU"
    "hAEqhJmZAIaGhg=="
)
_TEMPLATE_TEXT = b"fixture-message"


def _nx_length(length: int) -> bytes:
    if length <= 127:
        return bytes([length])
    if length <= 32767:
        return b"\x81" + length.to_bytes(2, "little", signed=True)
    return b"\x82" + length.to_bytes(4, "little", signed=True)


def attributed_body(text: str) -> bytes:
    """Replace the template's length-prefixed NSString payload."""
    start = _ATTRIBUTED_TEMPLATE.index(_TEMPLATE_TEXT)
    assert _ATTRIBUTED_TEMPLATE[start - 1] == len(_TEMPLATE_TEXT)
    encoded = text.encode("utf-8")
    return (
        _ATTRIBUTED_TEMPLATE[: start - 1]
        + _nx_length(len(encoded))
        + encoded
        + _ATTRIBUTED_TEMPLATE[start + len(_TEMPLATE_TEXT) :]
    )


def _build_db(path, chats, messages, handles=(), participants=()):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
            CREATE TABLE chat (
                ROWID INTEGER PRIMARY KEY,
                chat_identifier TEXT,
                display_name TEXT
            );
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                attributedBody BLOB,
                handle_id INTEGER,
                date INTEGER,
                is_from_me INTEGER
            );
            CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
            CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
            """
        )
        conn.executemany(
            "INSERT INTO chat (ROWID, chat_identifier, display_name) VALUES (?, ?, ?)",
            chats,
        )
        conn.executemany(
            "INSERT INTO message "
            "(ROWID, text, attributedBody, handle_id, date, is_from_me) "
            "VALUES (?, ?, ?, NULL, 0, 1)",
            [(rowid, text, body) for rowid, _, text, body in messages],
        )
        conn.executemany(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            [(chat_id, rowid) for rowid, chat_id, _, _ in messages],
        )
        conn.executemany(
            "INSERT INTO handle (ROWID, id) VALUES (?, ?)", handles
        )
        conn.executemany(
            "INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (?, ?)",
            participants,
        )
        conn.commit()
    finally:
        conn.close()


def test_plain_text_and_valid_attributed_text_are_parsed(tmp_path):
    path = tmp_path / "messages.db"
    _build_db(
        path,
        [(1, "identifier-one", None)],
        [
            (1, 1, "plain text wins", attributed_body("ignored attributed text")),
            (2, 1, None, attributed_body("decoded attributed text")),
            (3, 1, None, attributed_body("Unicode café 🪄")),
        ],
    )

    parsed = parse_messages(path)

    assert [message["text"] for message in parsed] == [
        "plain text wins",
        "decoded attributed text",
        "Unicode café 🪄",
    ]


def test_malformed_and_non_text_messages_get_safe_placeholders(tmp_path):
    path = tmp_path / "messages.db"
    _build_db(
        path,
        [(1, "identifier-one", None)],
        [
            (1, 1, None, b"not a typedstream archive"),
            (2, 1, None, attributed_body("\ufffc")),
            (3, 1, None, None),
        ],
    )

    parsed = parse_messages(path)

    assert [message["text"] for message in parsed] == [
        MALFORMED_ATTRIBUTED_BODY,
        NON_TEXT_MESSAGE,
        NON_TEXT_MESSAGE,
    ]


def test_thread_name_fallbacks_never_return_blank(tmp_path):
    path = tmp_path / "messages.db"
    chats = [
        (1, "identifier-empty", ""),
        (2, "identifier-space", " \t\n "),
        (3, "identifier-null", None),
        (4, "identifier-group", "Named Group"),
        (5, " \t\r\n ", None),
        (6, None, None),
    ]
    messages = [(chat_id, chat_id, "text", None) for chat_id, _, _ in chats]
    _build_db(path, chats, messages)

    names = [message["thread_name"] for message in parse_messages(path)]

    assert names == [
        "identifier-empty",
        "identifier-space",
        "identifier-null",
        "Named Group",
        "[unknown thread]",
        "[unknown thread]",
    ]
    assert all(name.strip() for name in names)
    assert [message["thread_display_name"] for message in parse_messages(path)] == [
        None,
        None,
        None,
        "Named Group",
        None,
        None,
    ]
    assert [message["thread_identifier"] for message in parse_messages(path)] == [
        "identifier-empty",
        "identifier-space",
        "identifier-null",
        "identifier-group",
        None,
        None,
    ]


def test_thread_participants_are_attached_per_thread(tmp_path):
    path = tmp_path / "messages.db"
    _build_db(
        path,
        [(1, "chat123456789", None), (2, "+15551110000", None), (3, "chat987", None)],
        [(1, 1, "group hello", None), (2, 2, "direct hello", None), (3, 3, "orphan", None)],
        handles=[(1, "+15551110000"), (2, "+15552220000"), (3, "alex@example.com")],
        participants=[(1, 2), (1, 3), (1, 1), (2, 1)],
    )

    by_thread = {m["thread_id"]: m["thread_participants"] for m in parse_messages(path)}

    assert by_thread[1] == ("+15551110000", "+15552220000", "alex@example.com")
    assert by_thread[2] == ("+15551110000",)
    assert by_thread[3] == ()  # no chat_handle_join rows -> empty, not an error


def test_timestamp_fixture_remains_a_datetime(tmp_path):
    path = tmp_path / "messages.db"
    _build_db(path, [(1, "identifier", None)], [(1, 1, "text", None)])
    assert isinstance(parse_messages(path)[0]["timestamp"], datetime)
