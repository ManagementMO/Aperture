"""Benchmark harness: Aperture vs vanilla Composio.

Measures the metrics that matter for production agents:
- Token efficiency (raw vs compressed)
- Latency (execution time)
- Context window pressure (cumulative tokens)
- Estimated cost (based on token pricing)
- Cache effectiveness (hit rate, API calls avoided)
- Quality preservation (critical fields retained)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from aperture.cache.interceptor import CachedExecutor
from aperture.cache.policy import is_cacheable
from aperture.compression.engine import compress_tool_output
from aperture.contracts import ApertureRunConfig
from aperture.demo.scenarios import SCENARIOS, get_mock_result
from aperture.routing.effort_modes import get_effort_config
from aperture.routing.intelligent_effort import select_effort
from aperture.schema_optimizer.auto_profile import ProfileRegistry
from aperture.tokenization import count_tokens
from aperture.tokenization.budget_manager import ContextBudgetManager


# OpenAI pricing per 1M tokens (as of 2024)
_TOKEN_COST = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


@dataclass
class ToolBenchmark:
    """Benchmark result for a single tool call."""

    tool_slug: str
    arguments: dict

    # Vanilla Composio
    vanilla_tokens: int = 0
    vanilla_latency_ms: float = 0.0

    # Aperture
    aperture_tokens: int = 0
    aperture_latency_ms: float = 0.0
    compression_ratio: float = 1.0
    tokens_saved: int = 0
    strategy: str = ""
    cache_status: str = "miss"
    effort_mode: str = ""

    # Quality
    critical_fields_retained: int = 0
    critical_fields_total: int = 0
    quality_score: float = 1.0

    # Cost
    vanilla_cost_cents: float = 0.0
    aperture_cost_cents: float = 0.0
    cost_savings_cents: float = 0.0


@dataclass
class ScenarioBenchmark:
    """Benchmark result for a full scenario (multi-step workflow)."""

    scenario_name: str
    mode: str
    tool_results: list[ToolBenchmark] = field(default_factory=list)

    # Aggregates
    total_vanilla_tokens: int = 0
    total_aperture_tokens: int = 0
    total_tokens_saved: int = 0
    total_vanilla_latency_ms: float = 0.0
    total_aperture_latency_ms: float = 0.0
    total_vanilla_cost_cents: float = 0.0
    total_aperture_cost_cents: float = 0.0
    total_cost_savings_cents: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_quality_score: float = 1.0
    context_window_vanilla: int = 0
    context_window_aperture: int = 0

    def __post_init__(self):
        self.total_vanilla_tokens = sum(t.vanilla_tokens for t in self.tool_results)
        self.total_aperture_tokens = sum(t.aperture_tokens for t in self.tool_results)
        self.total_tokens_saved = sum(t.tokens_saved for t in self.tool_results)
        self.total_vanilla_latency_ms = sum(t.vanilla_latency_ms for t in self.tool_results)
        self.total_aperture_latency_ms = sum(t.aperture_latency_ms for t in self.tool_results)
        self.total_vanilla_cost_cents = sum(t.vanilla_cost_cents for t in self.tool_results)
        self.total_aperture_cost_cents = sum(t.aperture_cost_cents for t in self.tool_results)
        self.total_cost_savings_cents = sum(t.cost_savings_cents for t in self.tool_results)
        self.cache_hits = sum(1 for t in self.tool_results if t.cache_status == "hit")
        self.cache_misses = sum(1 for t in self.tool_results if t.cache_status == "miss")
        quality_scores = [t.quality_score for t in self.tool_results if t.quality_score > 0]
        self.avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 1.0


def _estimate_cost(tokens: int, model: str = "gpt-4o", is_input: bool = True) -> float:
    """Estimate API cost in cents for a given token count."""
    pricing = _TOKEN_COST.get(model, _TOKEN_COST["gpt-4o"])
    rate = pricing["input"] if is_input else pricing["output"]
    return (tokens / 1_000_000) * rate * 100  # Convert to cents


def _compute_quality(
    raw_payload: object,
    compressed_payload: object,
    tool_slug: str,
) -> tuple[int, int, float]:
    """Compute quality score with deterministic semantic probes when available."""
    try:
        from aperture.benchmarks.vanilla_vs_aperture import _QUALITY_PROBES

        probe = _QUALITY_PROBES.get(tool_slug)
        if probe is not None:
            checks = probe(raw_payload, compressed_payload)
            if checks:
                retained = sum(1 for passed in checks.values() if passed)
                total = len(checks)
                return retained, total, retained / total
    except Exception:
        pass

    # Fallback for tools that do not yet have a semantic quality probe.
    from aperture.schema_optimizer.auto_profile import generate_tool_profile

    try:
        profile = generate_tool_profile(tool_slug, raw_payload)
        critical = set(profile.critical_fields)

        if not critical:
            return 0, 0, 1.0

        # Check which critical fields are present in compressed payload
        if isinstance(compressed_payload, dict):
            retained = sum(1 for f in critical if f in str(compressed_payload))
        else:
            retained = len(critical)  # Assume all retained if not dict

        score = retained / len(critical)
        return retained, len(critical), score
    except Exception:
        return 0, 0, 1.0


def benchmark_tool(
    tool_slug: str,
    arguments: dict,
    mode: str = "medium",
    model: str = "gpt-4o",
    enable_cache: bool = True,
    user_query: str | None = None,
) -> ToolBenchmark:
    """Benchmark a single tool call: vanilla vs Aperture."""
    raw_payload = get_mock_result(tool_slug, arguments)

    # Vanilla Composio
    t0 = time.perf_counter()
    vanilla_tokens = count_tokens(raw_payload).tokens
    vanilla_latency = (time.perf_counter() - t0) * 1000

    # Aperture
    config = ApertureRunConfig(
        run_id=f"bench-{tool_slug}",
        model=model,
        effort_mode=mode,
        cache_bypass=not enable_cache,
    )

    t0 = time.perf_counter()

    # Determine compression mode
    if mode == "auto":
        decision = select_effort(
            tool_slug=tool_slug,
            arguments=arguments,
            user_query=user_query or "",
        )
        compression_mode = decision.compression_mode
    else:
        effort = get_effort_config(mode)
        compression_mode = effort.compression_mode

    if mode != "auto":
        cache_bypass = not enable_cache or not effort.cache_reads
        config = ApertureRunConfig(
            run_id=f"bench-{tool_slug}",
            model=model,
            effort_mode=mode,
            cache_bypass=cache_bypass,
            connected_account_id="bench_account",
        )
    else:
        config = ApertureRunConfig(
            run_id=f"bench-{tool_slug}",
            model=model,
            effort_mode=mode,
            cache_bypass=not enable_cache,
            connected_account_id="bench_account",
        )

    # Execute with cache
    cache = CachedExecutor()

    def executor():
        return raw_payload

    _, cache_event = cache.execute(
        tool_slug=tool_slug,
        arguments=arguments,
        executor=executor,
        config=config,
    )

    compressed = compress_tool_output(
        raw_payload=raw_payload,
        tool_slug=tool_slug,
        mode=compression_mode,
        model=model,
    )

    aperture_tokens = compressed.compressed_tokens
    aperture_latency = (time.perf_counter() - t0) * 1000

    # Quality
    retained, total, quality = _compute_quality(raw_payload, compressed.compressed_payload, tool_slug)

    # Cost
    vanilla_cost = _estimate_cost(vanilla_tokens, model)
    aperture_cost = _estimate_cost(aperture_tokens, model)

    return ToolBenchmark(
        tool_slug=tool_slug,
        arguments=arguments,
        vanilla_tokens=vanilla_tokens,
        vanilla_latency_ms=vanilla_latency,
        aperture_tokens=aperture_tokens,
        aperture_latency_ms=aperture_latency,
        compression_ratio=compressed.compression_ratio,
        tokens_saved=compressed.tokens_saved,
        strategy=compressed.strategy,
        cache_status=cache_event.cache_status,
        effort_mode=mode if mode != "auto" else (decision.effort_mode if mode == "auto" else mode),
        critical_fields_retained=retained,
        critical_fields_total=total,
        quality_score=quality,
        vanilla_cost_cents=vanilla_cost,
        aperture_cost_cents=aperture_cost,
        cost_savings_cents=vanilla_cost - aperture_cost,
    )


def benchmark_scenario(
    scenario_name: str,
    mode: str = "medium",
    model: str = "gpt-4o",
    enable_cache: bool = True,
) -> ScenarioBenchmark:
    """Benchmark a full scenario workflow."""
    scenario = SCENARIOS[scenario_name]

    # Clear cache for fresh benchmark
    if enable_cache:
        try:
            from upstash_redis import Redis
            from aperture.config import Config
            r = Redis(url=Config.UPSTASH_REDIS_REST_URL, token=Config.UPSTASH_REDIS_REST_TOKEN)
            for k in r.keys("aperture:cache:*"):
                r.delete(k)
        except Exception:
            pass

    tool_results = []
    vanilla_context: list[dict] = []
    aperture_context: list[dict] = []

    for step in scenario.steps:
        result = benchmark_tool(
            tool_slug=step.tool_slug,
            arguments=step.arguments,
            mode=mode,
            model=model,
            enable_cache=enable_cache,
            user_query=scenario.user_query,
        )
        tool_results.append(result)

        # Track context window growth
        raw_payload = get_mock_result(step.tool_slug, step.arguments)
        vanilla_context.append({"tool": step.tool_slug, "result": raw_payload})

        compressed_payload = compress_tool_output(
            raw_payload=raw_payload,
            tool_slug=step.tool_slug,
            mode=get_effort_config(mode).compression_mode if mode != "auto" else "balanced",
            model=model,
        ).compressed_payload
        aperture_context.append({"tool": step.tool_slug, "result": compressed_payload})

    benchmark = ScenarioBenchmark(
        scenario_name=scenario_name,
        mode=mode,
        tool_results=tool_results,
    )
    benchmark.context_window_vanilla = count_tokens(vanilla_context).tokens
    benchmark.context_window_aperture = count_tokens(aperture_context).tokens

    return benchmark


def run_full_benchmark(
    modes: list[str] | None = None,
    scenarios: list[str] | None = None,
) -> dict[str, list[ScenarioBenchmark]]:
    """Run benchmarks across all scenarios and modes.

    Returns:
        Dict mapping mode -> list of scenario benchmarks
    """
    modes = modes or ["off", "low", "medium", "high", "auto"]
    scenarios = scenarios or list(SCENARIOS.keys())

    results: dict[str, list[ScenarioBenchmark]] = {}

    for mode in modes:
        results[mode] = []
        for scenario_name in scenarios:
            bench = benchmark_scenario(scenario_name, mode=mode)
            results[mode].append(bench)

    return results
