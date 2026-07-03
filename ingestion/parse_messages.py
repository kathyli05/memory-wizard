"""Parse a chat.db copy into a clean per-thread message list.

Schema reference (real chat.db, macOS):
  message            ROWID, text, attributedBody, handle_id, date, is_from_me
  handle             ROWID, id                  (sender phone/email)
  chat               ROWID, chat_identifier, display_name
  chat_message_join  chat_id, message_id        (links messages to threads)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import typedstream
from typedstream.archiving import GenericArchivedObject, TypedGroup
from typedstream.types.foundation import NSString

APPLE_EPOCH = datetime(2001, 1, 1)

MALFORMED_ATTRIBUTED_BODY = "[unsupported: malformed attributedBody]"
UNSUPPORTED_ATTRIBUTED_BODY = "[unsupported: attributedBody]"
NON_TEXT_MESSAGE = "[attachment or non-text message]"

# chat.db stored `date` in seconds pre-High Sierra, nanoseconds from
# High Sierra/Catalina onward. Values below this threshold are seconds;
# above it, nanoseconds. (~5e8-8e8 for seconds today vs ~7-8e17 for ns.)
_NS_THRESHOLD = 1_000_000_000_000

_QUERY = """
SELECT
    chat.ROWID AS thread_id,
    NULLIF(TRIM(chat.display_name, char(9) || char(10) || char(11) ||
                char(12) || char(13) || ' '), '') AS thread_display_name,
    NULLIF(TRIM(chat.chat_identifier, char(9) || char(10) || char(11) ||
                char(12) || char(13) || ' '), '') AS thread_identifier,
    COALESCE(
        NULLIF(TRIM(chat.display_name, char(9) || char(10) || char(11) ||
                    char(12) || char(13) || ' '), ''),
        NULLIF(TRIM(chat.chat_identifier, char(9) || char(10) || char(11) ||
                    char(12) || char(13) || ' '), ''),
        '[unknown thread]'
    ) AS thread_name,
    message.is_from_me AS is_from_me,
    handle.id AS handle_id,
    message.text AS text,
    message.attributedBody AS attributed_body,
    message.date AS date
FROM message
JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
JOIN chat ON chat.ROWID = chat_message_join.chat_id
LEFT JOIN handle ON handle.ROWID = message.handle_id
ORDER BY chat.ROWID, message.date ASC
"""


def _apple_date_to_datetime(date_value: int) -> datetime:
    seconds = date_value / 1_000_000_000 if date_value > _NS_THRESHOLD else date_value
    return APPLE_EPOCH + timedelta(seconds=seconds)


def _decode_attributed_body(blob: bytes) -> str:
    """Decode Messages' NSArchiver-serialized attributed string safely.

    The text is accepted only from the first object field of a structurally
    decoded NSAttributedString root. This deliberately avoids scanning raw
    bytes, which can mistake attribute metadata for message text.
    """
    try:
        root = typedstream.unarchive_from_data(bytes(blob))
    except Exception:
        return MALFORMED_ATTRIBUTED_BODY

    if not isinstance(root, GenericArchivedObject):
        return UNSUPPORTED_ATTRIBUTED_BODY
    if root.clazz.name not in {b"NSAttributedString", b"NSMutableAttributedString"}:
        return UNSUPPORTED_ATTRIBUTED_BODY
    if not root.contents:
        return UNSUPPORTED_ATTRIBUTED_BODY

    string_field = root.contents[0]
    if not isinstance(string_field, TypedGroup):
        return UNSUPPORTED_ATTRIBUTED_BODY
    if string_field.encodings != [b"@"] or len(string_field.values) != 1:
        return UNSUPPORTED_ATTRIBUTED_BODY

    string_object = string_field.values[0]
    if not isinstance(string_object, NSString) or not isinstance(string_object.value, str):
        return UNSUPPORTED_ATTRIBUTED_BODY

    text = string_object.value
    # U+FFFC is the attributed-string attachment placeholder; U+FFFD is used
    # for some app/non-text message parts. Neither alone is readable text.
    if not text or not text.replace("\ufffc", "").replace("\ufffd", "").strip():
        return NON_TEXT_MESSAGE
    return text


def parse_messages(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(_QUERY).fetchall()
    finally:
        conn.close()

    messages = []
    for row in rows:
        is_from_me = bool(row["is_from_me"])

        if row["text"] is not None:
            text = row["text"]
        elif row["attributed_body"] is not None:
            text = _decode_attributed_body(row["attributed_body"])
        else:
            text = NON_TEXT_MESSAGE

        sender = "Me" if is_from_me else (row["handle_id"] or "Unknown")

        messages.append(
            {
                "thread_id": row["thread_id"],
                "thread_name": row["thread_name"],
                "thread_display_name": row["thread_display_name"],
                "thread_identifier": row["thread_identifier"],
                "sender": sender,
                "text": text,
                "timestamp": _apple_date_to_datetime(row["date"]),
                "is_from_me": is_from_me,
            }
        )

    return messages
