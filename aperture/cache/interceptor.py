"""Cache interceptor that wraps tool execution."""

from typing import Any, Callable

from aperture.cache.key_builder import build_cache_key
from aperture.cache.policy import get_cache_ttl, is_cacheable
from aperture.cache.store import CacheStore
from aperture.contracts import ApertureRunConfig, CacheEvent


class CachedExecutor:
    """Wraps a tool execution function with caching."""

    def __init__(self):
        self.store = CacheStore()

    def execute(
        self,
        tool_slug: str,
        arguments: dict,
        executor: Callable[[], Any],
        config: ApertureRunConfig,
    ) -> tuple[Any, CacheEvent]:
        """Execute a tool with cache checking.

        Returns:
            (result, cache_event)
        """
        # Check if caching is enabled and tool is cacheable
        if config.cache_bypass or not is_cacheable(tool_slug):
            result = executor()
            event = CacheEvent(
                run_id=config.run_id,
                toolkit_slug=None,
                tool_slug=tool_slug,
                cache_status="not_cacheable" if not is_cacheable(tool_slug) else "bypass",
                reason="cache_bypass" if config.cache_bypass else "tool_not_cacheable",
            )
            return result, event

        # Build cache key
        cache_key = build_cache_key(
            tool_slug=tool_slug,
            arguments=arguments,
            user_id=config.user_id,
            tenant_id=config.tenant_id,
            connected_account_id=config.connected_account_id,
        )

        # Try cache hit
        cached = self.store.get(cache_key)
        if cached is not None:
            event = CacheEvent(
                run_id=config.run_id,
                toolkit_slug=None,
                tool_slug=tool_slug,
                cache_status="hit",
                cache_key_hash=cache_key[-16:],  # last 16 chars for logging
                api_call_avoided=True,
                tokens_saved_estimate=cached.get("__aperture_tokens", 0),
            )
            # Return the cached result without the metadata wrapper
            return cached.get("__aperture_result", cached), event

        # Cache miss — execute
        result = executor()

        # Store in cache
        ttl = get_cache_ttl(tool_slug)
        # Wrap result with metadata for token estimate on hit
        wrapped = {
            "__aperture_result": result,
            "__aperture_tokens": 0,  # Will be updated by compression layer
        }
        self.store.set(cache_key, wrapped, ttl)

        event = CacheEvent(
            run_id=config.run_id,
            toolkit_slug=None,
            tool_slug=tool_slug,
            cache_status="miss",
            cache_key_hash=cache_key[-16:],
            api_call_avoided=False,
        )
        return result, event

    def update_cached_tokens(self, cache_key_hash: str, tokens: int) -> None:
        """Update token estimate on a cached entry after compression."""
        # This is a no-op for now; in production we'd update the cache entry
        pass
