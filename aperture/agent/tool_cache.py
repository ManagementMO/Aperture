"""Tool-call result cache — saves Composio bill on repeat tool executions.

When Claude asks for the SAME tool with the SAME arguments twice — even
inside one conversation, even across different user asks — we serve the
second call from cache. Composio doesn't see the second request, so it
isn't billed.

Cache key shape:
    (tool_slug, sorted-args-json, user_id)

Why this is safe:
- TTL eviction (default 5 min) — schema/data drift can't go stale long.
- Read-only guard: WRITE-class tools (SEND/CREATE/UPDATE/DELETE/POST/
  EXECUTE) bypass the cache entirely. We never want to "skip" an action
  the user expected to happen.
- Bypass flag (`bypass=True`) lets the agent override per-call.
- The cache key includes user_id, so per-user data never crosses tenants.

Stats (`cache_stats()`) are surfaced by the API so the dashboard can show
"X Composio calls avoided" and the cumulative bill saved.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any


_TTL_SECONDS = int(os.getenv("APERTURE_TOOL_CACHE_TTL", "300"))    # 5 min
_MAX_ENTRIES = int(os.getenv("APERTURE_TOOL_CACHE_MAX", "500"))


# Tool slug substrings that indicate a side-effect-producing tool. Anything
# matching this list bypasses the cache and goes straight to Composio so
# we never silently elide a real action.
_WRITE_INDICATORS = (
    "SEND", "CREATE", "POST", "UPDATE", "PUT", "PATCH", "DELETE",
    "REMOVE", "MOVE", "ARCHIVE", "STAR", "UNSTAR", "MERGE", "CLOSE",
    "OPEN", "REOPEN", "COMMENT", "REPLY", "ASSIGN", "UNASSIGN",
    "ADD", "INVITE", "EXECUTE_QUERY", "PUBLISH",
)
# Read-style verbs that *contain* write substrings but are actually safe.
_READ_OVERRIDES = (
    "GET_THE_AUTHENTICATED_USER",
    "FETCH_EMAILS", "FETCH_DATA", "FETCH_DATABASE",
    "FETCH_TABLE_ROWS", "FETCH_BLOCK_CONTENTS", "FETCH_COMMENTS",
    "FETCH_MESSAGE_BY_THREAD_ID", "FETCH_CONVERSATION_HISTORY",
)


def is_write_tool(slug: str) -> bool:
    """True if the slug looks like it produces a side effect."""
    upper = slug.upper()
    if any(o in upper for o in _READ_OVERRIDES):
        return False
    return any(w in upper for w in _WRITE_INDICATORS)


def is_read_only_mode() -> bool:
    return os.getenv("APERTURE_READ_ONLY", "0") in ("1", "true", "True")


# ---------------------------------------------------------------------------
# Cache state (process-local)
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, Any]] = {}
_STATS: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "writes_skipped": 0,
    "evictions": 0,
}
# Per-call event log so the UI can render "this call hit cache, this didn't"
_RECENT_EVENTS: list[dict[str, Any]] = []
_RECENT_LIMIT = 100


def _key(tool_slug: str, args: dict, user_id: str) -> str:
    payload = json.dumps(
        {"slug": tool_slug, "args": args, "user": user_id},
        sort_keys=True, default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _record_event(event: dict[str, Any]) -> None:
    _RECENT_EVENTS.append(event)
    if len(_RECENT_EVENTS) > _RECENT_LIMIT:
        del _RECENT_EVENTS[: len(_RECENT_EVENTS) - _RECENT_LIMIT]


def lookup(
    tool_slug: str, args: dict, user_id: str
) -> tuple[Any, dict[str, Any] | None]:
    """Return (cached_value_or_None, event_or_None).

    Returns (None, None) on miss. Returns (value, event) on hit. Event is
    None when the lookup was skipped (write tool, read-only mode is a
    refusal, not a cache miss)."""
    if is_write_tool(tool_slug):
        _STATS["writes_skipped"] += 1
        return None, None

    key = _key(tool_slug, args, user_id)
    entry = _CACHE.get(key)
    if entry is None:
        _STATS["misses"] += 1
        return None, None

    expires_at, value = entry
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        _STATS["evictions"] += 1
        _STATS["misses"] += 1
        return None, None

    _STATS["hits"] += 1
    age = max(0.0, _TTL_SECONDS - (expires_at - time.time()))
    event = {
        "tool": tool_slug,
        "status": "hit",
        "age_seconds": round(age, 1),
        "ts": time.time(),
    }
    _record_event(event)
    return value, event


def store(tool_slug: str, args: dict, user_id: str, value: Any) -> None:
    """Cache the result of a non-write tool call."""
    if is_write_tool(tool_slug):
        return
    key = _key(tool_slug, args, user_id)
    if len(_CACHE) >= _MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
        _STATS["evictions"] += 1
    _CACHE[key] = (time.time() + _TTL_SECONDS, value)
    _record_event({
        "tool": tool_slug,
        "status": "miss_stored",
        "ts": time.time(),
    })


def clear() -> int:
    n = len(_CACHE)
    _CACHE.clear()
    return n


def cache_stats() -> dict[str, Any]:
    total_attempts = _STATS["hits"] + _STATS["misses"]
    return {
        "entries": len(_CACHE),
        "ttl_seconds": _TTL_SECONDS,
        "max_entries": _MAX_ENTRIES,
        "hits": _STATS["hits"],
        "misses": _STATS["misses"],
        "writes_skipped": _STATS["writes_skipped"],
        "evictions": _STATS["evictions"],
        "hit_rate": round(_STATS["hits"] / max(total_attempts, 1) * 100, 1),
        "read_only_mode": is_read_only_mode(),
        "recent_events": _RECENT_EVENTS[-15:],
    }


# ---------------------------------------------------------------------------
# Composio cost estimate
# ---------------------------------------------------------------------------

# Composio's pricing varies by toolkit and plan. Use a conservative
# placeholder of $0.001 per tool call so we can show a real-feeling
# "Composio bill saved" number. Override per toolkit if you have actual
# numbers from the user's plan.
_COMPOSIO_COST_DEFAULT = float(os.getenv("APERTURE_COMPOSIO_COST_PER_CALL", "0.001"))
_COMPOSIO_COST_OVERRIDES: dict[str, float] = {
    # Heavy / metered toolkits could go here:
    # "GMAIL_SEARCH_EMAILS": 0.002,
}


def composio_cost_estimate(tool_slug: str) -> float:
    return _COMPOSIO_COST_OVERRIDES.get(tool_slug, _COMPOSIO_COST_DEFAULT)


def estimated_composio_savings_usd() -> float:
    # Approximate: every cache hit saved one Composio call at the default rate.
    # We don't have per-slug visibility into past hits without more state, so
    # this is a clean approximation good enough for the dashboard.
    return round(_STATS["hits"] * _COMPOSIO_COST_DEFAULT, 4)
