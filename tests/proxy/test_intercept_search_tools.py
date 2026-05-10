"""Tests for the SEARCH_TOOLS interception handler."""

from __future__ import annotations

import pytest

from aperture.cache.search_tools_cache import has_schema_or_plan, merge_response, search_query_key, split_response
from aperture.observability.event_emitter import clear_in_memory_events, get_in_memory_cache_events
from aperture.proxy.intercept.search_tools import handle_search_tools
from aperture.types import ExecutionContext


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id="acct_1",
        toolkit_slug=None,
        tool_slug="COMPOSIO_SEARCH_TOOLS",
        meta_tool_slug="COMPOSIO_SEARCH_TOOLS",
        model="gpt-4o",
    )


@pytest.fixture(autouse=True)
def _reset_events():
    clear_in_memory_events()
    yield
    clear_in_memory_events()


def test_search_query_key_is_deterministic_and_versioned():
    k1 = search_query_key("find issues", model="gpt-4o")
    k2 = search_query_key("find issues", model="gpt-4o")
    assert k1 == k2
    assert k1.startswith("aperture:v1:p1:public:none:COMPOSIO_SEARCH_TOOLS:")


def test_search_query_key_varies_by_model_and_query():
    a = search_query_key("find issues", model="gpt-4o")
    b = search_query_key("find issues", model="claude-haiku-4-5")
    c = search_query_key("create issue", model="gpt-4o")
    assert a != b
    assert a != c
    assert b != c


def test_split_response_separates_schema_from_connection_status():
    resp = {
        "tools": [{"name": "GITHUB_GET_REPO"}],
        "plans": [{"id": "p_1"}],
        "connection_status": {"github": "ACTIVE"},
    }
    cacheable, fresh = split_response(resp)
    assert "tools" in cacheable
    assert "plans" in cacheable
    assert "connection_status" not in cacheable
    assert fresh == {"connection_status": {"github": "ACTIVE"}}


def test_merge_response_round_trips():
    cacheable = {"tools": [{"name": "X"}], "plans": []}
    fresh = {"connection_status": {"github": "ACTIVE"}}
    merged = merge_response(cacheable, fresh)
    assert merged["tools"] == [{"name": "X"}]
    assert merged["connection_status"] == {"github": "ACTIVE"}


def test_has_schema_or_plan_recognizes_alt_keys():
    assert has_schema_or_plan({"tools": []}) is True
    assert has_schema_or_plan({"matched_tools": []}) is True
    assert has_schema_or_plan({"plans": []}) is True
    assert has_schema_or_plan({"random": "thing"}) is False
    assert has_schema_or_plan({}) is False


@pytest.mark.asyncio
async def test_handle_search_tools_forwards_when_cache_misses():
    upstream_calls = []

    async def upstream():
        upstream_calls.append(True)
        return {
            "tools": [{"name": "GITHUB_GET_REPO"}],
            "connection_status": {"github": "ACTIVE"},
        }

    result = await handle_search_tools(
        {"query": "find issues"},
        context=_ctx(),
        upstream_call=upstream,
    )
    assert len(upstream_calls) == 1
    assert "tools" in result


@pytest.mark.asyncio
async def test_handle_search_tools_merges_fresh_connection_status():
    """When fetch_connection_status is provided, it overrides whatever
    came back in the response (or got served from cache)."""

    async def upstream():
        return {"tools": [{"name": "X"}], "connection_status": {"github": "STALE"}}

    async def fetch_status():
        return {"connection_status": {"github": "FRESH"}}

    result = await handle_search_tools(
        {"query": "find"},
        context=_ctx(),
        upstream_call=upstream,
        fetch_connection_status=fetch_status,
    )
    assert result["connection_status"]["github"] == "FRESH"
    assert result["tools"] == [{"name": "X"}]


@pytest.mark.asyncio
async def test_handle_search_tools_emits_cache_event_on_forward():
    """The interceptor under the hood emits a CacheEvent (miss for cold cache)."""

    async def upstream():
        return {"tools": []}

    await handle_search_tools(
        {"query": "find issues"},
        context=_ctx(),
        upstream_call=upstream,
    )
    events = get_in_memory_cache_events()
    # SEARCH_TOOLS is not yet in policy.yaml; expect not_cacheable. The point
    # is that *some* cache event was emitted.
    assert len(events) >= 1
