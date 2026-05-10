"""Handler for `COMPOSIO_GET_TOOL_SCHEMAS`.

PR 3: tokenize the response, emit attribution event, return verbatim.
PR 4: apply schema overlay (rewrite descriptions per _overlay.json).
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


async def handle_get_tool_schemas(
    arguments: dict[str, Any],
    *,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    session_turn: int | None = None,
) -> Any:
    """Forward → tokenize → emit. No cache (per Plan-Agent 1 §3 matrix)."""
    response = await upstream_call()

    raw_count = await _measure(response, context.model)
    if raw_count is not None:
        emit_meta_tool_event(
            context=context,
            raw_count=raw_count,
            cache_status=None,
            session_turn=session_turn,
        )

    return response
