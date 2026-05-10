"""Aggregation helpers for Aperture events.

The simple per-tool aggregators below stay for the salvage report code.
The v1 API endpoints (`/api/v3.1/project/usage/...`) need richer
aggregation: group_by + date-range filtering + ordering + pagination.
That lives in `aggregate_token_events_v1` and `aggregate_cache_events_v1`
at the bottom of this file.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

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


# ----- v1 API-shape aggregators (handoff §17.2) ----------------------------

_TOKEN_GROUP_FIELDS = {
    "meta_tool_slug",
    "toolkit_slug",
    "session_turn",
    "user_id",
    "tool_slug",
    "model",
    "date",
}

_CACHE_GROUP_FIELDS = {
    "tool_slug",
    "toolkit_slug",
    "user_id",
    "cache_status",
    "date",
}


def _group_value(event_dict: dict[str, Any], group_by: str) -> Any:
    if group_by == "date":
        ts = event_dict.get("timestamp", "")
        return ts.split("T", 1)[0] if isinstance(ts, str) else None
    return event_dict.get(group_by)


def _within_window(timestamp: str | None, dt_gt: str | None, dt_lt: str | None) -> bool:
    if not isinstance(timestamp, str):
        return False
    if dt_gt and timestamp < dt_gt:
        return False
    if dt_lt and timestamp > dt_lt:
        return False
    return True


def aggregate_token_events_v1(
    rows: Iterable[dict[str, Any]],
    *,
    group_by: str,
    dt_gt: str | None = None,
    dt_lt: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    order_by: str = "total_quantity",
    order_direction: str = "desc",
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Aggregate token-event rows into the v3.1 API response shape.

    Each row is a dict (the SQLite row format or a TokenAttributionEvent dict).
    Returns:
        {
          "data": [
              {"group_value": ..., "total_input_tokens_contributed": ...,
               "total_calls": ..., "average_per_call": ...},
              ...
          ],
          "page": int,
          "page_size": int,
          "total_groups": int,
        }
    """
    if group_by not in _TOKEN_GROUP_FIELDS:
        raise ValueError(f"Unsupported group_by '{group_by}'. Allowed: {sorted(_TOKEN_GROUP_FIELDS)}")
    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be >= 1")

    buckets: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"total_input_tokens_contributed": 0, "total_calls": 0}
    )

    for row in rows:
        if user_id is not None and row.get("user_id") != user_id:
            continue
        if session_id is not None and row.get("session_id") != session_id:
            continue
        if not _within_window(row.get("timestamp"), dt_gt, dt_lt):
            continue
        key = _group_value(row, group_by)
        bucket = buckets[key]
        bucket["total_input_tokens_contributed"] += int(row.get("input_tokens_contributed") or 0)
        bucket["total_calls"] += 1

    items = []
    for key, bucket in buckets.items():
        total = bucket["total_input_tokens_contributed"]
        calls = bucket["total_calls"]
        items.append({
            "group_value": key,
            "total_input_tokens_contributed": total,
            "total_calls": calls,
            "average_per_call": round(total / calls, 2) if calls else 0,
        })

    if order_by == "total_quantity":
        items.sort(key=lambda x: x["total_input_tokens_contributed"], reverse=(order_direction == "desc"))
    elif order_by == "name":
        items.sort(key=lambda x: str(x["group_value"] or ""), reverse=(order_direction == "desc"))

    total_groups = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": items[start:end],
        "page": page,
        "page_size": page_size,
        "total_groups": total_groups,
    }


def aggregate_cache_events_v1(
    rows: Iterable[dict[str, Any]],
    *,
    group_by: str,
    dt_gt: str | None = None,
    dt_lt: str | None = None,
    user_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Aggregate cache events into v3.1 `cache_tokens_saved` response shape."""
    if group_by not in _CACHE_GROUP_FIELDS:
        raise ValueError(f"Unsupported group_by '{group_by}'. Allowed: {sorted(_CACHE_GROUP_FIELDS)}")
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be >= 1")

    buckets: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"hits": 0, "misses": 0, "tokens_saved": 0, "api_calls_avoided": 0}
    )

    for row in rows:
        if user_id is not None and row.get("user_id") != user_id:
            continue
        if not _within_window(row.get("timestamp"), dt_gt, dt_lt):
            continue
        key = _group_value(row, group_by)
        bucket = buckets[key]
        status = row.get("cache_status")
        if status == "hit":
            bucket["hits"] += 1
        elif status == "miss":
            bucket["misses"] += 1
        if int(row.get("api_call_avoided") or 0):
            bucket["api_calls_avoided"] += 1
        bucket["tokens_saved"] += int(row.get("tokens_saved_estimate") or 0)

    items = [
        {
            "group_value": key,
            "hits": bucket["hits"],
            "misses": bucket["misses"],
            "api_calls_avoided": bucket["api_calls_avoided"],
            "tokens_saved": bucket["tokens_saved"],
        }
        for key, bucket in buckets.items()
    ]
    items.sort(key=lambda x: x["tokens_saved"], reverse=True)

    total_groups = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": items[start:end],
        "page": page,
        "page_size": page_size,
        "total_groups": total_groups,
    }

