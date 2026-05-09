"""Benchmark report generation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from aperture.benchmarks.metrics import aggregate_run_metrics
from aperture.types import BenchmarkRunResult


def _markdown_table(rows: list[dict]) -> str:
    headers = ["mode", "tasks", "raw_tokens", "compressed_tokens", "tokens_saved", "compression_ratio", "cache_hits", "api_calls_avoided", "schema_tokens_saved", "success_rate"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                f"{row[key]:.3f}" if isinstance(row[key], float) else str(row[key])
                for key in headers
            )
            + " |"
        )
    return "\n".join(lines)


def build_benchmark_report(runs: list[BenchmarkRunResult]) -> str:
    """Build a Markdown benchmark report."""

    summaries = [aggregate_run_metrics(run) for run in runs]
    failure_lines = []
    for run in runs:
        for metric in run.metrics:
            if not metric.task_success:
                failure_lines.append(f"- `{run.mode}` / `{metric.task_id}`: score={metric.success_score:.2f}")
    failures = "\n".join(failure_lines) if failure_lines else "_No benchmark failures._"
    return (
        "# Aperture Benchmark Report\n\n"
        "Deterministic fixture benchmark comparing raw Composio-style outputs against Aperture modes.\n\n"
        "## Summary\n\n"
        + _markdown_table(summaries)
        + "\n\n## Failure Cases\n\n"
        + failures
        + "\n\n## Recommendation\n\n"
        "Use `balanced` compression with exact-match caching for profiled read tools. Keep raw references enabled.\n"
    )


def write_benchmark_outputs(runs: list[BenchmarkRunResult], out_dir: Path) -> None:
    """Write benchmark metrics JSON and Markdown report."""

    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = [
        {
            "mode": run.mode,
            "summary": aggregate_run_metrics(run),
            "metrics": [asdict(metric) for metric in run.metrics],
        }
        for run in runs
    ]
    (out_dir / "benchmark_metrics.json").write_text(json.dumps(metrics_payload, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "benchmark_report.md").write_text(build_benchmark_report(runs), encoding="utf-8")
    raw_run = next((run for run in runs if run.mode == "raw"), None)
    compressed_run = next((run for run in runs if run.mode == "aperture_compressed"), None)
    cached_run = next((run for run in runs if run.mode == "aperture_cached"), None)
    if raw_run:
        raw_rows = "\n".join(
            f"| {metric.task_id} | {metric.raw_tokens} |"
            for metric in raw_run.metrics
        )
        (out_dir / "raw_token_baseline.md").write_text(
            "# Raw Token Baseline\n\n| Task | Raw Tokens |\n| --- | --- |\n" + raw_rows + "\n",
            encoding="utf-8",
        )
    if compressed_run:
        rows = "\n".join(
            f"| {metric.task_id} | {metric.raw_tokens} | {metric.compressed_tokens} | {metric.tokens_saved} | {metric.compression_ratio:.3f} |"
            for metric in compressed_run.metrics
        )
        (out_dir / "compression_report.md").write_text(
            "# Compression Report\n\n| Task | Raw | Compressed | Saved | Ratio |\n| --- | --- | --- | --- | --- |\n" + rows + "\n",
            encoding="utf-8",
        )
    if cached_run:
        rows = "\n".join(
            f"| {metric.task_id} | {metric.cache_hits} | {metric.api_calls_avoided} |"
            for metric in cached_run.metrics
        )
        (out_dir / "cache_report.md").write_text(
            "# Cache Report\n\n| Task | Cache Hits | API Calls Avoided |\n| --- | --- | --- |\n" + rows + "\n",
            encoding="utf-8",
        )
