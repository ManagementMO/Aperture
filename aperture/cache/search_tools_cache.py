"""COMPOSIO_SEARCH_TOOLS response split-and-merge logic.

A SEARCH_TOOLS response contains three logical portions (handoff §13.1 cell 11):
    1. Tool schemas — public, shareable across users.
    2. Execution plans — public, shareable across users.
    3. Connection status — per-user, NOT shareable.

The cache key for the schema+plan portion uses scope=public + the search query
hash; the connection_status portion is fetched fresh on every call and merged
into the response before it's returned to the LLM.

This module exposes:
    - split_response(): tear apart the upstream response into (cacheable, fresh).
    - merge_response(): glue them back together for the LLM.
    - search_query_key(): deterministic key for the search-query portion.
"""

from __future__ import annotations

import hashlib
from typing import Any

from aperture.tokenization.serializers import stable_serialize_payload


def search_query_key(query: str, model: str | None = None) -> str:
    """Deterministic key for caching SEARCH_TOOLS responses by query string.

    Format: aperture:v1:p1:public:none:COMPOSIO_SEARCH_TOOLS:{sha256_hex}

    Includes `model` because Composio's SEARCH_TOOLS accepts a `model` param
    that tunes plan ranking. Different models legitimately deserve different
    cached plans.
    """
    payload = {"query": (query or "").strip().lower(), "model": model}
    digest = hashlib.sha256(stable_serialize_payload(payload).encode("utf-8")).hexdigest()
    return f"aperture:v1:p1:public:none:COMPOSIO_SEARCH_TOOLS:{digest}"


# Field names we expect Composio to use for the three portions. Composio's
# wire schema can evolve; these are documented assumptions, not the actual
# response shape from a live call. The functions tolerate missing fields.
_SCHEMA_FIELDS = ("tools", "schemas", "matched_tools")
_PLAN_FIELDS = ("plans", "execution_plans", "learned_plans")
_CONNECTION_STATUS_FIELDS = ("connection_status", "connections", "auth_status")


def split_response(response: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (cacheable_portion, fresh_portion).

    The cacheable portion contains anything not in `_CONNECTION_STATUS_FIELDS`.
    The fresh portion contains only those fields. Either may be empty when the
    response shape doesn't carry that data.
    """
    if not isinstance(response, dict):
        return ({"_aperture_raw": response}, {})

    cacheable: dict[str, Any] = {}
    fresh: dict[str, Any] = {}
    for key, value in response.items():
        if key in _CONNECTION_STATUS_FIELDS:
            fresh[key] = value
        else:
            cacheable[key] = value
    return cacheable, fresh


def merge_response(cacheable: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    """Reassemble the response. Fresh data wins on key collision."""
    merged: dict[str, Any] = dict(cacheable) if isinstance(cacheable, dict) else {"_aperture_raw": cacheable}
    if isinstance(fresh, dict):
        merged.update(fresh)
    return merged


def has_schema_or_plan(payload: dict[str, Any]) -> bool:
    """Quick check: does this response actually carry a schema/plan portion
    that's worth caching? Used to skip caching empty / error responses.
    """
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in (*_SCHEMA_FIELDS, *_PLAN_FIELDS))
