"""Aperture core package."""

__version__ = "0.3.0"

from aperture.config import ApertureConfig
from aperture.types import (
    BenchmarkMetrics,
    BenchmarkRunResult,
    BenchmarkTask,
    CacheEvent,
    CachePolicy,
    CompressionContext,
    CompressionResult,
    ExecutionContext,
    SchemaOptimizationResult,
    TokenAttributionEvent,
    TokenCount,
)

__all__ = [
    "ApertureConfig",
    "BenchmarkMetrics",
    "BenchmarkRunResult",
    "BenchmarkTask",
    "CacheEvent",
    "CachePolicy",
    "CompressionContext",
    "CompressionResult",
    "ExecutionContext",
    "SchemaOptimizationResult",
    "TokenAttributionEvent",
    "TokenCount",
]

