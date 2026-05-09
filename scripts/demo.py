#!/usr/bin/env python3
"""CLI demo script for Aperture — agent workflow scenarios.

Usage:
    uv run python scripts/demo.py --scenario research_project --mode medium
    uv run python scripts/demo.py --scenario triage_bugs --mode medium --cache
    uv run python scripts/demo.py --scenario research_project --compare
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
from rich.tree import Tree

from aperture.config import Config
from aperture.demo.agent_simulator import (
    run_workflow_with_aperture,
    run_workflow_without_aperture,
)
from aperture.demo.scenarios import SCENARIOS

console = Console()


def run_comparative_demo(scenario_name: str, mode: str = "medium", enable_cache: bool = True):
    """Run the same agent workflow with and without Aperture, side by side."""
    scenario = SCENARIOS[scenario_name]

    console.print()
    console.print(Panel(
        f"[bold blue]Aperture Agent Demo[/bold blue]\n"
        f"[dim]{scenario.description}[/dim]\n"
        f"Steps: {len(scenario.steps)} tool calls",
        title=f"Scenario: {scenario_name}",
        border_style="blue",
    ))

    # Without Aperture
    console.print("\n[bold red]❌ WITHOUT Aperture[/bold red] — raw Composio outputs")
    raw = run_workflow_without_aperture(scenario_name)
    _print_workflow(raw, color="red")

    # With Aperture
    mode_label = f"[auto]" if mode == "auto" else mode
    console.print(f"\n[bold green]✅ WITH Aperture[/bold green] — mode={mode_label}, cache={'on' if enable_cache else 'off'}")
    opt = run_workflow_with_aperture(scenario_name, mode=mode, enable_cache=enable_cache, user_query=scenario.user_query)
    _print_workflow(opt, color="green")

    # Show auto reasoning
    if mode == "auto":
        console.print("\n[dim]🧠 Auto Effort Decisions:[/dim]")
        for i, step in enumerate(opt.steps):
            if len(step.strategy) > 10:  # It's a reasoning string, not just a strategy name
                console.print(f"  Step {i+1}: {step.strategy}")

    # Summary comparison
    console.print("\n[bold]📊 Side-by-Side Summary[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Without Aperture", style="red")
    table.add_column("With Aperture", style="green")
    table.add_column("Improvement", style="cyan")

    raw_total = raw.total_raw_tokens
    opt_total = opt.total_compressed_tokens
    saved = raw_total - opt_total
    ratio = saved / raw_total if raw_total > 0 else 0

    table.add_row("Total Tokens", f"{raw_total:,}", f"{opt_total:,}", f"-{saved:,} ({ratio:.1%})")
    table.add_row("Context Window", f"{raw.context_window_used:,}", f"{opt.context_window_used:,}", f"-{raw.context_window_used - opt.context_window_used:,}")
    table.add_row("Cache Hits", "0", f"{opt.cache_hits}", f"{opt.api_calls_avoided} API calls avoided")
    table.add_row("Avg Compression", "0%", f"{ratio:.1%}", "—")

    console.print(table)

    # Per-step breakdown
    console.print("\n[bold]🔍 Per-Step Breakdown[/bold]")
    step_table = Table(show_header=True, header_style="bold")
    step_table.add_column("Step")
    step_table.add_column("Tool")
    step_table.add_column("Raw")
    step_table.add_column("Compressed")
    step_table.add_column("Saved")
    step_table.add_column("Cache")
    step_table.add_column("Strategy")

    for i, step in enumerate(opt.steps):
        step_table.add_row(
            str(i + 1),
            step.tool_slug.replace("GITHUB_", "").replace("GMAIL_", "").replace("SLACK_", ""),
            f"{step.raw_tokens:,}",
            f"{step.compressed_tokens:,}",
            f"{step.tokens_saved:,}",
            step.cache_status,
            step.strategy,
        )

    console.print(step_table)

    # Show context window pressure visually
    console.print("\n[bold]🌊 Context Window Pressure[/bold]")
    _print_context_bar(raw.context_window_used, opt.context_window_used)

    # If cached, run again to show cache hit
    if enable_cache and opt.cache_misses > 0:
        console.print("\n[yellow]Running again to test cache...[/yellow]")
        opt2 = run_workflow_with_aperture(scenario_name, mode=mode, enable_cache=True)
        if opt2.cache_hits > 0:
            console.print(f"[green]✅ {opt2.cache_hits}/{len(opt2.steps)} steps served from cache — zero API calls![/green]")
        else:
            console.print("[red]✗ Cache miss[/red]")


def _print_workflow(result, color: str = "white"):
    """Print a workflow result."""
    for i, step in enumerate(result.steps):
        icon = "🔄" if step.cache_status == "hit" else "📡"
        strategy_text = step.strategy
        # Truncate long reasoning strings
        if len(strategy_text) > 60:
            strategy_text = strategy_text[:57] + "..."
        console.print(
            f"  {icon} Step {i+1}: [bold]{step.tool_slug}[/bold] → "
            f"{step.raw_tokens:,} raw → {step.compressed_tokens:,} compressed "
            f"([{color}]{strategy_text}[/{color}], cache={step.cache_status})"
        )
    console.print(f"  Total: [{color}]{result.total_raw_tokens:,}[/{color}] tokens")


def _print_context_bar(raw_total: int, opt_total: int, max_context: int = 128_000):
    """Print a visual context window bar."""
    bar_width = 50
    raw_pct = min(raw_total / max_context, 1.0)
    opt_pct = min(opt_total / max_context, 1.0)

    raw_bars = int(bar_width * raw_pct)
    opt_bars = int(bar_width * opt_pct)

    raw_bar = "█" * raw_bars + "░" * (bar_width - raw_bars)
    opt_bar = "█" * opt_bars + "░" * (bar_width - opt_bars)

    console.print(f"  Without Aperture: [{raw_pct*100:5.1f}%] {raw_bar} {raw_total:,} / {max_context:,}")
    console.print(f"  With Aperture:    [{opt_pct*100:5.1f}%] {opt_bar} {opt_total:,} / {max_context:,}")

    if raw_pct > 0.5:
        console.print("  [red]⚠️ Without Aperture, you're using >50% of your context window![/red]")
    if opt_pct < 0.1:
        console.print("  [green]✅ With Aperture, context pressure is minimal.[/green]")


def main():
    parser = argparse.ArgumentParser(description="Aperture Agent Workflow Demo")
    parser.add_argument("--scenario", default="research_project", choices=list(SCENARIOS.keys()))
    parser.add_argument("--mode", default="medium", choices=["off", "low", "medium", "high", "auto"])
    parser.add_argument("--cache", action="store_true", help="Enable caching")
    parser.add_argument("--compare", action="store_true", help="Show with/without Aperture comparison")
    args = parser.parse_args()

    run_comparative_demo(args.scenario, mode=args.mode, enable_cache=args.cache)


if __name__ == "__main__":
    main()
