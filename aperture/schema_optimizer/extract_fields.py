"""Extract description fields from tool schemas."""

from __future__ import annotations

from typing import Any

from aperture.schema_optimizer.models import SchemaField


def _tool_slug(schema: dict[str, Any]) -> str:
    return str(schema.get("slug") or schema.get("name") or "UNKNOWN_TOOL")


def extract_description_fields(schema: dict) -> list[SchemaField]:
    """Extract tool and parameter description fields with paths."""

    tool_slug = _tool_slug(schema)
    fields: list[SchemaField] = []
    description = schema.get("description")
    if isinstance(description, str) and description:
        fields.append(SchemaField(tool_slug, "description", description))

    parameters = schema.get("parameters") or schema.get("input_schema") or {}
    properties = parameters.get("properties", {}) if isinstance(parameters, dict) else {}
    for name, prop in sorted(properties.items()):
        if isinstance(prop, dict) and isinstance(prop.get("description"), str):
            fields.append(SchemaField(tool_slug, f"parameters.properties.{name}.description", prop["description"]))
        enum = prop.get("enum") if isinstance(prop, dict) else None
        enum_description = prop.get("enum_description") if isinstance(prop, dict) else None
        if enum and isinstance(enum_description, str):
            fields.append(SchemaField(tool_slug, f"parameters.properties.{name}.enum_description", enum_description))
    return fields

