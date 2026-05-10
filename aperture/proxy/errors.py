"""Fallback decorators for non-load-bearing proxy enrichment layers.

Hard rule (Plan-Agent 1 §8): the proxy MUST always forward to Composio
successfully when its enrichment layers fail. Cache, tokenize, and overlay
all fail open — they log a warning and the proxy continues with the raw
upstream call.

The ONE exception: if `upstream.forward` itself raises, that's a real error
and propagates to the MCP client.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def safe(fallback_value: T, *, log_level: int = logging.WARNING) -> Callable[
    [Callable[..., Awaitable[T]]],
    Callable[..., Awaitable[T]],
]:
    """Decorator: any exception inside the wrapped async fn → log + return fallback.

    Use on cache lookup, tokenize, overlay apply. NEVER on upstream forward
    or anything in the response path that affects correctness.
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                logger.log(
                    log_level,
                    "aperture.proxy.%s failed (returning fallback): %s",
                    fn.__name__,
                    exc,
                )
                return fallback_value

        return wrapper

    return decorator


class ProxyError(Exception):
    """Raised when the proxy itself cannot continue (e.g., upstream unreachable
    AND fallbacks exhausted). Surfaced to the MCP client as a tool error."""
