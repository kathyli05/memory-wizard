"""Build a synthetic SQLite db that mirrors chat.db's real table structure.

Used only to sanity-check ingestion.parse_messages against a known schema —
this is NOT real message data. There is no macOS Messages database available
in this environment to copy from.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

APPLE_EPOCH = datetime(2001, 1, 1)

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parent / "fixture_chat.db"


def _apple_ns(dt: datetime) -> int:
    return int((dt - APPLE_EPOCH).total_seconds() * 1_000_000_000)


def build_fixture_db(path: Path = DEFAULT_FIXTURE_PATH) -> Path:
    path.unlink(missing_ok=True)
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
            """
        )

        conn.executemany(
            "INSERT INTO handle (ROWID, id) VALUES (?, ?)",
            [(1, "+15551234567"), (2, "+15557654321")],
        )

        conn.executemany(
            "INSERT INTO chat (ROWID, chat_identifier, display_name) VALUES (?, ?, ?)",
            [
                (1, "+15551234567", None),
                (2, "chat123456789", "Weekend Trip Planning"),
            ],
        )

        base = datetime(2026, 6, 20, 9, 0, 0)
        thread_1 = [
            (1, "hey, are we still on for saturday?", 1, 0, 0),
            (2, "yeah! what time works", None, 1, 1),
            (3, "noon good?", 1, 0, 2),
            (4, "works for me", None, 1, 3),
            (5, "see you then", 1, 0, 4),
        ]
        thread_2 = [
            (6, "who's driving on friday", 1, 0, 0),
            (7, "I can drive", None, 1, 1),
            (8, "same, I have the bigger car though", 2, 0, 2),
            (9, "ok you drive then", None, 1, 3),
            (10, "packing list?", 1, 0, 4),
            (11, "I'll send one tonight", None, 1, 5),
            (12, "hotel confirmed btw", 2, 0, 6),
        ]

        rows = []
        for rowid, text, handle_id, is_from_me, minute_offset in thread_1:
            rows.append((rowid, text, handle_id, is_from_me,
                          _apple_ns(base + timedelta(minutes=minute_offset))))
        for rowid, text, handle_id, is_from_me, minute_offset in thread_2:
            rows.append((rowid, text, handle_id, is_from_me,
                          _apple_ns(base + timedelta(hours=3, minutes=minute_offset))))

        conn.executemany(
            "INSERT INTO message (ROWID, text, handle_id, is_from_me, date) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )

        conn.executemany(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            [(1, i) for i in range(1, 6)] + [(2, i) for i in range(6, 13)],
        )

        conn.commit()
    finally:
        conn.close()

    return path


if __name__ == "__main__":
    fixture_path = build_fixture_db()
    print(f"built fixture db at {fixture_path}")
