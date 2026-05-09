"""Tool context selection based on effort mode."""

from typing import Any

from aperture.contracts import ApertureRunConfig
from aperture.routing.effort_modes import get_effort_config
from aperture.tokenization import count_tokens


def select_tool_context(
    tools: list[dict[str, Any]],
    config: ApertureRunConfig,
) -> dict[str, Any]:
    """Select and compact tool schemas based on effort mode.

    Returns:
        Dict with 'exposed_tools', 'full_schema_tokens', 'exposed_schema_tokens', 'tokens_saved'
    """
    effort = get_effort_config(config.effort_mode)

    full_tokens = 0
    exposed_tools = []

    for tool in tools:
        full_tokens += count_tokens(tool).tokens
        compacted = _compact_tool_schema(tool, effort)
        exposed_tools.append(compacted)

    # Limit tool count if configured
    if effort.max_tools_exposed and len(exposed_tools) > effort.max_tools_exposed:
        exposed_tools = exposed_tools[: effort.max_tools_exposed]

    exposed_tokens = sum(count_tokens(t).tokens for t in exposed_tools)

    return {
        "exposed_tools": exposed_tools,
        "full_schema_tokens": full_tokens,
        "exposed_schema_tokens": exposed_tokens,
        "tokens_saved": full_tokens - exposed_tokens,
    }


def _compact_tool_schema(tool: dict[str, Any], effort) -> dict[str, Any]:
    """Compact a single tool schema based on effort config."""
    result = {
        "type": tool.get("type", "function"),
        "function": {
            "name": tool.get("function", {}).get("name", ""),
            "description": tool.get("function", {}).get("description", ""),
        },
    }

    # Compact parameters
    params = tool.get("function", {}).get("parameters", {})
    compacted_params = _compact_parameters(params, effort)
    if compacted_params:
        result["function"]["parameters"] = compacted_params

    return result


def _compact_parameters(params: dict[str, Any], effort) -> dict[str, Any]:
    """Compact parameter definitions."""
    if not params:
        return {}

    result = {
        "type": params.get("type", "object"),
        "properties": {},
        "required": params.get("required", []),
    }

    for name, prop in params.get("properties", {}).items():
        compacted = {}

        # Always keep type and description
        if "type" in prop:
            compacted["type"] = prop["type"]
        if "description" in prop:
            compacted["description"] = prop["description"]

        # Optional: drop examples, enum descriptions
        if effort.include_examples and "examples" in prop:
            compacted["examples"] = prop["examples"]
        if "enum" in prop:
            compacted["enum"] = prop["enum"]

        result["properties"][name] = compacted

    return result
