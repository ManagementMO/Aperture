"""Field pruning for low-value API payload metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aperture.compression.profile_loader import CompressionProfile


def _is_preserved(path: str, key: str, profile: CompressionProfile) -> bool:
    return path in profile.preserve_fields or key in profile.preserve_fields


def _should_drop_api_url(key: str, value: Any, profile: CompressionProfile) -> bool:
    if not profile.drop_obvious_api_urls or not isinstance(value, str):
        return False
    if key in {"html_url", "permalink", "url"}:
        return False
    return key.endswith("_url") or key in {"api_url"}


def _prune(value: Any, profile: CompressionProfile, path: str, omitted: list[str]) -> Any:
    if isinstance(value, list):
        return [_prune(item, profile, path, omitted) for item in value]
    if not isinstance(value, dict):
        return value

    pruned: dict[str, Any] = {}
    for key, item in value.items():
        item_path = f"{path}.{key}" if path else key
        if _is_preserved(item_path, key, profile):
            pruned[key] = _prune(item, profile, item_path, omitted)
            continue
        if item_path in profile.drop_fields or key in profile.drop_fields:
            omitted.append(item_path)
            continue
        if profile.drop_nulls and item is None:
            omitted.append(item_path)
            continue
        if profile.drop_empty_strings and item == "":
            omitted.append(item_path)
            continue
        if profile.drop_empty_arrays and item == []:
            omitted.append(item_path)
            continue
        if _should_drop_api_url(key, item, profile):
            omitted.append(item_path)
            continue
        pruned[key] = _prune(item, profile, item_path, omitted)
    return pruned


def prune_fields(payload: object, profile: CompressionProfile) -> tuple[object, list[str]]:
    """Remove configured low-value fields while preserving critical fields."""

    omitted: list[str] = []
    return _prune(deepcopy(payload), profile, "", omitted), omitted

