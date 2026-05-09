"""Event schema helpers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aperture.types import CacheEvent, TokenAttributionEvent


def event_to_dict(event: TokenAttributionEvent | CacheEvent) -> dict[str, Any]:
    """Convert an Aperture event dataclass into a serializable dictionary."""

    return asdict(event)


def validate_token_event(event: TokenAttributionEvent) -> None:
    """Validate required token attribution event fields."""

    if not event.event_type:
        raise ValueError("Token event requires event_type")
    if not event.payload_kind:
        raise ValueError("Token event requires payload_kind")
    if event.input_tokens_contributed < 0:
        raise ValueError("input_tokens_contributed cannot be negative")


def validate_cache_event(event: CacheEvent) -> None:
    """Validate required cache event fields."""

    if not event.tool_slug:
        raise ValueError("Cache event requires tool_slug")
    if event.cache_status not in {"hit", "miss", "bypass", "not_cacheable", "error", "store"}:
        raise ValueError(f"Invalid cache status: {event.cache_status}")

