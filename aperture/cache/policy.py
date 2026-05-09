"""Cache policy loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aperture.types import CachePolicy


def _policy_path() -> Path:
    return Path(__file__).with_name("policy.yaml")


def _load_policy_file(path: Path | None = None) -> dict[str, Any]:
    selected = path or _policy_path()
    with selected.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if data.get("version") != 1:
        raise ValueError("Cache policy file must have version: 1")
    return data


def _build_policy(tool_slug: str, data: dict[str, Any]) -> CachePolicy:
    return CachePolicy(
        tool_slug=tool_slug,
        cacheable=bool(data.get("cacheable", False)),
        operation_type=str(data.get("operation_type", "unknown")),
        privacy_scope=str(data.get("privacy_scope", "none")),
        ttl_seconds=data.get("ttl_seconds"),
        matching=str(data.get("matching", "none")),
        reason=data.get("reason"),
    )


def load_cache_policy(tool_slug: str, path: Path | None = None) -> CachePolicy:
    """Return cache policy, defaulting to non-cacheable."""

    data = _load_policy_file(path)
    default = dict(data.get("default") or {})
    override = dict((data.get("tools") or {}).get(tool_slug) or {})
    return _build_policy(tool_slug, {**default, **override})

