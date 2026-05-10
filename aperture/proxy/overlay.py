"""Schema overlay loading and application for proxy responses."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import mcp.types as mcp_types

logger = logging.getLogger(__name__)


def default_overlay_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schema_optimizer" / "_overlay.json"


class SchemaOverlay:
    """Best-effort description rewrite overlay.

    Missing or malformed overlay files disable the layer. Applying an overlay
    must never block or fail a proxy request.
    """

    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None
        self._tools: dict[str, dict[str, dict[str, Any]]] = {}
        if self.path is not None:
            self.reload()

    @property
    def enabled(self) -> bool:
        return bool(self._tools)

    def reload(self) -> None:
        if self.path is None or not self.path.exists():
            self._tools = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            tools = data.get("tools") if isinstance(data, dict) else None
            self._tools = tools if isinstance(tools, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to load schema overlay %s: %s", self.path, exc)
            self._tools = {}

    def apply_to_tools(self, tools: list[mcp_types.Tool]) -> list[mcp_types.Tool]:
        if not self.enabled:
            return tools
        return [self._apply_to_mcp_tool(tool) for tool in tools]

    def apply_to_payload(self, payload: Any) -> Any:
        if not self.enabled:
            return payload
        return self._apply_to_any(deepcopy(payload))

    def _apply_to_mcp_tool(self, tool: mcp_types.Tool) -> mcp_types.Tool:
        fields = self._tools.get(tool.name)
        if not fields:
            return tool
        updates: dict[str, Any] = {}
        if "description" in fields:
            updates["description"] = fields["description"].get("optimized", tool.description)
        input_schema = deepcopy(tool.inputSchema)
        for field_path, entry in fields.items():
            if field_path == "description":
                continue
            _set_field_path(input_schema, _schema_path(field_path), entry.get("optimized"))
        if input_schema != tool.inputSchema:
            updates["inputSchema"] = input_schema
        return tool.model_copy(update=updates) if updates else tool

    def _apply_to_any(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._apply_to_any(item) for item in value]
        if not isinstance(value, dict):
            return value

        function = value.get("function") if isinstance(value.get("function"), dict) else None
        slug = value.get("slug") or value.get("name") or (function or {}).get("name")
        if isinstance(slug, str) and slug in self._tools:
            target = function if function is not None else value
            self._apply_fields_to_dict(target, self._tools[slug])

        for key, item in list(value.items()):
            if key != "function":
                value[key] = self._apply_to_any(item)
        return value

    def _apply_fields_to_dict(self, target: dict[str, Any], fields: dict[str, dict[str, Any]]) -> None:
        for field_path, entry in fields.items():
            optimized = entry.get("optimized")
            if not isinstance(optimized, str):
                continue
            if field_path == "description":
                target["description"] = optimized
            else:
                _set_field_path(target, field_path.split("."), optimized)


def _schema_path(field_path: str) -> list[str]:
    parts = field_path.split(".")
    if parts and parts[0] == "parameters":
        return parts[1:]
    return parts


def _set_field_path(target: dict[str, Any], parts: list[str], value: Any) -> None:
    if value is None:
        return
    current: Any = target
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, dict) and parts:
        current[parts[-1]] = value
