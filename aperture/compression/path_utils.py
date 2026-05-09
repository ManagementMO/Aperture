"""Small helpers for nested payload paths."""

from __future__ import annotations

from typing import Any


def get_path(payload: Any, dotted_path: str) -> Any:
    current = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_path(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = payload
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            return
        current = child
    current[parts[-1]] = value


def delete_path(payload: Any, dotted_path: str) -> bool:
    if not isinstance(payload, dict):
        return False
    parts = dotted_path.split(".")
    current = payload
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if isinstance(current, dict) and parts[-1] in current:
        del current[parts[-1]]
        return True
    return False

