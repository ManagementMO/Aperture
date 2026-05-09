"""Aggregation helpers for Aperture events."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from aperture.types import CacheEvent, SchemaOptimizationResult, TokenAttributionEvent


def aggregate_tokens_by_tool(events: Iterable[TokenAttributionEvent]) -> dict[str, int]:
    """Aggregate input tokens by tool slug."""

    totals: dict[str, int] = defaultdict(int)
    for event in events:
        totals[event.tool_slug or event.meta_tool_slug or "unknown"] += event.input_tokens_contributed
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def aggregate_compression_savings(events: Iterable[TokenAttributionEvent]) -> dict[str, int]:
    """Aggregate compression token savings by tool slug."""

    totals: dict[str, int] = defaultdict(int)
    for event in events:
        if event.event_type == "tool_output_compression":
            totals[event.tool_slug or "unknown"] += event.tokens_saved
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def aggregate_cache_savings(events: Iterable[CacheEvent]) -> dict[str, dict[str, int]]:
    """Aggregate cache hits and estimated savings by tool slug."""

    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"hits": 0, "api_calls_avoided": 0, "tokens_saved": 0})
    for event in events:
        bucket = totals[event.tool_slug]
        if event.cache_status == "hit":
            bucket["hits"] += 1
        if event.api_call_avoided:
            bucket["api_calls_avoided"] += 1
        bucket["tokens_saved"] += event.tokens_saved_estimate
    return dict(totals)


def aggregate_schema_savings(results: Iterable[SchemaOptimizationResult]) -> dict[str, int]:
    """Aggregate accepted schema token savings by tool slug."""

    totals: dict[str, int] = defaultdict(int)
    for result in results:
        if result.accepted:
            totals[result.tool_slug] += result.reduction_tokens
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))

