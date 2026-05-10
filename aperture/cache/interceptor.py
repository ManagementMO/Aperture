"""Cache interceptor around tool execution."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Awaitable, Callable

from aperture.cache.key_builder import build_cache_key, cache_key_hash
from aperture.cache.policy import load_cache_policy
from aperture.cache.redis_store import CacheStore, InMemoryCacheStore
from aperture.observability.event_emitter import emit_cache_event
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import CacheEvent, ExecutionContext

ExecuteFn = Callable[[], object | Awaitable[object]]


def _event(
    *,
    context: ExecutionContext,
    tool_slug: str,
    cache_status: str,
    cache_scope: str,
    key: str | None,
    ttl_seconds: int | None,
    cached_age_seconds: int | None,
    api_call_avoided: bool,
    tokens_saved_estimate: int,
    reason: str | None,
) -> CacheEvent:
    return CacheEvent(
        event_type="cache_lookup",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=context.project_id,
        user_id=context.user_id,
        session_id=context.session_id,
        connected_account_id=context.connected_account_id,
        tool_slug=tool_slug,
        toolkit_slug=context.toolkit_slug,
        cache_status=cache_status,
        cache_scope=cache_scope,
        cache_key_hash=cache_key_hash(key),
        ttl_seconds=ttl_seconds,
        cached_age_seconds=cached_age_seconds,
        api_call_avoided=api_call_avoided,
        tokens_saved_estimate=tokens_saved_estimate,
        reason=reason,
    )


async def _execute(execute_fn: ExecuteFn) -> object:
    result = execute_fn()
    if inspect.isawaitable(result):
        return await result
    return result


def _success_response(response: object) -> bool:
    if isinstance(response, dict):
        if response.get("success") is False:
            return False
        if "error" in response and response["error"]:
            return False
    return True


async def maybe_execute_with_cache(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    execute_fn: ExecuteFn,
    store: CacheStore | None = None,
) -> object:
    """Return cached response on hit, otherwise execute and store if safe."""

    selected_store = store or InMemoryCacheStore()
    policy = load_cache_policy(tool_slug)

    if context.cache_bypass:
        response = await _execute(execute_fn)
        emit_cache_event(
            _event(
                context=context,
                tool_slug=tool_slug,
                cache_status="bypass",
                cache_scope=policy.privacy_scope,
                key=None,
                ttl_seconds=policy.ttl_seconds,
                cached_age_seconds=None,
                api_call_avoided=False,
                tokens_saved_estimate=0,
                reason="context_cache_bypass",
            )
        )
        return response

    key = build_cache_key(tool_slug, params, context, policy)
    if key is None:
        response = await _execute(execute_fn)
        emit_cache_event(
            _event(
                context=context,
                tool_slug=tool_slug,
                cache_status="not_cacheable",
                cache_scope=policy.privacy_scope,
                key=None,
                ttl_seconds=policy.ttl_seconds,
                cached_age_seconds=None,
                api_call_avoided=False,
                tokens_saved_estimate=0,
                reason=policy.reason or "unsafe_or_missing_scope",
            )
        )
        return response

    cached = selected_store.get(key)
    if cached is not None:
        emit_cache_event(
            _event(
                context=context,
                tool_slug=tool_slug,
                cache_status="hit",
                cache_scope=policy.privacy_scope,
                key=key,
                ttl_seconds=policy.ttl_seconds,
                cached_age_seconds=selected_store.age_seconds(key),
                api_call_avoided=True,
                tokens_saved_estimate=count_tokens_for_payload(cached, context.model).tokens,
                reason=None,
            )
        )
        return cached

    response = await _execute(execute_fn)
    if _success_response(response) and policy.ttl_seconds is not None:
        selected_store.set(key, response, policy.ttl_seconds)
    emit_cache_event(
        _event(
            context=context,
            tool_slug=tool_slug,
            cache_status="miss",
            cache_scope=policy.privacy_scope,
            key=key,
            ttl_seconds=policy.ttl_seconds,
            cached_age_seconds=None,
            api_call_avoided=False,
            tokens_saved_estimate=0,
            reason=None if _success_response(response) else "failed_response_not_cached",
        )
    )
    return response

