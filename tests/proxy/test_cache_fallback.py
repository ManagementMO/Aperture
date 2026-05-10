"""Tests for the proxy's cache-failure fallback behavior.

Hard rule (Plan-Agent 1 §8): if the cache layer raises, the proxy MUST still
forward to upstream. The `safe()` decorator on cache lookups ensures this.
"""

from __future__ import annotations

import pytest

from aperture.proxy.errors import safe
from aperture.proxy.intercept.search_tools import handle_search_tools
from aperture.types import ExecutionContext


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id="acct_1",
        toolkit_slug=None,
        tool_slug=None,
        meta_tool_slug=None,
        model="gpt-4o",
    )


@pytest.mark.asyncio
async def test_safe_decorator_returns_fallback_on_exception():
    @safe(fallback_value="fallback")
    async def boom():
        raise RuntimeError("kaboom")

    result = await boom()
    assert result == "fallback"


@pytest.mark.asyncio
async def test_safe_decorator_passes_through_on_success():
    @safe(fallback_value="fallback")
    async def ok():
        return "real"

    result = await ok()
    assert result == "real"


@pytest.mark.asyncio
async def test_search_tools_falls_back_to_upstream_when_cache_layer_breaks(monkeypatch):
    """When the bridge's cache lookup raises, search_tools must still return
    the upstream response."""

    async def broken_cache(**kwargs):
        raise RuntimeError("redis down")

    # Inject a broken cache by patching the bridge function search_tools uses.
    from aperture.proxy.intercept import search_tools as st_module

    original = st_module.cached_or_forward
    monkeypatch.setattr(st_module, "cached_or_forward", broken_cache)

    upstream_calls = []

    async def upstream():
        upstream_calls.append(True)
        return {"tools": [{"name": "X"}]}

    result = await handle_search_tools(
        {"query": "anything"},
        context=_ctx(),
        upstream_call=upstream,
    )
    # Despite the cache being broken, the response came back.
    assert result == {"tools": [{"name": "X"}]}
    assert len(upstream_calls) == 1

    # Restore the real function so other tests don't see the patch.
    monkeypatch.setattr(st_module, "cached_or_forward", original)
