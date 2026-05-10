"""Async bridge to the existing sync cache layer.

Plan-Agent 1 §7: the salvage `aperture/cache/interceptor.py:maybe_execute_with_cache`
is *already* `async def` and accepts `Callable[[], Awaitable[object]]`, so the
bridge can be thinner than originally feared. We just import and delegate.

PR 5 may async-rewrite the Redis store under the hood; the bridge's public
shape stays stable.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aperture.cache.interceptor import maybe_execute_with_cache
from aperture.cache.policy import load_cache_policy
from aperture.cache.redis_store import CacheStore, InMemoryCacheStore
from aperture.types import CachedResult, ExecutionContext


_DEFAULT_STORE: CacheStore | None = None


def get_default_store() -> CacheStore:
    """Lazy module-level in-memory store; tests inject their own."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = InMemoryCacheStore()
    return _DEFAULT_STORE


def set_default_store(store: CacheStore) -> None:
    """Override the module-level store. Used by `__main__` to wire Redis when
    APERTURE_REDIS_URL is set, and by tests to inject mocks."""
    global _DEFAULT_STORE
    _DEFAULT_STORE = store


async def cached_or_forward(
    *,
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    store: CacheStore | None = None,
) -> Any:
    """Hit cache if safe; otherwise forward to upstream and cache the success.

    Returns the raw payload (cache hit or upstream response). Cache events
    are emitted by the underlying interceptor — the bridge does not need to
    duplicate that.
    """
    selected_store = store or get_default_store()
    return await maybe_execute_with_cache(
        tool_slug,
        params,
        context,
        upstream_call,
        store=selected_store,
    )


def unwrap_cached_result(value: Any) -> Any:
    """Return the payload the MCP client should see."""

    return value.data if isinstance(value, CachedResult) else value


def policy_summary(tool_slug: str) -> dict[str, Any]:
    """Helper for the proxy's debug/admin endpoints (Phase 7)."""
    policy = load_cache_policy(tool_slug)
    return {
        "tool_slug": policy.tool_slug,
        "cacheable": policy.cacheable,
        "operation_type": policy.operation_type,
        "privacy_scope": policy.privacy_scope,
        "ttl_seconds": policy.ttl_seconds,
        "matching": policy.matching,
        "reason": policy.reason,
    }
