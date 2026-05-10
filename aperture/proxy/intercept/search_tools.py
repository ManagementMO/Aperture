"""Handler for `COMPOSIO_SEARCH_TOOLS`.

Cache the schema+plan portion (public, shareable across users); always
fetch the connection_status portion fresh and merge before returning.
Per Plan-Agent 1 §3 + handoff §13.1 cell 11 + aperture/cache/search_tools_cache.py.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aperture.cache.search_tools_cache import (
    has_schema_or_plan,
    merge_response,
    split_response,
)
from aperture.proxy.cache_bridge import cached_or_forward, unwrap_cached_result
from aperture.proxy.errors import safe
from aperture.types import ExecutionContext


@safe(fallback_value=None)
async def _maybe_get_cached_search(
    *,
    arguments: dict[str, Any],
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
) -> Any:
    """Return the cached or freshly-forwarded raw response, or None on cache failure."""
    return await cached_or_forward(
        tool_slug="COMPOSIO_SEARCH_TOOLS",
        params=arguments,
        context=context,
        upstream_call=upstream_call,
    )


async def handle_search_tools(
    arguments: dict[str, Any],
    *,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    fetch_connection_status: Callable[[], Awaitable[Any]] | None = None,
) -> Any:
    """Run the SEARCH_TOOLS pipeline: cache → overlay → tokenize.

    Args:
        arguments: the inbound `tools/call` arguments dict.
        context: ExecutionContext built by the router.
        upstream_call: async no-arg callable that performs the actual MCP forward.
        fetch_connection_status: optional async no-arg that re-fetches per-user
            auth state. When provided, it overlays into the cached portion.

    Returns the merged response payload. Falls back to a direct upstream call
    if the cache layer raises.
    """
    cached_or_fresh = await _maybe_get_cached_search(
        arguments=arguments,
        context=context,
        upstream_call=upstream_call,
    )

    if cached_or_fresh is None:
        # Cache layer itself failed — fall back to a direct forward.
        cached_or_fresh = await upstream_call()
    cached_or_fresh = unwrap_cached_result(cached_or_fresh)

    # If the response carries a schema/plan portion, optionally enrich with
    # fresh connection_status. Otherwise just pass through.
    if not has_schema_or_plan(cached_or_fresh) or fetch_connection_status is None:
        return cached_or_fresh

    cacheable, _stale_status = split_response(cached_or_fresh)
    fresh_status = await fetch_connection_status()
    fresh_dict = fresh_status if isinstance(fresh_status, dict) else {}
    return merge_response(cacheable, fresh_dict)
