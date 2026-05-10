"""Integrated Aperture tool result pipeline."""

from __future__ import annotations

from typing import Awaitable, Callable

from aperture.cache.interceptor import maybe_execute_with_cache
from aperture.cache.redis_store import CacheStore
from aperture.compression.compressor import compress_tool_output
from aperture.config import ApertureConfig
from aperture.types import CachedResult, CompressionContext, ExecutionContext

ExecuteFn = Callable[[], object | Awaitable[object]]


async def aperture_tool_result_pipeline(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    execute_fn: ExecuteFn,
    *,
    cache_store: CacheStore | None = None,
) -> object:
    """Run cache, compression, and token attribution around a tool call."""

    raw_result = await maybe_execute_with_cache(
        tool_slug=tool_slug,
        params=params,
        context=context,
        execute_fn=execute_fn,
        store=cache_store,
    )
    if isinstance(raw_result, CachedResult):
        raw_result = raw_result.data
    if context.compression_bypass:
        return raw_result
    compression_mode = ApertureConfig.from_env().mode
    compression_context = CompressionContext(
        project_id=context.project_id,
        user_id=context.user_id,
        session_id=context.session_id,
        connected_account_id=context.connected_account_id,
        toolkit_slug=context.toolkit_slug,
        tool_slug=tool_slug,
        user_goal=None,
        model=context.model,
        mode=compression_mode,
    )
    return compress_tool_output(raw_result, compression_context).compressed_payload
