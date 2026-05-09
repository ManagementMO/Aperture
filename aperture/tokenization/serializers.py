"""Stable, deterministic JSON serialization for token counting and hashing."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def _default_encoder(obj: Any) -> Any:
    """Handle dataclasses and other non-JSON types safely."""
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def stable_json_dumps(payload: object) -> str:
    """Return a deterministic JSON string.

    Requirements:
    - Same payload = same string
    - Nested keys sorted
    - No payload mutation
    - Compact separators
    - Unicode preserved
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default_encoder,
    )
