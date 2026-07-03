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

from ingestion.decode_attributed_body import decode_attributed_body

APPLE_EPOCH = datetime(2001, 1, 1)

# chat.db stored `date` in seconds pre-High Sierra, nanoseconds from
# High Sierra/Catalina onward. Values below this threshold are seconds;
# above it, nanoseconds. (~5e8-8e8 for seconds today vs ~7-8e17 for ns.)
_NS_THRESHOLD = 1_000_000_000_000

_QUERY = """
SELECT
    chat.ROWID AS thread_id,
    COALESCE(chat.display_name, chat.chat_identifier) AS thread_name,
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
            text = decode_attributed_body(row["attributed_body"]) or "[unsupported: attributedBody]"
        else:
            text = ""

        sender = "Me" if is_from_me else (row["handle_id"] or "Unknown")

        messages.append(
            {
                "thread_id": row["thread_id"],
                "thread_name": row["thread_name"],
                "sender": sender,
                "text": text,
                "timestamp": _apple_date_to_datetime(row["date"]),
                "is_from_me": is_from_me,
            }
        )

    return messages
