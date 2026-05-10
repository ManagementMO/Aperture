"""Tests for aperture.proxy.router.dispatch.

Verifies the meta-tool routing matrix:
- SEARCH_TOOLS → handle_search_tools
- MULTI_EXECUTE_TOOL → handle_multi_execute
- everything else → transparent forward
"""

from __future__ import annotations

import pytest

from aperture.observability.event_emitter import clear_in_memory_events
from aperture.proxy.router import dispatch
from aperture.types import ExecutionContext


def _ctx(connected_account_id: str | None = "acct_1") -> ExecutionContext:
    return ExecutionContext(
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id=connected_account_id,
        toolkit_slug=None,
        tool_slug=None,
        meta_tool_slug=None,
        model="gpt-4o",
    )


@pytest.fixture(autouse=True)
def _reset_events():
    clear_in_memory_events()
    yield
    clear_in_memory_events()


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_forwards_verbatim():
    forwarded = []

    async def upstream():
        forwarded.append(True)
        return {"ok": True}

    result = await dispatch("MY_CUSTOM_TOOL", {"a": 1}, context=_ctx(), upstream_call=upstream)
    assert forwarded == [True]
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_dispatch_search_tools_routes_to_handler():
    calls = {"upstream": 0}

    async def upstream():
        calls["upstream"] += 1
        return {"tools": [{"name": "GITHUB_GET_REPO"}], "connection_status": {"github": "ACTIVE"}}

    result = await dispatch(
        "COMPOSIO_SEARCH_TOOLS",
        {"query": "find issues"},
        context=_ctx(),
        upstream_call=upstream,
    )
    assert calls["upstream"] == 1
    assert "tools" in result


@pytest.mark.asyncio
async def test_dispatch_multi_execute_no_subset_forwards_full():
    """Without upstream_call_subset, partial-batch is disabled and the whole
    batch goes to upstream regardless of cache state."""
    calls = {"full": 0}

    async def upstream():
        calls["full"] += 1
        return {"results": [{"ok": 1}, {"ok": 2}]}

    result = await dispatch(
        "COMPOSIO_MULTI_EXECUTE_TOOL",
        {"tool_calls": [{"tool_slug": "GITHUB_GET_REPO", "arguments": {"a": 1}}]},
        context=_ctx(),
        upstream_call=upstream,
    )
    assert calls["full"] == 1
    assert result["results"][0]["ok"] == 1


@pytest.mark.asyncio
async def test_dispatch_get_tool_schemas_forwards_verbatim_pr2():
    """PR 2 doesn't intercept GET_TOOL_SCHEMAS — overlay lands in PR 4."""
    calls = {"upstream": 0}

    async def upstream():
        calls["upstream"] += 1
        return {"schemas": []}

    result = await dispatch(
        "COMPOSIO_GET_TOOL_SCHEMAS",
        {"slugs": ["GITHUB_GET_REPO"]},
        context=_ctx(),
        upstream_call=upstream,
    )
    assert calls["upstream"] == 1
    assert "schemas" in result
