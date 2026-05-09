"""Deterministic serialization for token attribution."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported payload value for stable serialization: {type(value).__name__}")


def stable_serialize_payload(payload: object) -> str:
    """Serialize payload deterministically for token counting."""

    safe_payload = _json_safe(payload)
    return json.dumps(
        safe_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

