"""Deterministic raw vs Aperture benchmark runner."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aperture.benchmarks.evaluators import field_presence_score, has_missing_critical_info
from aperture.benchmarks.task_set import load_tasks
from aperture.cache.redis_store import InMemoryCacheStore
from aperture.integration.pipeline import aperture_tool_result_pipeline
from aperture.observability.event_emitter import (
    clear_in_memory_events,
    get_in_memory_cache_events,
)
from aperture.schema_optimizer.reports import optimize_schemas
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import BenchmarkMetrics, BenchmarkRunResult, BenchmarkTask, ExecutionContext

VALID_MODES = {"raw", "aperture_compressed", "aperture_cached", "aperture_full", "shadow"}


def _fixture_path(name: str) -> Path:
    return Path(__file__).parents[1] / "fixtures" / "tool_outputs" / name


def _load_fixture(name: str) -> object:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _execution_context(task: BenchmarkTask, *, cache_bypass: bool = False) -> ExecutionContext:
    return ExecutionContext(
        project_id="fixture_project",
        user_id="fixture_user",
        session_id="fixture_session",
        connected_account_id="fixture_account",
        toolkit_slug=task.category.upper(),
        tool_slug=task.tool_slug,
        meta_tool_slug=None,
        model="gpt-4o-mini",
        cache_bypass=cache_bypass,
        compression_bypass=False,
    )


def _schema_savings_by_tool() -> dict[str, int]:
    savings: dict[str, int] = {}
    for result in optimize_schemas(live=False):
        if result.accepted:
            savings[result.tool_slug] = savings.get(result.tool_slug, 0) + result.reduction_tokens
    return savings


async def _run_task(task: BenchmarkTask, mode: str, store: InMemoryCacheStore, schema_savings: dict[str, int]) -> BenchmarkMetrics:
    raw_payload = _load_fixture(task.fixture)
    raw_count = count_tokens_for_payload(raw_payload, model="gpt-4o-mini")

    if mode == "raw":
        payload = raw_payload
        compressed_tokens = raw_count.tokens
        tokens_saved = 0
        cache_hits = 0
        api_calls_avoided = 0
    else:
        context = _execution_context(task, cache_bypass=mode == "aperture_compressed" or mode == "shadow")
        if mode == "shadow":
            # Shadow mode measures compression separately but returns raw-like output.
            context = ExecutionContext(**{**context.__dict__, "compression_bypass": False})
        execute_calls = {"count": 0}

        def execute_fn() -> object:
            execute_calls["count"] += 1
            return raw_payload

        clear_in_memory_events()
        payload = await aperture_tool_result_pipeline(task.tool_slug, task.params, context, execute_fn, cache_store=store)
        if mode in {"aperture_cached", "aperture_full"}:
            payload = await aperture_tool_result_pipeline(task.tool_slug, task.params, context, execute_fn, cache_store=store)
        if mode == "shadow":
            payload = raw_payload
        cache_events = get_in_memory_cache_events()
        cache_hits = sum(1 for event in cache_events if event.cache_status == "hit")
        api_calls_avoided = sum(1 for event in cache_events if event.api_call_avoided)
        if isinstance(payload, dict) and payload.get("aperture_compressed"):
            compressed_tokens = int(payload["compression"]["compressed_tokens"])
            tokens_saved = int(payload["compression"]["tokens_saved"])
        else:
            compressed_tokens = count_tokens_for_payload(payload, model="gpt-4o-mini").tokens
            tokens_saved = max(0, raw_count.tokens - compressed_tokens)

    score = field_presence_score(payload, task.expected_fields)
    missing_critical = has_missing_critical_info(payload, task.critical_fields)
    return BenchmarkMetrics(
        task_id=task.task_id,
        mode=mode,
        raw_tokens=raw_count.tokens,
        compressed_tokens=compressed_tokens,
        tokens_saved=tokens_saved,
        compression_ratio=(compressed_tokens / raw_count.tokens) if raw_count.tokens else 1.0,
        cache_hits=cache_hits,
        api_calls_avoided=api_calls_avoided,
        schema_tokens_saved=schema_savings.get(task.tool_slug, 0) if mode == "aperture_full" else 0,
        task_success=score >= 0.8 and not missing_critical,
        success_score=score,
        missing_critical_info=missing_critical,
        extra_tool_calls=0,
        raw_fallback_used=False,
        latency_ms=0,
    )


async def run_benchmark(task_set: list[BenchmarkTask], mode: str) -> BenchmarkRunResult:
    """Run tasks in selected mode and collect metrics."""

    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported benchmark mode: {mode}")
    store = InMemoryCacheStore()
    schema_savings = _schema_savings_by_tool() if mode == "aperture_full" else {}
    metrics = [await _run_task(task, mode, store, schema_savings) for task in task_set]
    return BenchmarkRunResult(mode=mode, metrics=metrics)


def run_benchmarks_from_path(path: Path, modes: list[str]) -> list[BenchmarkRunResult]:
    """Load tasks and run all selected benchmark modes."""

    tasks = load_tasks(path)
    return [asyncio.run(run_benchmark(tasks, mode)) for mode in modes]
