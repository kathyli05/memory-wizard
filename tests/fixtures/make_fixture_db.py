"""Build a synthetic SQLite db that mirrors chat.db's real table structure.

Used only to sanity-check ingestion.parse_messages and contacts.build_profiles
against a known schema — this is NOT real message data. There is no macOS
Messages database available in this environment to copy from.

Thread 1 (1:1) has 3 conversations (gaps >24h) alternating who initiates,
so initiation-ratio logic gets exercised in both directions. Thread 2
(group chat) has 2 conversations, both initiated by the same contact, as
a contrasting case. Both threads have multiple incoming-run -> my-reply
transitions so median response latency has more than one sample.

Threads 3, 4, and 5 exist to exercise triage.detect_unanswered: their last
message is timed relative to build time (not a fixed 2026 date) so the
"is this older than the threshold" / "is this within the lookback window"
checks are correct whenever the fixture is built. Thread 3 ends with an
incoming message ~3 days old (a triage candidate under the 24h default);
thread 4 ends with one ~2 hours old (not yet a candidate under the
default, but becomes one under a shorter threshold — useful for testing
the boundary); thread 5 ends with one ~200 days old (past the 24h
threshold but outside the default 150-day lookback window — excluded by
default, included when the window is disabled or widened).
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
            [
                (1, "+15551234567"),
                (2, "+15557654321"),
                (3, "+15556667777"),
                (4, "+15554443333"),
            ],
        )

        conn.executemany(
            "INSERT INTO chat (ROWID, chat_identifier, display_name) VALUES (?, ?, ?)",
            [
                (1, "+15551234567", None),
                (2, "chat123456789", "Weekend Trip Planning"),
                (3, "+15556667777", None),
                (4, "+15554443333", None),
                (5, "+15559998888", None),
            ],
        )

        # (rowid, text, handle_id, is_from_me, datetime)
        thread_1 = [
            # conversation A — they initiate
            (1, "hey, are we still on for saturday?", 1, 0, datetime(2026, 6, 1, 10, 0)),
            (2, "yeah! what time works", None, 1, datetime(2026, 6, 1, 11, 30)),
            (3, "noon good?", 1, 0, datetime(2026, 6, 1, 11, 32)),
            (4, "works for me", None, 1, datetime(2026, 6, 1, 11, 40)),
            (5, "see you then", 1, 0, datetime(2026, 6, 1, 11, 41)),
            # conversation B (gap >24h) — I initiate
            (6, "hey I'm running late", None, 1, datetime(2026, 6, 5, 9, 0)),
            (7, "no worries, see you soon", 1, 0, datetime(2026, 6, 5, 9, 20)),
            # conversation C (gap >24h) — they initiate
            (8, "you around this weekend?", 1, 0, datetime(2026, 6, 15, 8, 0)),
            (9, "yes! let's do something", None, 1, datetime(2026, 6, 15, 20, 0)),
        ]
        thread_2 = [
            # conversation A — handle 1 initiates
            (10, "who's driving on friday", 1, 0, datetime(2026, 6, 10, 9, 0)),
            (11, "I can take my car", 2, 0, datetime(2026, 6, 10, 9, 5)),
            (12, "sounds good, I'll bring snacks", None, 1, datetime(2026, 6, 10, 9, 10)),
            (13, "packing list?", 1, 0, datetime(2026, 6, 10, 9, 12)),
            (14, "I'll send one tonight", None, 1, datetime(2026, 6, 10, 9, 20)),
            # conversation B (gap >24h) — handle 1 initiates again
            (15, "hotel confirmed btw", 1, 0, datetime(2026, 6, 25, 14, 0)),
            (16, "awesome, thanks!", None, 1, datetime(2026, 6, 25, 14, 30)),
        ]

        build_time = datetime.now()
        thread_3 = [
            (17, "let's catch up soon", None, 1, build_time - timedelta(days=10)),
            (18, "hey, haven't heard from you in a while, you doing ok?", 3, 0,
             build_time - timedelta(days=3)),
        ]
        thread_4 = [
            (19, "on my way!", 4, 0, build_time - timedelta(hours=2)),
        ]
        thread_5 = [
            (20, "long time no talk, we should catch up sometime", 5, 0,
             build_time - timedelta(days=200)),
        ]

        rows = [
            (rowid, text, handle_id, is_from_me, _apple_ns(dt))
            for rowid, text, handle_id, is_from_me, dt
            in thread_1 + thread_2 + thread_3 + thread_4 + thread_5
        ]

        conn.executemany(
            "INSERT INTO message (ROWID, text, handle_id, is_from_me, date) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )

        conn.executemany(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            [(1, i) for i in range(1, 10)] + [(2, i) for i in range(10, 17)]
            + [(3, 17), (3, 18), (4, 19), (5, 20)],
        )

        conn.commit()
    finally:
        conn.close()

    return path


if __name__ == "__main__":
    fixture_path = build_fixture_db()
    print(f"built fixture db at {fixture_path}")
