"""Parameter normalization for exact-match cache keys."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            if not str(key).startswith("aperture_")
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def normalize_params(tool_slug: str, params: dict) -> dict:
    """Normalize params for exact-match keying."""

    del tool_slug
    return _normalize(deepcopy(params))

