"""Agent simulator that runs multi-step scenarios with/without Aperture.

Shows context window pressure, token savings, and cache hits across an
entire agent workflow — not just a single tool call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aperture.cache.interceptor import CachedExecutor
from aperture.cache.policy import is_cacheable
from aperture.compression.engine import compress_tool_output
from aperture.contracts import ApertureRunConfig, CompressionResult, ToolCall
from aperture.demo.scenarios import get_mock_result
from aperture.routing.effort_modes import get_effort_config
from aperture.tokenization import count_tokens


@dataclass
class StepResult:
    """Result of a single step in the agent workflow."""

    tool_slug: str
    arguments: dict
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    strategy: str
    cache_status: str
    omitted_fields: list[str] = field(default_factory=list)
    raw_result_preview: str = ""
    compressed_result_preview: str = ""


@dataclass
class WorkflowResult:
    """Aggregated result of an entire agent workflow."""

    scenario_name: str
    mode: str
    steps: list[StepResult]
    total_raw_tokens: int = 0
    total_compressed_tokens: int = 0
    total_tokens_saved: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls_avoided: int = 0
    context_window_used: int = 0

    def __post_init__(self):
        self.total_raw_tokens = sum(s.raw_tokens for s in self.steps)
        self.total_compressed_tokens = sum(s.compressed_tokens for s in self.steps)
        self.total_tokens_saved = sum(s.tokens_saved for s in self.steps)
        self.cache_hits = sum(1 for s in self.steps if s.cache_status == "hit")
        self.cache_misses = sum(1 for s in self.steps if s.cache_status == "miss")
        self.api_calls_avoided = self.cache_hits
        # Context window = cumulative raw tokens (what the agent would see without Aperture)
        self.context_window_used = self.total_raw_tokens


def _make_executor(tool_slug: str, arguments: dict):
    """Return a no-arg executor that returns mock data."""

    def execute():
        return get_mock_result(tool_slug, arguments)

    return execute


def run_workflow_without_aperture(scenario_name: str) -> WorkflowResult:
    """Simulate an agent workflow WITHOUT Aperture — raw Composio outputs."""
    from aperture.demo.scenarios import get_scenario

    scenario = get_scenario(scenario_name)
    steps: list[StepResult] = []
    cumulative_context: list[dict] = []

    for call in scenario.steps:
        executor = _make_executor(call.tool_slug, call.arguments)
        raw_result = executor()
        raw_tokens = count_tokens(raw_result).tokens

        # Without Aperture, the agent sees the FULL raw result
        cumulative_context.append({"tool": call.tool_slug, "result": raw_result})
        context_tokens = count_tokens(cumulative_context).tokens

        steps.append(
            StepResult(
                tool_slug=call.tool_slug,
                arguments=call.arguments,
                raw_tokens=raw_tokens,
                compressed_tokens=raw_tokens,
                tokens_saved=0,
                compression_ratio=1.0,
                strategy="off",
                cache_status="bypass",
                raw_result_preview=f"{type(raw_result).__name__} ({raw_tokens:,} tokens)",
            )
        )

    result = WorkflowResult(
        scenario_name=scenario_name,
        mode="off",
        steps=steps,
    )
    result.context_window_used = count_tokens(cumulative_context).tokens
    return result


def run_workflow_with_aperture(
    scenario_name: str,
    mode: str = "medium",
    enable_cache: bool = True,
    user_query: str | None = None,
) -> WorkflowResult:
    """Simulate an agent workflow WITH Aperture — compressed + cached outputs.

    Supports 'auto' mode for intelligent effort allocation.
    """
    from aperture.demo.scenarios import get_scenario
    from aperture.routing.intelligent_effort import select_effort

    scenario = get_scenario(scenario_name)
    cache = CachedExecutor()
    config = ApertureRunConfig(
        run_id=f"sim-{scenario_name}-{mode}",
        model="gpt-4o",
        effort_mode=mode,
        cache_bypass=not enable_cache,
    )

    steps: list[StepResult] = []
    cumulative_context: list[dict] = []
    context_used = 0

    for call in scenario.steps:
        executor = _make_executor(call.tool_slug, call.arguments)

        # Determine compression mode
        if mode == "auto":
            decision = select_effort(
                tool_slug=call.tool_slug,
                arguments=call.arguments,
                user_query=user_query or scenario.description,
                context_used=context_used,
            )
            compression_mode = decision.compression_mode
        else:
            effort = get_effort_config(mode)
            compression_mode = effort.compression_mode
            decision = None

        # Execute with cache
        raw_result, cache_event = cache.execute(
            tool_slug=call.tool_slug,
            arguments=call.arguments,
            executor=executor,
            config=config,
        )

        # Compress result
        if cache_event.cache_status == "hit":
            compressed = CompressionResult(
                compressed_payload=raw_result,
                raw_tokens=0,
                compressed_tokens=0,
                tokens_saved=0,
                compression_ratio=1.0,
                strategy="cache_hit",
            )
        else:
            compressed = compress_tool_output(
                raw_payload=raw_result,
                tool_slug=call.tool_slug,
                mode=compression_mode,
                model=config.model,
            )

        # Build cumulative context with COMPRESSED results
        cumulative_context.append({"tool": call.tool_slug, "result": compressed.compressed_payload})
        context_tokens = count_tokens(cumulative_context).tokens
        context_used = context_tokens

        steps.append(
            StepResult(
                tool_slug=call.tool_slug,
                arguments=call.arguments,
                raw_tokens=compressed.raw_tokens,
                compressed_tokens=compressed.compressed_tokens,
                tokens_saved=compressed.tokens_saved,
                compression_ratio=compressed.compression_ratio,
                strategy=decision.reasoning if decision else compressed.strategy,
                cache_status=cache_event.cache_status,
                omitted_fields=compressed.omitted_fields,
                raw_result_preview=f"{type(raw_result).__name__} ({compressed.raw_tokens:,} tokens)",
                compressed_result_preview=f"{type(compressed.compressed_payload).__name__} ({compressed.compressed_tokens:,} tokens)",
            )
        )

    result = WorkflowResult(
        scenario_name=scenario_name,
        mode=mode,
        steps=steps,
    )
    result.context_window_used = context_tokens
    return result
