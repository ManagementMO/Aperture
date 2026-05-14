"""TokenAttributionEvent + CacheEvent builders for the proxy.

Plan-Agent 1 §1: handlers don't repeat the dataclass plumbing — the
attribution layer accepts measured token counts + execution context and
produces the canonical event shapes that the SQLite event log + the
v3.1 API endpoints both consume.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aperture import __version__
from aperture.observability.event_emitter import emit_token_event
from aperture.types import ExecutionContext, TokenAttributionEvent, TokenCount


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA_META_TOOLS = frozenset({
    "COMPOSIO_SEARCH_TOOLS",
    "COMPOSIO_GET_TOOL_SCHEMAS",
})


def _meta_tool_payload_kind(meta_tool_slug: str | None) -> str:
    """Classify what kind of payload the LLM received from a meta-tool call."""

    if meta_tool_slug in _SCHEMA_META_TOOLS:
        return "schema"
    return "execution_result"


def build_meta_tool_response_event(
    *,
    context: ExecutionContext,
    raw_count: TokenCount,
    compressed_count: TokenCount | None = None,
    cache_status: str | None = None,
    session_turn: int | None = None,
) -> TokenAttributionEvent:
    """Build the canonical token attribution event for one meta-tool response.

    ``compressed_count`` is None when no compression was applied. When the
    schema overlay rewrites a description, the rewritten payload's count
    is passed as ``compressed_count`` so the event reflects the savings.
    """
    final_count = compressed_count or raw_count
    raw_tokens = raw_count.tokens
    compressed_tokens = final_count.tokens
    tokens_saved = max(0, raw_tokens - compressed_tokens)
    ratio = (compressed_tokens / raw_tokens) if raw_tokens else 1.0

    return TokenAttributionEvent(
        event_type="meta_tool_response",
        timestamp=_now_iso(),
        project_id=context.project_id,
        user_id=context.user_id,
        session_id=context.session_id,
        connected_account_id=context.connected_account_id,
        toolkit_slug=context.toolkit_slug,
        tool_slug=context.tool_slug,
        meta_tool_slug=context.meta_tool_slug,
        payload_kind=_meta_tool_payload_kind(context.meta_tool_slug),
        model=context.model,
        tokenizer=final_count.tokenizer,
        tokenizer_is_approximate=(
            raw_count.tokenizer_is_approximate or final_count.tokenizer_is_approximate
        ),
        raw_payload_bytes=raw_count.payload_bytes,
        compressed_payload_bytes=final_count.payload_bytes,
        raw_tokens=raw_tokens,
        compressed_tokens=compressed_tokens,
        input_tokens_contributed=compressed_tokens,
        tokens_saved=tokens_saved,
        compression_ratio=round(ratio, 6),
        cache_status=cache_status,
        aperture_version=__version__,
        session_turn=session_turn,
    )


def emit_meta_tool_event(
    *,
    context: ExecutionContext,
    raw_count: TokenCount,
    compressed_count: TokenCount | None = None,
    cache_status: str | None = None,
    session_turn: int | None = None,
) -> TokenAttributionEvent:
    """Build + emit. Convenience for handlers."""
    event = build_meta_tool_response_event(
        context=context,
        raw_count=raw_count,
        compressed_count=compressed_count,
        cache_status=cache_status,
        session_turn=session_turn,
    )
    emit_token_event(event)
    return event


def build_cache_hit_savings_event(
    *,
    context: ExecutionContext,
    cached_payload_count: TokenCount,
    session_turn: int | None = None,
) -> TokenAttributionEvent:
    """When a cache hit avoids an upstream call, we still emit a token
    attribution event so the v3.1 API can report savings (the LLM saw the
    same content, just from cache). `tokens_saved` here represents the
    upstream call's would-have-been cost — not perfectly accurate without
    the original cost token count, but a useful signal.
    """
    return TokenAttributionEvent(
        event_type="cache_hit_savings",
        timestamp=_now_iso(),
        project_id=context.project_id,
        user_id=context.user_id,
        session_id=context.session_id,
        connected_account_id=context.connected_account_id,
        toolkit_slug=context.toolkit_slug,
        tool_slug=context.tool_slug,
        meta_tool_slug=context.meta_tool_slug,
        payload_kind="execution_result",
        model=context.model,
        tokenizer=cached_payload_count.tokenizer,
        tokenizer_is_approximate=cached_payload_count.tokenizer_is_approximate,
        raw_payload_bytes=cached_payload_count.payload_bytes,
        compressed_payload_bytes=cached_payload_count.payload_bytes,
        raw_tokens=cached_payload_count.tokens,
        compressed_tokens=cached_payload_count.tokens,
        input_tokens_contributed=cached_payload_count.tokens,
        tokens_saved=cached_payload_count.tokens,
        compression_ratio=1.0,
        cache_status="hit",
        aperture_version=__version__,
        session_turn=session_turn,
    )


def attribute_to_dict(event: TokenAttributionEvent) -> dict[str, Any]:
    """Tolerant dict conversion for HTTP responses + SQLite serialization."""
    from dataclasses import asdict

    return asdict(event)
