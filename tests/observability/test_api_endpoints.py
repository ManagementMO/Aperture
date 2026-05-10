"""Tests for /api/v3.1 FastAPI endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aperture import __version__
from aperture.observability import event_log_sqlite
from aperture.observability.api_endpoints import create_api_app
from aperture.observability.event_log_sqlite import SQLiteEventLog
from aperture.types import CacheEvent, TokenAttributionEvent


@pytest.fixture
def client(tmp_path):
    log = SQLiteEventLog(tmp_path / "events.db")
    event_log_sqlite.set_default_log(log)
    app = create_api_app()
    yield TestClient(app), log
    event_log_sqlite.set_default_log(None)
    log.close()


def _token_event() -> TokenAttributionEvent:
    return TokenAttributionEvent(
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


def _cache_event() -> CacheEvent:
    return CacheEvent(
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
        cache_key_hash="abc",
        ttl_seconds=300,
        cached_age_seconds=10,
        api_call_avoided=True,
        tokens_saved_estimate=80,
        reason=None,
    )


def test_health_returns_version_and_log_status(client):
    c, _log = client
    response = c.get("/api/v3.1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["aperture_version"] == __version__
    assert body["sqlite_log_configured"] is True
    assert body["token_event_count"] == 0


def test_input_tokens_contributed_returns_aggregated_data(client):
    c, log = client
    log.append_token(_token_event())
    log.append_token(_token_event())
    response = c.post(
        "/api/v3.1/project/usage/input_tokens_contributed",
        json={"group_by": "meta_tool_slug"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_groups"] == 1
    assert body["data"][0]["group_value"] == "COMPOSIO_SEARCH_TOOLS"
    assert body["data"][0]["total_input_tokens_contributed"] == 200
    assert body["data"][0]["total_calls"] == 2
    assert "queried_at" in body


def test_input_tokens_contributed_rejects_bad_group_by(client):
    c, _log = client
    response = c.post(
        "/api/v3.1/project/usage/input_tokens_contributed",
        json={"group_by": "blarghhhhh"},
    )
    assert response.status_code == 400


def test_cache_tokens_saved_returns_aggregated_data(client):
    c, log = client
    log.append_cache(_cache_event())
    response = c.post(
        "/api/v3.1/project/usage/cache_tokens_saved",
        json={"group_by": "tool_slug"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_groups"] == 1
    assert body["data"][0]["group_value"] == "GITHUB_GET_REPO"
    assert body["data"][0]["hits"] == 1
    assert body["data"][0]["tokens_saved"] == 80


def test_endpoints_handle_no_sqlite_log_gracefully(tmp_path):
    """When SQLite log is not configured, endpoints return data: [] not 500."""
    event_log_sqlite.set_default_log(None)
    app = create_api_app()
    c = TestClient(app)
    response = c.post(
        "/api/v3.1/project/usage/input_tokens_contributed",
        json={"group_by": "meta_tool_slug"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert "warning" in body
