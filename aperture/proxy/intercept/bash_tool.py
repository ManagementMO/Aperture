"""Handler for `COMPOSIO_REMOTE_BASH_TOOL`.

Bash output is non-deterministic — not cacheable. Tokenize for visibility.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aperture.proxy.attribution import emit_meta_tool_event
from aperture.proxy.errors import safe
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import ExecutionContext


@safe(fallback_value=None)
async def _measure(payload: Any, model: str | None):
    return count_tokens_for_payload(payload, model)


async def handle_bash_tool(
    arguments: dict[str, Any],
    *,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    session_turn: int | None = None,
) -> Any:
    response = await upstream_call()
    raw_count = await _measure(response, context.model)
    if raw_count is not None:
        emit_meta_tool_event(
            context=context,
            raw_count=raw_count,
            cache_status="not_cacheable",
            session_turn=session_turn,
        )
    return response
