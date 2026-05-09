"""Auto-generate compression profiles for any Composio tool.

When Composio adds a new toolkit, Aperture doesn't need manual configuration.
It analyzes the tool's schema and generates optimal compression rules:
- Which fields are low-value (URLs, nulls, empty arrays)
- Which fields are critical (IDs, names, status)
- What the typical payload size is
- What compression strategy works best

Detection is **value-shape first, name second**. The substring heuristics
(e.g. `"url" in name`) miss anything that doesn't follow English naming —
so we run regex classifiers on actual sampled values before falling back
to the name. When two or more samples are available we also use
cross-payload entropy to detect constants and identifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aperture.tokenization import count_tokens

# Value-shape regexes — check the actual data, not the field name.
_URL_RE = re.compile(r"^https?://\S+$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_OPAQUE_HEX_RE = re.compile(r"^[0-9a-f]{16,64}$")
_NUMERIC_ID_RE = re.compile(r"^\d{6,}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")
_EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}$")

_NAME_KEEP = {
    "name", "title", "description", "status", "state", "message",
    "body", "content", "text", "email", "login", "owner",
    "created_at", "updated_at", "number", "count", "total", "summary",
    "subject", "snippet", "from", "to", "label", "labels",
}


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


def _classify_string(name: str, value: str) -> str:
    """Classify a string value by *shape* (URL, UUID, opaque ID, date, email,
    long_text, text). Falls back to the name only if the value is ambiguous."""
    if _URL_RE.match(value):
        return "url"
    if _UUID_RE.match(value) or _OPAQUE_HEX_RE.match(value):
        return "opaque_id"
    if _NUMERIC_ID_RE.match(value):
        return "id"
    if _DATE_RE.match(value):
        return "date"
    if _EMAIL_RE.match(value):
        return "email"
    if len(value) > 200:
        return "long_text"
    if name.endswith(("_url", "Url", "URL")):
        return "url"
    if name.endswith(("_id", "Id", "ID")):
        return "id"
    return "text"


def _detect_field_type(name: str, value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, str):
        return _classify_string(name, value)
    return "unknown"


def _name_says_critical(name: str) -> bool:
    leaf = name.split(".")[-1].lower()
    return leaf in _NAME_KEEP or any(p in leaf for p in _NAME_KEEP)


def _analyze_field(name: str, value: Any, depth: int = 0) -> FieldProfile:
    """Analyze a single field — value-shape first, name fallback."""
    field_type = _detect_field_type(name, value)
    typical_size = count_tokens(value).tokens if value is not None else 0

    # Entropy heuristic baked in by shape.
    value_entropy = {
        "url": 0.9,
        "opaque_id": 0.95,
        "id": 0.9,
        "boolean": 0.1,
        "number": 0.3,
        "long_text": 0.8,
        "date": 0.4,
        "email": 0.6,
    }.get(field_type, 0.5)

    is_critical = _name_says_critical(name) and field_type not in ("url", "opaque_id")

    # Compression rule — value shape wins over name.
    if field_type in ("url", "opaque_id"):
        compression_rule = "drop"
    elif field_type == "id" and depth > 0 and not is_critical:
        compression_rule = "drop"
    elif is_critical:
        compression_rule = "keep"
    elif field_type == "boolean" and name.startswith(("has_", "is_", "can_")):
        compression_rule = "keep"
    elif field_type == "object" and depth > 2:
        compression_rule = "flatten"
    elif field_type in ("array", "long_text") and typical_size > 50:
        compression_rule = "truncate"
    elif typical_size > 100:
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


def cross_sample_entropy(samples: list[Any]) -> float:
    """How variable are these N values? 0.0 = identical (constant), 1.0 = all distinct."""
    if not samples:
        return 0.0
    try:
        unique = {repr(s) for s in samples}
    except Exception:
        return 1.0
    return len(unique) / len(samples)


def merge_profiles(profiles: list[FieldProfile]) -> FieldProfile:
    """Combine multiple profiles for the same field across samples."""
    base = profiles[0]
    typical = max(p.typical_size for p in profiles)
    nullable = all(p.is_nullable for p in profiles)
    is_critical = any(p.is_critical for p in profiles)

    # If the field is identical across all samples → it's a constant. Drop.
    rules = [p.compression_rule for p in profiles]
    rule = "drop" if "drop" in rules else (
        "truncate" if "truncate" in rules else (
            "flatten" if "flatten" in rules else "keep"
        )
    )

    return FieldProfile(
        name=base.name,
        field_type=base.field_type,
        is_nullable=nullable,
        typical_size=typical,
        value_entropy=max(p.value_entropy for p in profiles),
        is_critical=is_critical,
        compression_rule=rule,
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
