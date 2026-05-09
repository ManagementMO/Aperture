"""Cache interceptor that wraps tool execution."""

from typing import Any, Callable

from aperture.cache.key_builder import build_cache_key, cache_key_hash
from aperture.cache.policy import get_cache_scope, get_cache_ttl, is_cacheable
from aperture.cache.store import CacheStore
from aperture.contracts import ApertureRunConfig, CacheEvent
from aperture.tokenization import count_tokens


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
        cacheable = is_cacheable(tool_slug)
        cache_scope = get_cache_scope(tool_slug) if cacheable else "none"

        # Check if caching is enabled and tool is cacheable
        if config.cache_bypass or not cacheable:
            result = executor()
            event = CacheEvent(
                run_id=config.run_id,
                toolkit_slug=None,
                tool_slug=tool_slug,
                cache_status="not_cacheable" if not cacheable else "bypass",
                cache_scope=cache_scope,
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
            cache_scope=cache_scope,
        )
        if cache_key is None:
            result = executor()
            event = CacheEvent(
                run_id=config.run_id,
                toolkit_slug=None,
                tool_slug=tool_slug,
                cache_status="not_cacheable",
                cache_scope=cache_scope,
                reason="missing_required_cache_scope",
            )
            return result, event

        # Try cache hit
        cached = self.store.get(cache_key)
        if cached is not None:
            event = CacheEvent(
                run_id=config.run_id,
                toolkit_slug=None,
                tool_slug=tool_slug,
                cache_status="hit",
                cache_scope=cache_scope,
                cache_key_hash=cache_key_hash(cache_key),
                api_call_avoided=True,
                tokens_saved_estimate=count_tokens(cached, config.model).tokens,
            )
            return cached, event

        # Cache miss — execute
        result = executor()

        # Store successful responses in cache.
        ttl = get_cache_ttl(tool_slug)
        if _success_response(result):
            self.store.set(cache_key, result, ttl)

        event = CacheEvent(
            run_id=config.run_id,
            toolkit_slug=None,
            tool_slug=tool_slug,
            cache_status="miss",
            cache_scope=cache_scope,
            cache_key_hash=cache_key_hash(cache_key),
            api_call_avoided=False,
            reason=None if _success_response(result) else "failed_response_not_cached",
        )
        return result, event

    def update_cached_tokens(self, cache_key_hash: str, tokens: int) -> None:
        """Update token estimate on a cached entry after compression."""
        # This is a no-op for now; in production we'd update the cache entry
        pass


def _success_response(response: object) -> bool:
    """Return whether a response is safe to store."""
    if isinstance(response, dict):
        if response.get("success") is False:
            return False
        if response.get("error"):
            return False
    return True
