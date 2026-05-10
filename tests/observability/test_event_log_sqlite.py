"""Tests for the SQLite event log."""

from __future__ import annotations

from datetime import datetime, timezone


from aperture import __version__
from aperture.observability.event_log_sqlite import SQLiteEventLog
from aperture.types import CacheEvent, TokenAttributionEvent


def _token_event(**overrides) -> TokenAttributionEvent:
    base = dict(
        event_type="meta_tool_response",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id="acct_1",
        toolkit_slug="github",
        tool_slug=None,
        meta_tool_slug="COMPOSIO_SEARCH_TOOLS",
        payload_kind="schema",
        model="gpt-4o",
        tokenizer="o200k_base",
        tokenizer_is_approximate=False,
        raw_payload_bytes=400,
        compressed_payload_bytes=400,
        raw_tokens=100,
        compressed_tokens=100,
        input_tokens_contributed=100,
        tokens_saved=0,
        compression_ratio=1.0,
        cache_status=None,
        aperture_version=__version__,
        session_turn=1,
    )
    base.update(overrides)
    return TokenAttributionEvent(**base)


def _cache_event(**overrides) -> CacheEvent:
    base = dict(
        event_type="cache_lookup",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id="acct_1",
        tool_slug="GITHUB_GET_REPO",
        toolkit_slug="github",
        cache_status="hit",
        cache_scope="public",
        cache_key_hash="abc123",
        ttl_seconds=300,
        cached_age_seconds=42,
        api_call_avoided=True,
        tokens_saved_estimate=80,
        reason=None,
    )
    base.update(overrides)
    return CacheEvent(**base)


def test_creates_db_and_tables(tmp_path):
    log = SQLiteEventLog(tmp_path / "events.db")
    assert log.count_tokens() == 0
    assert log.count_cache() == 0
    log.close()


def test_appends_token_event(tmp_path):
    log = SQLiteEventLog(tmp_path / "events.db")
    log.append_token(_token_event())
    assert log.count_tokens() == 1
    rows = log.all_token_events()
    assert rows[0]["event_type"] == "meta_tool_response"
    assert rows[0]["meta_tool_slug"] == "COMPOSIO_SEARCH_TOOLS"
    assert rows[0]["session_turn"] == 1
    assert rows[0]["aperture_version"] == __version__
    log.close()


def test_appends_cache_event(tmp_path):
    log = SQLiteEventLog(tmp_path / "events.db")
    log.append_cache(_cache_event())
    assert log.count_cache() == 1
    rows = log.all_cache_events()
    assert rows[0]["cache_status"] == "hit"
    assert rows[0]["api_call_avoided"] == 1
    log.close()


def test_persistence_across_instances(tmp_path):
    db = tmp_path / "events.db"
    log_a = SQLiteEventLog(db)
    log_a.append_token(_token_event(meta_tool_slug="COMPOSIO_SEARCH_TOOLS"))
    log_a.close()

    log_b = SQLiteEventLog(db)
    assert log_b.count_tokens() == 1
    log_b.close()


def test_emit_token_event_writes_to_sqlite_when_default_log_set(tmp_path, monkeypatch):
    """The event_emitter writes to SQLite when get_default_log() returns a log."""
    from aperture.observability import event_emitter, event_log_sqlite

    log = SQLiteEventLog(tmp_path / "events.db")
    event_log_sqlite.set_default_log(log)

    event_emitter.clear_in_memory_events()
    event_emitter.emit_token_event(_token_event())
    event_emitter.emit_cache_event(_cache_event())

    assert log.count_tokens() == 1
    assert log.count_cache() == 1

    # Cleanup so other tests don't pick up this default.
    event_log_sqlite.set_default_log(None)
    log.close()
