"""Deterministic cache key builder with scoping."""

import hashlib

from aperture.tokenization.serializers import stable_json_dumps


def build_cache_key(
    tool_slug: str,
    arguments: dict,
    user_id: str | None = None,
    tenant_id: str | None = None,
    connected_account_id: str | None = None,
) -> str:
    """Build a scoped, deterministic cache key.

    Format: aperture:cache:{scope}:{tool_slug}:{args_hash}
    """
    # Normalize and hash arguments
    args_str = stable_json_dumps(arguments)
    args_hash = hashlib.sha256(args_str.encode("utf-8")).hexdigest()[:16]

    # Determine scope
    scope_parts = []
    if tenant_id:
        scope_parts.append(f"t:{tenant_id}")
    if user_id:
        scope_parts.append(f"u:{user_id}")
    if connected_account_id:
        scope_parts.append(f"ca:{connected_account_id}")

    scope = "|".join(scope_parts) if scope_parts else "global"

    return f"aperture:cache:{scope}:{tool_slug}:{args_hash}"
