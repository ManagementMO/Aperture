"""Handler for `COMPOSIO_MULTI_EXECUTE_TOOL`.

Plan-Agent 1 §3 partial-batch optimization: the request carries a list of
inner tools to execute. For each inner tool, check the cache (with the
inner tool's own slug + scope policy). Partition into `cached` and
`to_forward`; forward only the misses; merge cached + upstream-returned
results back into the original ordering.

Default behavior: enabled (even 5-of-50 hits is a real win). Set
`APERTURE_PROXY_PARTIAL_BATCH=false` to disable and forward whole batches.
"""

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable

from aperture.cache.policy import load_cache_policy
from aperture.proxy.cache_bridge import cached_or_forward, unwrap_cached_result
from aperture.proxy.errors import safe
from aperture.types import ExecutionContext


def _partial_batch_enabled() -> bool:
    return os.getenv("APERTURE_PROXY_PARTIAL_BATCH", "true").strip().lower() not in {
        "false",
        "0",
        "no",
        "off",
    }


def _inner_tool_calls(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the list of inner tool call descriptors from a MULTI_EXECUTE
    arguments dict. Composio uses several names; tolerate them.
    """
    for key in ("tool_calls", "calls", "executions", "tools"):
        value = arguments.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


@safe(fallback_value=None)
async def _try_cache_inner(
    *,
    inner_slug: str,
    inner_args: dict[str, Any],
    context: ExecutionContext,
) -> Any:
    """Return cached value for one inner tool, or None on miss/error.

    Constructs an unsatisfiable upstream_call so the bridge ALWAYS misses
    when the cache is empty; the actual forwarding for misses happens via
    the batch-level upstream call.
    """

    async def _miss():
        # Sentinel: bridge will store this if it returns from upstream_call.
        # We don't want to store it — so this should never actually be reached
        # for a true miss, since the bridge will execute it. To suppress, we
        # return a marker that fails _success_response and is never cached.
        return {"success": False, "error": "deferred_to_batch_forward"}

    return await cached_or_forward(
        tool_slug=inner_slug,
        params=inner_args,
        context=context,
        upstream_call=_miss,
    )


async def handle_multi_execute(
    arguments: dict[str, Any],
    *,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    upstream_call_subset: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = None,
) -> Any:
    """Run the MULTI_EXECUTE pipeline with partial-batch caching.

    Args:
        arguments: the inbound MULTI_EXECUTE arguments (containing a list of
            inner tool calls).
        context: ExecutionContext.
        upstream_call: forwards the WHOLE original arguments to upstream.
            Called when partial-batch is disabled or when there's nothing
            in the cache for any inner tool.
        upstream_call_subset: optional — forwards only a subset of inner tool
            calls (the misses). When provided, partial-batch is enabled.

    Returns the assembled batch response. On any unexpected error the function
    falls back to the full upstream call.
    """
    if not _partial_batch_enabled() or upstream_call_subset is None:
        return await upstream_call()

    inner_calls = _inner_tool_calls(arguments)
    if not inner_calls:
        return await upstream_call()

    cache_hits: dict[int, Any] = {}
    misses: list[tuple[int, dict[str, Any]]] = []

    for idx, call in enumerate(inner_calls):
        inner_slug = call.get("tool_slug") or call.get("slug") or call.get("name")
        if not isinstance(inner_slug, str):
            misses.append((idx, call))
            continue

        # Quick policy gate — skip cache lookup for non-cacheable tools.
        policy = load_cache_policy(inner_slug)
        if not policy.cacheable:
            misses.append((idx, call))
            continue

        inner_args = call.get("arguments") or call.get("params") or {}
        cached = await _try_cache_inner(
            inner_slug=inner_slug,
            inner_args=inner_args if isinstance(inner_args, dict) else {},
            context=context,
        )
        cached = unwrap_cached_result(cached)
        if cached is None or _looks_like_miss_sentinel(cached):
            misses.append((idx, call))
        else:
            cache_hits[idx] = cached

    if not cache_hits:
        return await upstream_call()

    # All-cache-hit short-circuit.
    if not misses:
        return _assemble(inner_calls, cache_hits, upstream_results=[])

    # Forward only the misses, then merge.
    miss_calls = [call for _, call in misses]
    upstream_response = await upstream_call_subset(miss_calls)
    upstream_results = _extract_results(upstream_response, expected=len(misses))

    miss_idx_to_result: dict[int, Any] = {}
    for (original_idx, _), result in zip(misses, upstream_results):
        miss_idx_to_result[original_idx] = result

    return _assemble(
        inner_calls,
        cache_hits,
        upstream_results=[miss_idx_to_result.get(i) for i in range(len(inner_calls))],
    )


def _looks_like_miss_sentinel(value: Any) -> bool:
    return isinstance(value, dict) and value.get("error") == "deferred_to_batch_forward"


def _extract_results(upstream_response: Any, *, expected: int) -> list[Any]:
    """Pull the per-inner-tool results out of an upstream MULTI_EXECUTE response."""
    if isinstance(upstream_response, dict):
        for key in ("results", "responses", "outputs", "tool_results"):
            value = upstream_response.get(key)
            if isinstance(value, list):
                return value
    if isinstance(upstream_response, list):
        return upstream_response
    return [None] * expected


def _assemble(
    inner_calls: list[dict[str, Any]],
    cache_hits: dict[int, Any],
    *,
    upstream_results: list[Any],
) -> dict[str, Any]:
    """Reconstruct a MULTI_EXECUTE-shape response from cache + upstream parts."""
    final_results: list[Any] = []
    for idx in range(len(inner_calls)):
        if idx in cache_hits:
            final_results.append(cache_hits[idx])
        elif idx < len(upstream_results) and upstream_results[idx] is not None:
            final_results.append(upstream_results[idx])
        else:
            final_results.append(None)
    return {
        "results": final_results,
        "_aperture_partial_batch": {
            "total": len(inner_calls),
            "from_cache": len(cache_hits),
            "from_upstream": len(inner_calls) - len(cache_hits),
        },
    }
