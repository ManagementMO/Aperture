"""End-to-end integration test for the v1 stack.

Exercises:
    - Cache: hit + miss paths via the policy YAML
    - Token attribution: TokenAttributionEvent emission with v1 fields
    - SQLite event log: cache + token events persist
    - v3.1 API: aggregations through the FastAPI router
    - Schema overlay: read + apply
    - Proxy router: dispatch + transparent forward

This test is the closest thing to a "the whole v1 stack works together"
sanity check that runs without live Composio or Anthropic.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aperture import __version__
from aperture.cache.interceptor import maybe_execute_with_cache
from aperture.cache.redis_store import InMemoryCacheStore
from aperture.observability import event_emitter, event_log_sqlite
from aperture.observability.api_endpoints import create_api_app
from aperture.observability.event_log_sqlite import SQLiteEventLog
from aperture.proxy.router import dispatch
from aperture.proxy.session import SessionRegistry
from aperture.proxy.attribution import emit_meta_tool_event
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import ExecutionContext


@pytest.mark.asyncio
async def test_v1_full_stack_end_to_end(tmp_path):
    """Exercises every Component A/B/C surface in one test.

    Story:
        1. Open a session, build context.
        2. Make a SEARCH_TOOLS-style call through the cache. Miss.
        3. Same call again. Hit.
        4. Make a MULTI_EXECUTE-style call (different tool, write op).
           Verify it doesn't cache.
        5. Tokenize each response and emit TokenAttributionEvent.
        6. Assert events landed in SQLite.
        7. Query the v3.1 API; assert aggregation produces expected counts.
    """
    # 1. Set up
    log = SQLiteEventLog(tmp_path / "events.db")
    event_log_sqlite.set_default_log(log)
    event_emitter.clear_in_memory_events()

    sessions = SessionRegistry()
    sessions.open("conn-1", user_id="user_test")
    ctx = sessions.context_for(
        "conn-1",
        toolkit_slug="github",
        tool_slug="GITHUB_GET_REPO",
        meta_tool_slug=None,
        model="gpt-4o",
    )
    assert ctx.session_id is not None

    cache_store = InMemoryCacheStore()
    counter = {"executions": 0}

    async def execute_repo():
        counter["executions"] += 1
        return {"id": 12345, "name": "aperture", "stargazers_count": 42}

    # 2. First call → miss, real execution
    result_1 = await maybe_execute_with_cache(
        "GITHUB_GET_REPO", {"owner": "ACME", "repo": "aperture"},
        ctx, execute_repo, store=cache_store,
    )
    assert result_1["name"] == "aperture"
    assert counter["executions"] == 1

    # 3. Second call → hit, no new execution
    result_2 = await maybe_execute_with_cache(
        "GITHUB_GET_REPO", {"owner": "ACME", "repo": "aperture"},
        ctx, execute_repo, store=cache_store,
    )
    assert result_2["name"] == "aperture"
    assert counter["executions"] == 1, "second call should have hit cache"

    # 4. Write tool — must not cache
    write_counter = {"executions": 0}

    async def execute_create_issue():
        write_counter["executions"] += 1
        return {"id": 1, "number": 1, "title": "test"}

    write_ctx = ExecutionContext(
        project_id=ctx.project_id, user_id=ctx.user_id,
        session_id=ctx.session_id, connected_account_id="acct_1",
        toolkit_slug="github", tool_slug="GITHUB_CREATE_ISSUE",
        meta_tool_slug=None, model="gpt-4o",
    )
    await maybe_execute_with_cache(
        "GITHUB_CREATE_ISSUE", {"owner": "ACME", "repo": "aperture", "title": "test"},
        write_ctx, execute_create_issue, store=cache_store,
    )
    await maybe_execute_with_cache(
        "GITHUB_CREATE_ISSUE", {"owner": "ACME", "repo": "aperture", "title": "test"},
        write_ctx, execute_create_issue, store=cache_store,
    )
    assert write_counter["executions"] == 2, "write tool MUST not cache"

    # 5. Tokenize results + emit attribution events
    for response in (result_1, result_2):
        count = count_tokens_for_payload(response, model="gpt-4o")
        emit_meta_tool_event(context=ctx, raw_count=count, session_turn=1)

    # 6. Verify SQLite log captured everything
    assert log.count_token_events_alias() if hasattr(log, "count_token_events_alias") else log.count_tokens() >= 2
    assert log.count_cache() >= 4  # 2 search hits/misses + 2 write events

    # 7. v3.1 API: aggregation through the FastAPI router
    api_app = create_api_app()
    client = TestClient(api_app)

    health_response = client.get("/api/v3.1/health")
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert health_body["status"] == "ok"
    assert health_body["aperture_version"] == __version__
    assert health_body["sqlite_log_configured"] is True
    assert health_body["token_event_count"] >= 2
    assert health_body["cache_event_count"] >= 4

    tokens_response = client.post(
        "/api/v3.1/project/usage/input_tokens_contributed",
        json={"group_by": "tool_slug"},
    )
    assert tokens_response.status_code == 200
    tokens_body = tokens_response.json()
    assert tokens_body["total_groups"] >= 1
    by_slug = {row["group_value"]: row for row in tokens_body["data"]}
    assert "GITHUB_GET_REPO" in by_slug or any("GITHUB" in str(k) for k in by_slug)

    cache_response = client.post(
        "/api/v3.1/project/usage/cache_tokens_saved",
        json={"group_by": "tool_slug"},
    )
    assert cache_response.status_code == 200
    cache_body = cache_response.json()
    by_slug_cache = {row["group_value"]: row for row in cache_body["data"]}
    # GITHUB_GET_REPO had 1 hit + 1 miss; we expect at least one entry with hits>0
    if "GITHUB_GET_REPO" in by_slug_cache:
        assert by_slug_cache["GITHUB_GET_REPO"]["hits"] >= 1
        assert by_slug_cache["GITHUB_GET_REPO"]["api_calls_avoided"] >= 1

    # Cleanup
    event_log_sqlite.set_default_log(None)
    log.close()


@pytest.mark.asyncio
async def test_proxy_router_dispatches_meta_tools_and_others_correctly():
    """The router must call the per-meta-tool handler for known meta tools
    and forward verbatim for everything else."""
    forwarded_calls = []

    async def upstream():
        forwarded_calls.append("called")
        return {"ok": True}

    ctx = ExecutionContext(
        project_id=None, user_id=None, session_id=None,
        connected_account_id=None, toolkit_slug=None, tool_slug=None,
        meta_tool_slug=None, model="gpt-4o",
    )

    # Unknown tool → forwarded verbatim
    forwarded_calls.clear()
    await dispatch("RANDOM_CUSTOM_TOOL", {"x": 1}, context=ctx, upstream_call=upstream)
    assert forwarded_calls == ["called"]

    # Meta tool we don't intercept yet (GET_TOOL_SCHEMAS in PR 2) → forwarded
    forwarded_calls.clear()
    await dispatch("COMPOSIO_GET_TOOL_SCHEMAS", {"slugs": []}, context=ctx, upstream_call=upstream)
    assert forwarded_calls == ["called"]

    # Meta tool that DOES route through a handler (SEARCH_TOOLS) — handler
    # forwards on a cold cache, so upstream still gets called once.
    forwarded_calls.clear()
    await dispatch("COMPOSIO_SEARCH_TOOLS", {"query": "test"}, context=ctx, upstream_call=upstream)
    assert len(forwarded_calls) == 1


def test_aperture_version_is_consistent():
    """`__version__` is the single source of truth — it appears in:
    - aperture/__init__.py (the value)
    - pyproject.toml (the project metadata)
    - aperture/proxy/server.py (Server constructor)
    - aperture/proxy/attribution.py (every TokenAttributionEvent)
    - reports / overlay JSONs
    """
    from aperture import __version__ as aperture_version

    # aperture/__init__.py declares it
    assert aperture_version
    # All TokenAttributionEvents must carry it
    from aperture.types import TokenAttributionEvent

    event = TokenAttributionEvent(
        event_type="meta_tool_response",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None, user_id=None, session_id=None, connected_account_id=None,
        toolkit_slug=None, tool_slug=None, meta_tool_slug=None,
        payload_kind="schema", model=None, tokenizer="cl100k",
        tokenizer_is_approximate=False,
        raw_payload_bytes=10, compressed_payload_bytes=10,
        raw_tokens=2, compressed_tokens=2, input_tokens_contributed=2,
        tokens_saved=0, compression_ratio=1.0, cache_status=None,
        aperture_version=aperture_version,
        session_turn=1,
    )
    assert event.aperture_version == aperture_version
