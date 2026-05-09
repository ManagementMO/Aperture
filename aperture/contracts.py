"""Shared dataclasses and type contracts for Aperture."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TokenCount:
    """Result of tokenizing a payload."""

    tokens: int
    tokenizer: str
    approximate: bool = False


@dataclass(frozen=True)
class ApertureRunConfig:
    """Configuration for a single Aperture-enhanced run."""

    run_id: str
    tenant_id: str | None = None
    user_id: str | None = None
    connected_account_id: str | None = None
    model: str | None = None
    effort_mode: str = "medium"  # low | medium | high | off | shadow
    cache_bypass: bool = False


@dataclass(frozen=True)
class ToolCall:
    """A single tool call request."""

    toolkit_slug: str | None
    tool_slug: str
    arguments: dict[str, Any]
    user_id: str | None = None


@dataclass
class CompressionResult:
    """Result of compressing a tool output."""

    compressed_payload: object
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    raw_reference_id: str | None = None
    strategy: str = "safe"
    omitted_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # When the LLM-bound payload should be sent in a non-JSON format (TOON,
    # caveman-prose, etc.) the engine fills `llm_format` + `llm_string`.
    # `compressed_tokens` reflects the LLM-bound representation, not the JSON.
    llm_format: str = "json"
    llm_string: str | None = None


@dataclass
class CacheEvent:
    """Record of a cache lookup."""

    run_id: str
    toolkit_slug: str | None
    tool_slug: str
    cache_status: str  # hit | miss | bypass | not_cacheable | error
    cache_scope: str = "user"
    cache_key_hash: str | None = None
    schema_version: str | None = None
    api_version: str | None = None
    freshness_policy: str | None = None
    api_call_avoided: bool = False
    tokens_saved_estimate: int = 0
    reason: str | None = None


@dataclass
class TokenEvent:
    """Record of token attribution for a payload."""

    event_type: str  # schema | argument | result | compressed | cache
    run_id: str
    toolkit_slug: str | None = None
    tool_slug: str | None = None
    payload_kind: str = "result"  # schema | argument | result | compressed | cache
    model: str | None = None
    tokenizer: str = "cl100k_base"
    approximate: bool = False
    raw_tokens: int = 0
    compressed_tokens: int = 0
    tokens_saved: int = 0
    compression_ratio: float | None = None
    cache_status: str | None = None
