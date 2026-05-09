"""Deterministic cache key builder with scoping."""

import hashlib

from aperture.tokenization.serializers import stable_json_dumps


def cache_key_hash(cache_key: str | None) -> str | None:
    """Return a log-safe hash of a cache key."""
    if cache_key is None:
        return None
    return hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]


def build_cache_key(
    tool_slug: str,
    arguments: dict,
    user_id: str | None = None,
    tenant_id: str | None = None,
    connected_account_id: str | None = None,
    cache_scope: str = "public",
) -> str | None:
    """Build a scoped, deterministic cache key.

    Format: aperture:cache:{scope}:{tool_slug}:{args_hash}

    Returns None when the required scope identifier is missing. This keeps
    private connected-account data from falling back to a global cache.
    """
    # Normalize and hash arguments
    args_str = stable_json_dumps(arguments)
    args_hash = hashlib.sha256(args_str.encode("utf-8")).hexdigest()[:16]

    # Determine scope
    if cache_scope == "public":
        # If the caller has a connected account, the result may be
        # personalized even for a nominally public tool. Avoid public reuse.
        if connected_account_id:
            return None
        scope = "public"
    elif cache_scope == "account":
        if not connected_account_id:
            return None
        scope = f"ca:{connected_account_id}"
    elif cache_scope == "user":
        if not user_id:
            return None
        scope = f"u:{user_id}"
    elif cache_scope == "tenant":
        if not tenant_id:
            return None
        scope = f"t:{tenant_id}"
    else:
        return None

    return f"aperture:cache:{scope}:{tool_slug}:{args_hash}"
