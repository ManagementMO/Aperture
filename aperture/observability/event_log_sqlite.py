"""SQLite event log alongside the existing JSONL sink.

Plan + handoff §13.2: events flow into a SQLite event log queryable by the
v3.1 API endpoints. JSONL is preserved as a secondary export for grep-based
debugging; SQLite is the source of truth for aggregations.

Schema is intentionally flat — one row per event with all fields columnized.
This makes `group_by` queries straightforward without JSON-path tricks.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aperture.types import CacheEvent, TokenAttributionEvent


_TOKEN_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS token_events (
    rowid              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type         TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    project_id         TEXT,
    user_id            TEXT,
    session_id         TEXT,
    session_turn       INTEGER,
    connected_account_id TEXT,
    toolkit_slug       TEXT,
    tool_slug          TEXT,
    meta_tool_slug     TEXT,
    payload_kind       TEXT NOT NULL,
    model              TEXT,
    tokenizer          TEXT NOT NULL,
    tokenizer_is_approximate INTEGER NOT NULL,
    raw_payload_bytes  INTEGER,
    compressed_payload_bytes INTEGER,
    raw_tokens         INTEGER,
    compressed_tokens  INTEGER,
    input_tokens_contributed INTEGER NOT NULL,
    tokens_saved       INTEGER NOT NULL,
    compression_ratio  REAL,
    cache_status       TEXT,
    aperture_version   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_timestamp ON token_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_token_meta_tool ON token_events(meta_tool_slug);
CREATE INDEX IF NOT EXISTS idx_token_user ON token_events(user_id);
CREATE INDEX IF NOT EXISTS idx_token_session ON token_events(session_id);
CREATE INDEX IF NOT EXISTS idx_token_toolkit ON token_events(toolkit_slug);
"""

_CACHE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS cache_events (
    rowid              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type         TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    project_id         TEXT,
    user_id            TEXT,
    session_id         TEXT,
    connected_account_id TEXT,
    tool_slug          TEXT NOT NULL,
    toolkit_slug       TEXT,
    cache_status       TEXT NOT NULL,
    cache_scope        TEXT NOT NULL,
    cache_key_hash     TEXT,
    ttl_seconds        INTEGER,
    cached_age_seconds INTEGER,
    api_call_avoided   INTEGER NOT NULL,
    tokens_saved_estimate INTEGER NOT NULL,
    reason             TEXT
);
CREATE INDEX IF NOT EXISTS idx_cache_timestamp ON cache_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_cache_tool ON cache_events(tool_slug);
CREATE INDEX IF NOT EXISTS idx_cache_status ON cache_events(cache_status);
"""


class SQLiteEventLog:
    """Thread-safe SQLite-backed event sink.

    Single writer, many readers. We use a per-instance threading.Lock around
    the connection because sqlite3.Connection is not threadsafe by default.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_TOKEN_TABLE_DDL)
            self._conn.executescript(_CACHE_TABLE_DDL)

    def append_token(self, event: TokenAttributionEvent) -> None:
        row = asdict(event)
        # Coerce bool to int for SQLite.
        row["tokenizer_is_approximate"] = int(bool(row["tokenizer_is_approximate"]))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO token_events (
                    event_type, timestamp, project_id, user_id, session_id,
                    session_turn, connected_account_id, toolkit_slug, tool_slug,
                    meta_tool_slug, payload_kind, model, tokenizer,
                    tokenizer_is_approximate, raw_payload_bytes,
                    compressed_payload_bytes, raw_tokens, compressed_tokens,
                    input_tokens_contributed, tokens_saved, compression_ratio,
                    cache_status, aperture_version
                ) VALUES (
                    :event_type, :timestamp, :project_id, :user_id, :session_id,
                    :session_turn, :connected_account_id, :toolkit_slug, :tool_slug,
                    :meta_tool_slug, :payload_kind, :model, :tokenizer,
                    :tokenizer_is_approximate, :raw_payload_bytes,
                    :compressed_payload_bytes, :raw_tokens, :compressed_tokens,
                    :input_tokens_contributed, :tokens_saved, :compression_ratio,
                    :cache_status, :aperture_version
                )
                """,
                row,
            )

    def append_cache(self, event: CacheEvent) -> None:
        row = asdict(event)
        row["api_call_avoided"] = int(bool(row["api_call_avoided"]))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cache_events (
                    event_type, timestamp, project_id, user_id, session_id,
                    connected_account_id, tool_slug, toolkit_slug, cache_status,
                    cache_scope, cache_key_hash, ttl_seconds, cached_age_seconds,
                    api_call_avoided, tokens_saved_estimate, reason
                ) VALUES (
                    :event_type, :timestamp, :project_id, :user_id, :session_id,
                    :connected_account_id, :tool_slug, :toolkit_slug, :cache_status,
                    :cache_scope, :cache_key_hash, :ttl_seconds, :cached_age_seconds,
                    :api_call_avoided, :tokens_saved_estimate, :reason
                )
                """,
                row,
            )

    @contextmanager
    def cursor(self):
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def count_tokens(self) -> int:
        with self.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM token_events")
            return int(cur.fetchone()[0])

    def count_cache(self) -> int:
        with self.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cache_events")
            return int(cur.fetchone()[0])

    def all_token_events(self) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM token_events ORDER BY rowid")
            return [dict(r) for r in cur.fetchall()]

    def all_cache_events(self) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM cache_events ORDER BY rowid")
            return [dict(r) for r in cur.fetchall()]


_DEFAULT_LOG: SQLiteEventLog | None = None


def get_default_log(db_path: Path | str | None = None) -> SQLiteEventLog | None:
    """Lazy module-level event log. Returns None if no path is provided AND
    no APERTURE_SQLITE_EVENT_LOG env var is set — callers MUST handle None."""
    global _DEFAULT_LOG
    import os

    if _DEFAULT_LOG is not None:
        return _DEFAULT_LOG
    path = db_path or os.getenv("APERTURE_SQLITE_EVENT_LOG")
    if not path:
        return None
    _DEFAULT_LOG = SQLiteEventLog(path)
    return _DEFAULT_LOG


def set_default_log(log: SQLiteEventLog | None) -> None:
    global _DEFAULT_LOG
    _DEFAULT_LOG = log
