"""Auto-generate compression profiles for any Composio tool.

When Composio adds a new toolkit, Aperture doesn't need manual configuration.
It analyzes the tool's schema and generates optimal compression rules:
- Which fields are low-value (URLs, nulls, empty arrays)
- Which fields are critical (IDs, names, status)
- What the typical payload size is
- What compression strategy works best

This is how Aperture scales to 1000+ Composio tools without hand-tuning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aperture.tokenization import count_tokens


@dataclass
class FieldProfile:
    """Analysis of a single field in a tool schema."""

    name: str
    field_type: str  # "url", "id", "text", "number", "boolean", "object", "array"
    is_nullable: bool
    typical_size: int  # tokens in a typical value
    value_entropy: float  # 0.0 = always same, 1.0 = highly variable
    is_critical: bool = False  # Determined by heuristics
    compression_rule: str = "keep"  # "keep", "truncate", "flatten", "drop"


@dataclass
class ToolProfile:
    """Auto-generated compression profile for a tool."""

    tool_slug: str
    toolkit: str
    typical_raw_tokens: int = 0
    typical_compressed_tokens: int = 0
    estimated_savings: float = 0.0
    field_profiles: list[FieldProfile] = field(default_factory=list)
    recommended_mode: str = "balanced"
    critical_fields: list[str] = field(default_factory=list)
    droppable_fields: list[str] = field(default_factory=list)


def _analyze_field(name: str, value: Any, depth: int = 0) -> FieldProfile:
    """Analyze a single field to determine its compression characteristics."""
    # Determine type
    if isinstance(value, str):
        if name.endswith(("_url", "Url", "URL")) or "url" in name.lower():
            field_type = "url"
        elif name.endswith(("_id", "Id", "ID")) or "id" in name.lower():
            field_type = "id"
        elif len(value) > 200:
            field_type = "long_text"
        else:
            field_type = "text"
    elif isinstance(value, bool):
        field_type = "boolean"
    elif isinstance(value, (int, float)):
        field_type = "number"
    elif isinstance(value, list):
        field_type = "array"
    elif isinstance(value, dict):
        field_type = "object"
    else:
        field_type = "unknown"

    # Size analysis
    typical_size = count_tokens(value).tokens if value is not None else 0

    # Entropy heuristic: URLs and IDs are high-entropy but low-value to LLMs
    if field_type in ("url", "id"):
        value_entropy = 0.9
    elif field_type == "boolean":
        value_entropy = 0.1
    elif field_type == "number":
        value_entropy = 0.3
    elif field_type == "long_text":
        value_entropy = 0.8
    else:
        value_entropy = 0.5

    # Critical field heuristics
    is_critical = False
    critical_patterns = [
        "name", "title", "description", "status", "state", "message",
        "body", "content", "text", "email", "login", "owner",
        "created_at", "updated_at", "number", "count", "total",
    ]
    for pattern in critical_patterns:
        if pattern in name.lower():
            is_critical = True
            break

    # Compression rule
    if is_critical:
        compression_rule = "keep"
    elif field_type == "url":
        compression_rule = "drop"
    elif field_type == "id" and depth > 1:
        compression_rule = "drop"
    elif field_type == "boolean" and name.startswith(("has_", "is_", "can_")):
        compression_rule = "keep"
    elif field_type == "object" and depth > 2:
        compression_rule = "flatten"
    elif field_type == "array" and typical_size > 50:
        compression_rule = "truncate"
    elif typical_size > 100 and not is_critical:
        compression_rule = "truncate"
    else:
        compression_rule = "keep"

    return FieldProfile(
        name=name,
        field_type=field_type,
        is_nullable=value is None or value == [] or value == {},
        typical_size=typical_size,
        value_entropy=value_entropy,
        is_critical=is_critical,
        compression_rule=compression_rule,
    )


def analyze_payload(payload: object, prefix: str = "", depth: int = 0) -> list[FieldProfile]:
    """Recursively analyze a payload and return field profiles."""
    profiles: list[FieldProfile] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            full_name = f"{prefix}.{key}" if prefix else key
            profile = _analyze_field(full_name, value, depth)
            profiles.append(profile)

            # Recurse into nested objects
            if isinstance(value, dict) and depth < 5:
                profiles.extend(analyze_payload(value, full_name, depth + 1))
            elif isinstance(value, list) and value and isinstance(value[0], dict) and depth < 5:
                # Analyze first item as representative
                profiles.extend(analyze_payload(value[0], full_name, depth + 1))

    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        # Analyze structure of list items
        profiles.extend(analyze_payload(payload[0], prefix, depth))

    return profiles


def generate_tool_profile(tool_slug: str, sample_payload: object) -> ToolProfile:
    """Generate a compression profile from a sample payload.

    This is the core scalability feature: feed Aperture ONE example response
    from a new Composio tool, and it automatically learns how to compress it.
    """
    parts = tool_slug.split("_")
    toolkit = parts[0].lower() if parts else "unknown"

    raw_tokens = count_tokens(sample_payload).tokens
    profiles = analyze_payload(sample_payload)

    critical = [p.name for p in profiles if p.is_critical]
    droppable = [p.name for p in profiles if p.compression_rule == "drop"]

    # Estimate compressed size
    compressed_estimate = sum(
        p.typical_size for p in profiles if p.compression_rule == "keep"
    )
    # Add truncated fields at 30% of original
    compressed_estimate += sum(
        p.typical_size * 0.3 for p in profiles if p.compression_rule == "truncate"
    )
    # Add flattened objects at 50% of original
    compressed_estimate += sum(
        p.typical_size * 0.5 for p in profiles if p.compression_rule == "flatten"
    )

    savings = (raw_tokens - compressed_estimate) / raw_tokens if raw_tokens > 0 else 0

    # Recommend mode based on payload size
    if raw_tokens < 500:
        recommended = "safe"
    elif raw_tokens < 2000:
        recommended = "balanced"
    elif raw_tokens < 8000:
        recommended = "safe" if len(critical) > 10 else "balanced"
    else:
        recommended = "balanced" if len(critical) < 5 else "safe"

    return ToolProfile(
        tool_slug=tool_slug,
        toolkit=toolkit,
        typical_raw_tokens=raw_tokens,
        typical_compressed_tokens=int(compressed_estimate),
        estimated_savings=round(savings, 3),
        field_profiles=profiles,
        recommended_mode=recommended,
        critical_fields=critical,
        droppable_fields=droppable,
    )


def register_new_toolkit(
    toolkit_name: str,
    tool_schemas: dict[str, object],
) -> dict[str, ToolProfile]:
    """Register an entire Composio toolkit and auto-generate profiles for all tools.

    Usage:
        profiles = register_new_toolkit("shopify", {
            "SHOPIFY_LIST_PRODUCTS": sample_products_response,
            "SHOPIFY_GET_ORDER": sample_order_response,
        })
    """
    profiles: dict[str, ToolProfile] = {}
    for tool_slug, sample_payload in tool_schemas.items():
        profiles[tool_slug] = generate_tool_profile(tool_slug, sample_payload)
    return profiles


class ProfileRegistry:
    """Central registry for all tool compression profiles.

    New toolkits are registered dynamically. No restarts needed.
    """

    def __init__(self):
        self._profiles: dict[str, ToolProfile] = {}

    def register(self, tool_slug: str, sample_payload: object) -> ToolProfile:
        """Register a single tool with a sample payload."""
        profile = generate_tool_profile(tool_slug, sample_payload)
        self._profiles[tool_slug] = profile
        return profile

    def register_toolkit(self, toolkit_name: str, tool_schemas: dict[str, object]) -> dict[str, ToolProfile]:
        """Register an entire toolkit."""
        profiles = register_new_toolkit(toolkit_name, tool_schemas)
        self._profiles.update(profiles)
        return profiles

    def get(self, tool_slug: str) -> ToolProfile | None:
        return self._profiles.get(tool_slug)

    def list_toolkits(self) -> set[str]:
        return set(p.toolkit for p in self._profiles.values())

    def stats(self) -> dict:
        if not self._profiles:
            return {}
        total_raw = sum(p.typical_raw_tokens for p in self._profiles.values())
        total_compressed = sum(p.typical_compressed_tokens for p in self._profiles.values())
        return {
            "tools_registered": len(self._profiles),
            "toolkits": len(self.list_toolkits()),
            "total_raw_tokens": total_raw,
            "total_compressed_tokens": total_compressed,
            "avg_savings": round((total_raw - total_compressed) / total_raw, 3) if total_raw > 0 else 0,
        }
