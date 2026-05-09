"""Scoped cache key construction."""

from __future__ import annotations

import hashlib

from aperture.cache.normalizer import normalize_params
from aperture.tokenization.serializers import stable_serialize_payload
from aperture.types import CachePolicy, ExecutionContext


def _scope_id(context: ExecutionContext, scope: str) -> str | None:
    if scope == "public":
        return "none"
    if scope == "project":
        return context.project_id
    if scope == "user":
        return context.user_id
    if scope == "account":
        return context.connected_account_id
    if scope == "session":
        return context.session_id
    return None


def build_cache_key(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    policy: CachePolicy,
) -> str | None:
    """Build scoped exact-match cache key or return None if unsafe."""

    if not policy.cacheable or policy.operation_type != "read" or policy.matching != "exact":
        return None
    if policy.privacy_scope == "public" and context.connected_account_id:
        return None
    scope_id = _scope_id(context, policy.privacy_scope)
    if scope_id is None:
        return None
    normalized = normalize_params(tool_slug, params)
    digest = hashlib.sha256(stable_serialize_payload(normalized).encode("utf-8")).hexdigest()
    return f"aperture:v1:{policy.privacy_scope}:{scope_id}:{tool_slug}:{digest}"


def cache_key_hash(cache_key: str | None) -> str | None:
    """Return a log-safe hash of a cache key."""

    if cache_key is None:
        return None
    return hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]

