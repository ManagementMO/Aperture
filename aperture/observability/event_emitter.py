"""Structured event emission for Aperture."""

from __future__ import annotations

import json
from pathlib import Path

from aperture.config import ApertureConfig
from aperture.observability.event_schema import (
    event_to_dict,
    validate_cache_event,
    validate_token_event,
)
from aperture.types import CacheEvent, TokenAttributionEvent

_TOKEN_EVENTS: list[TokenAttributionEvent] = []
_CACHE_EVENTS: list[CacheEvent] = []


def clear_in_memory_events() -> None:
    """Clear in-memory events for tests and isolated benchmark runs."""

    _TOKEN_EVENTS.clear()
    _CACHE_EVENTS.clear()


def get_in_memory_token_events() -> list[TokenAttributionEvent]:
    """Return token attribution events captured in memory."""

    return list(_TOKEN_EVENTS)


def get_in_memory_cache_events() -> list[CacheEvent]:
    """Return cache events captured in memory."""

    return list(_CACHE_EVENTS)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def emit_token_event(event: TokenAttributionEvent, sink_path: Path | None = None) -> None:
    """Emit a token attribution event to memory and optionally JSONL."""

    validate_token_event(event)
    _TOKEN_EVENTS.append(event)
    if sink_path is None:
        sink_path = ApertureConfig.from_env().event_sink_path
    if sink_path:
        _append_jsonl(sink_path, {"kind": "token", **event_to_dict(event)})


def emit_cache_event(event: CacheEvent, sink_path: Path | None = None) -> None:
    """Emit a cache event to memory and optionally JSONL."""

    validate_cache_event(event)
    _CACHE_EVENTS.append(event)
    if sink_path is None:
        sink_path = ApertureConfig.from_env().event_sink_path
    if sink_path:
        _append_jsonl(sink_path, {"kind": "cache", **event_to_dict(event)})

