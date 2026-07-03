"""Persist contact profiles (derived signals only) to ./data/triage.db.

No raw message text is accepted or stored here — only the aggregate
fields produced by contacts.build_profiles.
"""

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contact_profiles (
    thread_id INTEGER PRIMARY KEY,
    thread_name TEXT,
    message_count_90d INTEGER NOT NULL,
    messages_per_day_90d REAL NOT NULL,
    median_response_latency_seconds_365d REAL,
    reply_opportunity_count_365d INTEGER NOT NULL DEFAULT 0,
    replied_within_1h_count_365d INTEGER NOT NULL DEFAULT 0,
    replied_within_1d_count_365d INTEGER NOT NULL DEFAULT 0,
    replied_within_3d_count_365d INTEGER NOT NULL DEFAULT 0,
    replied_within_7d_count_365d INTEGER NOT NULL DEFAULT 0,
    conversation_count_365d INTEGER NOT NULL,
    initiation_ratio_me_365d REAL,
    computed_at TEXT NOT NULL
);
"""

_UPSERT = """
INSERT INTO contact_profiles (
    thread_id, thread_name, message_count_90d, messages_per_day_90d,
    median_response_latency_seconds_365d, reply_opportunity_count_365d,
    replied_within_1h_count_365d, replied_within_1d_count_365d,
    replied_within_3d_count_365d, replied_within_7d_count_365d,
    conversation_count_365d,
    initiation_ratio_me_365d, computed_at
) VALUES (
    :thread_id, :thread_name, :message_count_90d, :messages_per_day_90d,
    :median_response_latency_seconds_365d, :reply_opportunity_count_365d,
    :replied_within_1h_count_365d, :replied_within_1d_count_365d,
    :replied_within_3d_count_365d, :replied_within_7d_count_365d,
    :conversation_count_365d,
    :initiation_ratio_me_365d, :computed_at
)
ON CONFLICT(thread_id) DO UPDATE SET
    thread_name=excluded.thread_name,
    message_count_90d=excluded.message_count_90d,
    messages_per_day_90d=excluded.messages_per_day_90d,
    median_response_latency_seconds_365d=excluded.median_response_latency_seconds_365d,
    reply_opportunity_count_365d=excluded.reply_opportunity_count_365d,
    replied_within_1h_count_365d=excluded.replied_within_1h_count_365d,
    replied_within_1d_count_365d=excluded.replied_within_1d_count_365d,
    replied_within_3d_count_365d=excluded.replied_within_3d_count_365d,
    replied_within_7d_count_365d=excluded.replied_within_7d_count_365d,
    conversation_count_365d=excluded.conversation_count_365d,
    initiation_ratio_me_365d=excluded.initiation_ratio_me_365d,
    computed_at=excluded.computed_at
"""


def init_db(db_path: Path) -> None:
    db_path = Path(db_path)
    parent_existed = db_path.parent.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed:
        # owner-only when we created it (never tighten a pre-existing user dir)
        os.chmod(db_path.parent, 0o700)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(contact_profiles)")}
        additive_columns = (
            "reply_opportunity_count_365d",
            "replied_within_1h_count_365d",
            "replied_within_1d_count_365d",
            "replied_within_3d_count_365d",
            "replied_within_7d_count_365d",
        )
        for name in additive_columns:
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE contact_profiles ADD COLUMN {name} "
                    "INTEGER NOT NULL DEFAULT 0"
                )
        conn.commit()
    finally:
        conn.close()


def upsert_profiles(db_path: Path, profiles: list[dict]) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(_UPSERT, profiles)
        conn.commit()
    finally:
        conn.close()
