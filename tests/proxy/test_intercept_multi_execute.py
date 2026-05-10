"""Tests for the MULTI_EXECUTE_TOOL partial-batch handler."""

from __future__ import annotations

import pytest

from aperture.observability.event_emitter import clear_in_memory_events
from aperture.proxy.intercept.multi_execute import (
    _extract_results,
    _inner_tool_calls,
    handle_multi_execute,
)
from aperture.types import ExecutionContext


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        project_id="p1",
        user_id="u1",
        session_id="s1",
        connected_account_id="acct_1",
        toolkit_slug=None,
        tool_slug="COMPOSIO_MULTI_EXECUTE_TOOL",
        meta_tool_slug="COMPOSIO_MULTI_EXECUTE_TOOL",
        model="gpt-4o",
    )


@pytest.fixture(autouse=True)
def _reset():
    clear_in_memory_events()
    yield
    clear_in_memory_events()


def test_inner_tool_calls_handles_alt_field_names():
    assert _inner_tool_calls({"tool_calls": [{"a": 1}]}) == [{"a": 1}]
    assert _inner_tool_calls({"calls": [{"a": 1}]}) == [{"a": 1}]
    assert _inner_tool_calls({"executions": [{"a": 1}]}) == [{"a": 1}]
    assert _inner_tool_calls({"tools": [{"a": 1}]}) == [{"a": 1}]
    assert _inner_tool_calls({}) == []
    assert _inner_tool_calls({"tool_calls": "not-a-list"}) == []


def test_extract_results_returns_per_call_results():
    assert _extract_results({"results": [1, 2, 3]}, expected=3) == [1, 2, 3]
    assert _extract_results({"responses": [1, 2]}, expected=2) == [1, 2]
    assert _extract_results([1, 2, 3], expected=3) == [1, 2, 3]
    assert _extract_results({}, expected=2) == [None, None]


@pytest.mark.asyncio
async def test_multi_execute_no_subset_callback_forwards_full():
    """Without upstream_call_subset, partial-batch is disabled."""
    full_calls = []

    async def upstream():
        full_calls.append(True)
        return {"results": [{"r": 1}]}

    arguments = {"tool_calls": [{"tool_slug": "GITHUB_GET_REPO", "arguments": {}}]}
    result = await handle_multi_execute(arguments, context=_ctx(), upstream_call=upstream)
    assert len(full_calls) == 1
    assert result["results"] == [{"r": 1}]


@pytest.mark.asyncio
async def test_multi_execute_zero_hits_falls_back_to_full_forward():
    """All-write inner batch → no cache hits → falls back to upstream_call (full)."""
    subset_received = {"calls": None}
    full_called = {"count": 0}

    async def upstream_full():
        full_called["count"] += 1
        return {"results": [{"r": 1}, {"r": 2}]}

    async def upstream_subset(calls):
        subset_received["calls"] = list(calls)
        return {"results": [{"r": "from_upstream"} for _ in calls]}

    arguments = {
        "tool_calls": [
            {"tool_slug": "GMAIL_SEND_EMAIL", "arguments": {"to": "x"}},
            {"tool_slug": "GMAIL_SEND_EMAIL", "arguments": {"to": "y"}},
        ],
    }
    result = await handle_multi_execute(
        arguments,
        context=_ctx(),
        upstream_call=upstream_full,
        upstream_call_subset=upstream_subset,
    )
    # When ZERO inner tools cache, we deliberately skip the subset path
    # (it would just forward everything anyway) and do one full forward.
    assert full_called["count"] == 1
    assert subset_received["calls"] is None  # subset path NOT taken
    assert result["results"] == [{"r": 1}, {"r": 2}]


@pytest.mark.asyncio
async def test_multi_execute_partial_batch_forwards_only_misses(tmp_path):
    """A real partial-batch run: prime the cache with one cacheable inner
    tool, then a 2-tool batch with [hit, miss] should forward ONLY the miss
    via upstream_call_subset and merge cached hit + upstream miss back into
    the original ordering.

    Per adversarial review 2026-05-10: the previous version of this test
    didn't actually verify the subset callback received the misses-only
    list — it only checked shape. This version locks the actual semantics.
    """
    from aperture.cache.redis_store import InMemoryCacheStore
    from aperture.proxy import cache_bridge

    # Inject a fresh in-memory store and prime it with a hit for tool A.
    store = InMemoryCacheStore()
    cache_bridge.set_default_store(store)

    ctx = _ctx()

    # Pre-populate cache for GITHUB_LIST_REPOSITORY_ISSUES with specific args.
    # Use the real key_builder so the entry actually shows up on lookup.
    from aperture.cache.policy import load_cache_policy
    from aperture.cache.key_builder import build_cache_key
    cached_args = {"owner": "ACME", "repo": "X"}
    policy = load_cache_policy("GITHUB_LIST_REPOSITORY_ISSUES")
    key = build_cache_key("GITHUB_LIST_REPOSITORY_ISSUES", cached_args, ctx, policy)
    assert key is not None, "policy.yaml should mark this slug as cacheable+account scope"
    store.set(key, {"primed": "from_cache", "title": "Login broken"}, ttl_seconds=900)

    subset_received = {"calls": None}
    full_called = {"count": 0}

    async def upstream_full():
        full_called["count"] += 1
        return {"results": [{"primed": "wrong"}, {"miss": "wrong"}]}

    async def upstream_subset(calls):
        subset_received["calls"] = list(calls)
        return {"results": [{"miss_resolved": True, "args": calls[0].get("arguments")}]}

    arguments = {
        "tool_calls": [
            # idx 0: cache HIT
            {"tool_slug": "GITHUB_LIST_REPOSITORY_ISSUES", "arguments": cached_args},
            # idx 1: cache MISS (GMAIL_SEND_EMAIL is non-cacheable write)
            {"tool_slug": "GMAIL_SEND_EMAIL", "arguments": {"to": "alice@example.com"}},
        ],
    }
    result = await handle_multi_execute(
        arguments,
        context=ctx,
        upstream_call=upstream_full,
        upstream_call_subset=upstream_subset,
    )

    # The full upstream MUST NOT be called — partial-batch wins.
    assert full_called["count"] == 0, "partial-batch path must skip full forward when ANY inner tool hits cache"

    # Subset MUST be called with ONLY the miss.
    assert subset_received["calls"] is not None, "subset callback must be invoked when there are misses"
    assert len(subset_received["calls"]) == 1
    assert subset_received["calls"][0]["tool_slug"] == "GMAIL_SEND_EMAIL"

    # Final result preserves original ordering: cached at idx 0, upstream at idx 1.
    assert len(result["results"]) == 2
    assert result["results"][0] == {"primed": "from_cache", "title": "Login broken"}
    assert result["results"][1]["miss_resolved"] is True
    assert result["results"][1]["args"] == {"to": "alice@example.com"}

    # Telemetry record on the assembled response.
    aperture_meta = result.get("_aperture_partial_batch")
    assert aperture_meta is not None
    assert aperture_meta["total"] == 2
    assert aperture_meta["from_cache"] == 1
    assert aperture_meta["from_upstream"] == 1

    # Cleanup so other tests don't see this store
    cache_bridge.set_default_store(InMemoryCacheStore())
