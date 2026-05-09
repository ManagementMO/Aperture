"""Effort mode configurations for schema exposure and result detail."""

from dataclasses import dataclass, field


@dataclass
class EffortConfig:
    """Configuration for a single effort mode."""

    name: str
    description: str
    # Schema exposure
    max_tools_exposed: int | None = None
    include_optional_fields: bool = True
    include_examples: bool = True
    include_enum_descriptions: bool = True
    # Result detail
    compression_mode: str = "safe"  # safe | balanced | aggressive
    max_result_items: int | None = None
    # Caching
    cache_reads: bool = True
    cache_ttl_seconds: int = 300
    # Fallback
    allow_fallback_expansion: bool = False


EFFORT_MODES: dict[str, EffortConfig] = {
    "low": EffortConfig(
        name="low",
        description="Minimal context, aggressive caching, expand only on failure",
        max_tools_exposed=10,
        include_optional_fields=False,
        include_examples=False,
        include_enum_descriptions=False,
        compression_mode="balanced",
        max_result_items=5,
        cache_reads=True,
        cache_ttl_seconds=600,
        allow_fallback_expansion=True,
    ),
    "medium": EffortConfig(
        name="medium",
        description="Balanced context and caching",
        max_tools_exposed=20,
        include_optional_fields=True,
        include_examples=False,
        include_enum_descriptions=False,
        compression_mode="balanced",
        max_result_items=10,
        cache_reads=True,
        cache_ttl_seconds=300,
        allow_fallback_expansion=True,
    ),
    "high": EffortConfig(
        name="high",
        description="Full context, minimal caching, maximum detail",
        max_tools_exposed=None,
        include_optional_fields=True,
        include_examples=True,
        include_enum_descriptions=True,
        compression_mode="safe",
        max_result_items=None,
        cache_reads=False,
        cache_ttl_seconds=60,
        allow_fallback_expansion=False,
    ),
    "off": EffortConfig(
        name="off",
        description="No Aperture optimization",
        max_tools_exposed=None,
        include_optional_fields=True,
        include_examples=True,
        include_enum_descriptions=True,
        compression_mode="off",
        max_result_items=None,
        cache_reads=False,
        cache_ttl_seconds=0,
        allow_fallback_expansion=False,
    ),
}


def get_effort_config(mode: str) -> EffortConfig:
    if mode not in EFFORT_MODES:
        return EFFORT_MODES["medium"]
    return EFFORT_MODES[mode]
