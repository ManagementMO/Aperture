"""Shared data contracts for Aperture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    tokenizer: str
    tokenizer_is_approximate: bool
    payload_bytes: int


@dataclass(frozen=True)
class ExecutionContext:
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    model: str | None
    cache_bypass: bool = False
    compression_bypass: bool = False


@dataclass(frozen=True)
class TokenAttributionEvent:
    event_type: str
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    payload_kind: str
    model: str | None
    tokenizer: str
    tokenizer_is_approximate: bool
    raw_payload_bytes: int | None
    compressed_payload_bytes: int | None
    raw_tokens: int | None
    compressed_tokens: int | None
    input_tokens_contributed: int
    tokens_saved: int
    compression_ratio: float | None
    cache_status: str | None
    aperture_version: str


@dataclass(frozen=True)
class CompressionContext:
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str
    user_goal: str | None
    model: str | None
    mode: str


@dataclass(frozen=True)
class CompressionResult:
    compressed_payload: object
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    raw_reference_id: str | None
    strategy: str
    omitted_fields: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class CachePolicy:
    tool_slug: str
    cacheable: bool
    operation_type: str
    privacy_scope: str
    ttl_seconds: int | None
    matching: str
    reason: str | None = None


@dataclass(frozen=True)
class CacheEvent:
    event_type: str
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    tool_slug: str
    toolkit_slug: str | None
    cache_status: str
    cache_scope: str
    cache_key_hash: str | None
    ttl_seconds: int | None
    cached_age_seconds: int | None
    api_call_avoided: bool
    tokens_saved_estimate: int
    reason: str | None


@dataclass(frozen=True)
class SchemaOptimizationResult:
    tool_slug: str
    field_path: str
    original_text: str
    optimized_text: str
    original_tokens: int
    optimized_tokens: int
    reduction_tokens: int
    reduction_pct: float
    validation_cases_run: int
    validation_passed: bool
    accepted: bool
    rejection_reason: str | None


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    category: str
    user_prompt: str
    tool_slug: str
    params: dict[str, Any]
    fixture: str
    expected_fields: list[str]
    critical_fields: list[str]
    evaluation_type: str = "field_presence"


@dataclass(frozen=True)
class BenchmarkMetrics:
    task_id: str
    mode: str
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    cache_hits: int
    api_calls_avoided: int
    schema_tokens_saved: int
    task_success: bool
    success_score: float
    missing_critical_info: bool
    extra_tool_calls: int
    raw_fallback_used: bool
    latency_ms: int


@dataclass(frozen=True)
class BenchmarkRunResult:
    mode: str
    metrics: list[BenchmarkMetrics] = field(default_factory=list)

    @property
    def total_tokens_saved(self) -> int:
        return sum(metric.tokens_saved for metric in self.metrics)

    @property
    def success_rate(self) -> float:
        if not self.metrics:
            return 0.0
        return sum(1 for metric in self.metrics if metric.task_success) / len(self.metrics)

