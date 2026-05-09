#!/usr/bin/env python3
"""Benchmark script — Aperture vs vanilla Composio.

Usage:
    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --scenario research_project
    uv run python scripts/benchmark.py --mode auto --scenario triage_bugs
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aperture.benchmarks.harness import benchmark_scenario, run_full_benchmark
from aperture.demo.scenarios import SCENARIOS

console = Console()


def print_tool_breakdown(bench):
    """Print per-tool benchmark results."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Tool")
    table.add_column("Vanilla Tokens", justify="right")
    table.add_column("Aperture Tokens", justify="right")
    table.add_column("Saved", justify="right")
    table.add_column("Ratio", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Cache", justify="center")
    table.add_column("Quality", justify="right")
    table.add_column("Cost ¢", justify="right")

    for tool in bench.tool_results:
        table.add_row(
            tool.tool_slug.replace("GITHUB_", "").replace("GMAIL_", "").replace("SLACK_", ""),
            f"{tool.vanilla_tokens:,}",
            f"{tool.aperture_tokens:,}",
            f"{tool.tokens_saved:,}",
            f"{tool.compression_ratio:.1%}",
            f"{tool.aperture_latency_ms:.1f}ms",
            tool.cache_status,
            f"{tool.quality_score:.0%}",
            f"{tool.aperture_cost_cents:.4f}¢",
        )

    console.print(table)


def print_scenario_summary(bench):
    """Print scenario-level summary."""
    saved = bench.total_tokens_saved
    ratio = saved / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0
    cost_saved = bench.total_cost_savings_cents

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Vanilla", style="red")
    table.add_column("Aperture", style="green")
    table.add_column("Improvement", style="cyan")

    table.add_row("Total Tokens", f"{bench.total_vanilla_tokens:,}", f"{bench.total_aperture_tokens:,}", f"-{saved:,} ({ratio:.1%})")
    table.add_row("Context Window", f"{bench.context_window_vanilla:,}", f"{bench.context_window_aperture:,}", f"-{bench.context_window_vanilla - bench.context_window_aperture:,}")
    table.add_row("Latency", f"{bench.total_vanilla_latency_ms:.1f}ms", f"{bench.total_aperture_latency_ms:.1f}ms", f"{bench.total_aperture_latency_ms - bench.total_vanilla_latency_ms:+.1f}ms")
    table.add_row("Cost", f"{bench.total_vanilla_cost_cents:.4f}¢", f"{bench.total_aperture_cost_cents:.4f}¢", f"-{cost_saved:.4f}¢ ({cost_saved/bench.total_vanilla_cost_cents:.1%})" if bench.total_vanilla_cost_cents > 0 else "—")
    table.add_row("Cache Hits", "0", f"{bench.cache_hits}/{bench.cache_hits + bench.cache_misses}", f"{bench.cache_hits} API calls avoided")
    table.add_row("Quality Score", "100%", f"{bench.avg_quality_score:.0%}", f"{-100 + bench.avg_quality_score * 100:.0f}pp" if bench.avg_quality_score < 1.0 else "Perfect")

    console.print(table)


def print_comparison_matrix(results):
    """Print a matrix comparing all modes across all scenarios."""
    console.print("\n[bold]📊 Mode Comparison Matrix[/bold]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Scenario")
    for mode in results:
        table.add_column(f"Mode: {mode}", justify="right")

    scenarios = list(SCENARIOS.keys())
    for scenario in scenarios:
        row = [scenario.replace("_", " ").title()]
        for mode in results:
            bench = next((b for b in results[mode] if b.scenario_name == scenario), None)
            if bench:
                saved = bench.total_tokens_saved
                ratio = saved / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0
                row.append(f"{ratio:.1%} ({bench.total_aperture_tokens:,})")
            else:
                row.append("—")
        table.add_row(*row)

    console.print(table)


def run_single_scenario(scenario_name: str, mode: str):
    """Benchmark a single scenario."""
    console.print(Panel(
        f"[bold blue]Benchmark: {scenario_name.replace('_', ' ').title()}[/bold blue]\n"
        f"Mode: {mode}",
        border_style="blue",
    ))

    bench = benchmark_scenario(scenario_name, mode=mode)

    console.print(f"\n[bold]🔍 Per-Tool Breakdown[/bold]")
    print_tool_breakdown(bench)

    console.print(f"\n[bold]📈 Scenario Summary[/bold]")
    print_scenario_summary(bench)


def run_all_benchmarks():
    """Run full benchmark suite."""
    console.print(Panel(
        "[bold blue]Aperture Full Benchmark Suite[/bold blue]\n"
        "Comparing Aperture modes against vanilla Composio",
        border_style="blue",
    ))

    modes = ["off", "low", "medium", "high", "auto"]
    scenarios = list(SCENARIOS.keys())

    console.print(f"\n[dim]Running {len(modes)} modes × {len(scenarios)} scenarios = {len(modes) * len(scenarios)} benchmarks...[/dim]\n")

    results = run_full_benchmark(modes=modes, scenarios=scenarios)

    # Print each scenario across modes
    for scenario in scenarios:
        console.print(f"\n[bold]📁 Scenario: {scenario.replace('_', ' ').title()}[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Mode")
        table.add_column("Raw Tokens", justify="right")
        table.add_column("Compressed", justify="right")
        table.add_column("Saved", justify="right")
        table.add_column("Savings", justify="right")
        table.add_column("Context Window", justify="right")
        table.add_column("Cache Hits", justify="right")
        table.add_column("Quality", justify="right")

        for mode in modes:
            bench = next(b for b in results[mode] if b.scenario_name == scenario)
            saved = bench.total_tokens_saved
            ratio = saved / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0

            if mode == "off":
                style = "red"
            elif mode == "auto":
                style = "bold green"
            else:
                style = "green"

            table.add_row(
                mode,
                f"{bench.total_vanilla_tokens:,}",
                f"{bench.total_aperture_tokens:,}",
                f"{saved:,}",
                f"{ratio:.1%}",
                f"{bench.context_window_aperture:,}",
                f"{bench.cache_hits}",
                f"{bench.avg_quality_score:.0%}",
                style=style,
            )

        console.print(table)

    # Comparison matrix
    print_comparison_matrix(results)

    # Overall summary
    console.print("\n[bold]🏆 Overall Winners[/bold]")

    for scenario in scenarios:
        best_mode = None
        best_savings = -1
        for mode in modes:
            if mode == "off":
                continue
            bench = next(b for b in results[mode] if b.scenario_name == scenario)
            saved = bench.total_tokens_saved
            if saved > best_savings:
                best_savings = saved
                best_mode = mode

        bench = next(b for b in results[best_mode] if b.scenario_name == scenario)
        ratio = best_savings / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0
        console.print(f"  {scenario.replace('_', ' ').title()}: [bold green]{best_mode}[/bold green] with {ratio:.1%} savings ({best_savings:,} tokens)")


def main():
    parser = argparse.ArgumentParser(description="Aperture Benchmark Suite")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), help="Benchmark a specific scenario")
    parser.add_argument("--mode", default="medium", choices=["off", "low", "medium", "high", "auto"], help="Aperture mode")
    parser.add_argument("--all", action="store_true", help="Run full benchmark suite")
    args = parser.parse_args()

    if args.all:
        run_all_benchmarks()
    elif args.scenario:
        run_single_scenario(args.scenario, args.mode)
    else:
        # Default: run full suite
        run_all_benchmarks()


if __name__ == "__main__":
    main()
