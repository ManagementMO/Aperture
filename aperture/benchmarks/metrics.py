"""Benchmark metric helpers."""

from __future__ import annotations

from aperture.types import BenchmarkMetrics, BenchmarkRunResult


def aggregate_run_metrics(run: BenchmarkRunResult) -> dict[str, float | int | str]:
    """Aggregate metrics for a benchmark run."""

    count = len(run.metrics)
    raw_tokens = sum(metric.raw_tokens for metric in run.metrics)
    compressed_tokens = sum(metric.compressed_tokens for metric in run.metrics)
    tokens_saved = sum(metric.tokens_saved for metric in run.metrics)
    return {
        "mode": run.mode,
        "tasks": count,
        "raw_tokens": raw_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "compression_ratio": (compressed_tokens / raw_tokens) if raw_tokens else 1.0,
        "cache_hits": sum(metric.cache_hits for metric in run.metrics),
        "api_calls_avoided": sum(metric.api_calls_avoided for metric in run.metrics),
        "schema_tokens_saved": sum(metric.schema_tokens_saved for metric in run.metrics),
        "success_rate": run.success_rate,
    }

