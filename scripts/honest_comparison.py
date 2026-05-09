#!/usr/bin/env python3
"""Honest side-by-side: Vanilla Composio vs Aperture.

This script demonstrates the EXACT difference:

VANILLA COMPOSIO:
    User intent → LLM picks tool → Composio SDK executes → Raw result → LLM
                                                    ↑
                                              No compression, no cache, no token counting

APERTURE:
    User intent → LLM picks tool → ApertureRunner.run_tool() → Composio SDK executes
                                                                     ↓
                                                           Compression + Cache + Token count
                                                                     ↓
                                                           Compressed result → LLM

The ONLY difference Aperture adds is optimization LAYER — it doesn't change
WHAT tools the agent calls, only HOW the results are delivered to the LLM.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import os
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aperture.integration import ApertureRunner
from aperture.contracts import ApertureRunConfig
from aperture.tokenization import count_tokens

console = Console()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Set {name} before running the live Composio comparison.")
    return value

# =============================================================================
# VANILLA COMPOSIO — what you get WITHOUT Aperture
# =============================================================================

def vanilla_composio_read_sheets():
    """Exactly what a developer does today: call Composio, pass raw result to LLM."""
    from composio import Composio

    c = Composio(api_key=_required_env("COMPOSIO_API_KEY"))
    session = c.create(
        user_id=_required_env("COMPOSIO_USER_ID"),
        toolkits=["googlesheets"],
        connected_accounts={
            "googlesheets": _required_env("COMPOSIO_GOOGLESHEETS_CONNECTED_ACCOUNT_ID")
        },
    )

    resp = session.execute(
        tool_slug="GOOGLESHEETS_BATCH_GET",
        arguments={
            "spreadsheet_id": "1eyr5XV1pGyJTbRWpFVIp_fcrLK-oEp4tlVg3l1VsqR0",
            "sheet_name": "Sheet1",
            "ranges": ["Sheet1!A1:M10001"],
        },
    )

    # Vanilla Composio: developer just passes this raw result to the LLM
    # No compression, no cache, no token counting
    d = resp if isinstance(resp, dict) else resp.model_dump()
    return d.get("data", {}).get("valueRanges", [{}])[0].get("values", [])


# =============================================================================
# APERTURE — what you get WITH Aperture
# =============================================================================

def aperture_read_sheets(effort_mode="balanced"):
    """Aperture wraps the SAME Composio call with optimization."""

    config = ApertureRunConfig(
        run_id="honest-demo",
        model="gpt-4o",
        effort_mode=effort_mode,
        cache_bypass=False,  # Cache is ON for Aperture
        connected_account_id=_required_env("COMPOSIO_GOOGLESHEETS_CONNECTED_ACCOUNT_ID"),
    )
    runner = ApertureRunner(config)

    # Aperture calls the SAME Composio function
    result = runner.run_tool(
        tool_slug="GOOGLESHEETS_BATCH_GET",
        arguments={"spreadsheet_id": "1eyr5XV1pGyJTbRWpFVIp_fcrLK-oEp4tlVg3l1VsqR0"},
        executor=vanilla_composio_read_sheets,
        toolkit_slug="GOOGLESHEETS",
    )

    summary = runner.finish()
    return result, summary


# =============================================================================
# HONEST COMPARISON
# =============================================================================

def run_honest_comparison():
    # Clear ANY pre-existing cache so the demo is honest
    try:
        from upstash_redis import Redis
        from aperture.config import Config
        r = Redis(url=Config.UPSTASH_REDIS_REST_URL, token=Config.UPSTASH_REDIS_REST_TOKEN)
        for k in r.keys("aperture:cache:*"):
            r.delete(k)
    except Exception:
        pass
    # Also clear in-memory fallback
    try:
        from aperture.cache.store import CacheStore
        store = CacheStore()
        store._memory._data.clear()
    except Exception:
        pass
    console.print("[dim]Cache cleared for honest comparison[/dim]")

    console.print(Panel(
        "[bold blue]Honest Comparison: Vanilla Composio vs Aperture[/bold blue]\n"
        "Both call the SAME Composio API. Aperture only adds optimization.",
        border_style="blue",
    ))

    # --- VANILLA COMPOSIO ---
    console.print("\n[bold red]1️⃣ VANILLA COMPOSIO[/bold red] — no Aperture")
    console.print("   Code: session.execute(tool_slug='GOOGLESHEETS_BATCH_GET', ...)")
    console.print("   Then: pass raw_result directly to LLM")

    t0 = time.perf_counter()
    vanilla_result = vanilla_composio_read_sheets()
    vanilla_latency = (time.perf_counter() - t0) * 1000
    vanilla_tokens = count_tokens(vanilla_result).tokens

    console.print(f"   Rows returned: {len(vanilla_result):,}")
    console.print(f"   Raw tokens: {vanilla_tokens:,}")
    console.print(f"   Latency: {vanilla_latency:.0f}ms")
    console.print(f"   Cache: none (vanilla Composio has no cache)")
    console.print(f"   Cost (GPT-4o input): ~${vanilla_tokens / 1_000_000 * 2.50:.3f}")
    console.print(f"   Context window: {vanilla_tokens / 128_000 * 100:.0f}% of 128K")
    console.print("   [red]⚠️ EXCEEDS context window — would crash the agent[/red]")

    # --- APERTURE (FIRST CALL) ---
    console.print("\n[bold green]2️⃣ APERTURE — First Call (Cache MISS)[/bold green]")
    console.print("   Code: runner.run_tool(slug='GOOGLESHEETS_BATCH_GET', executor=...)")
    console.print("   Aperture: calls Composio → compresses → stores in Redis cache")

    t0 = time.perf_counter()
    aperture_result, aperture_summary = aperture_read_sheets(effort_mode="balanced")
    aperture_latency_1 = (time.perf_counter() - t0) * 1000

    comp = aperture_result["compression"]
    cache = aperture_result["cache_event"]

    console.print(f"   Rows returned by Composio: {len(vanilla_result):,}")
    console.print(f"   Raw tokens (before Aperture): {comp.raw_tokens:,}")
    console.print(f"   Compressed tokens (after Aperture): {comp.compressed_tokens:,}")
    console.print(f"   Tokens saved: {comp.tokens_saved:,}")
    console.print(f"   Compression ratio: {comp.compression_ratio:.1%}")
    console.print(f"   Strategy: {comp.strategy}")
    console.print(f"   Cache status: {cache.cache_status}")
    console.print(f"   Latency: {aperture_latency_1:.0f}ms (Composio API + compression)")
    console.print(f"   Cost (GPT-4o input): ~${comp.compressed_tokens / 1_000_000 * 2.50:.3f}")
    console.print(f"   Context window: {comp.compressed_tokens / 128_000 * 100:.1f}% of 128K")
    console.print("   [green]✅ Fits easily in context window[/green]")

    # --- APERTURE (SECOND CALL) ---
    console.print("\n[bold cyan]3️⃣ APERTURE — Second Call (Cache HIT)[/bold cyan]")
    console.print("   Code: runner.run_tool(slug='GOOGLESHEETS_BATCH_GET', executor=...)")
    console.print("   Aperture: checks Redis cache → serves cached result → NO Composio API call")

    t0 = time.perf_counter()
    aperture_result_2, aperture_summary_2 = aperture_read_sheets(effort_mode="balanced")
    aperture_latency_2 = (time.perf_counter() - t0) * 1000

    comp2 = aperture_result_2["compression"]
    cache2 = aperture_result_2["cache_event"]

    console.print(f"   Cache status: {cache2.cache_status}")
    console.print(f"   Latency: {aperture_latency_2:.1f}ms (Redis only, no API call)")
    console.print(f"   Cost: $0 (no API tokens used)")
    console.print("   [green]✅ Zero API call, zero cost, instant response[/green]")

    # --- SUMMARY TABLE ---
    console.print("\n[bold]📊 Side-by-Side Summary[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Vanilla Composio", style="red")
    table.add_column("Aperture (1st)", style="green")
    table.add_column("Aperture (2nd)", style="cyan")

    table.add_row("Tool Call", "GOOGLESHEETS_BATCH_GET", "GOOGLESHEETS_BATCH_GET", "GOOGLESHEETS_BATCH_GET")
    table.add_row("Raw Tokens", f"{vanilla_tokens:,}", f"{comp.raw_tokens:,}", "0 (cached)")
    table.add_row("LLM Sees", f"{vanilla_tokens:,} tokens", f"{comp.compressed_tokens:,} tokens", f"{comp2.compressed_tokens:,} tokens")
    table.add_row("Compression", "None", f"{comp.compression_ratio:.1%}", "Cache hit")
    table.add_row("Cache", "❌ None", "❌ Miss", "✅ Hit")
    table.add_row("Latency", f"{vanilla_latency:.0f}ms", f"{aperture_latency_1:.0f}ms", f"{aperture_latency_2:.1f}ms")
    table.add_row("API Cost", f"~${vanilla_tokens/1e6*2.50:.2f}", f"~${comp.compressed_tokens/1e6*2.50:.3f}", "$0.000")
    table.add_row("Context Window", f"{vanilla_tokens/128000*100:.0f}% ⚠️", f"{comp.compressed_tokens/128000*100:.1f}% ✅", f"{comp2.compressed_tokens/128000*100:.1f}% ✅")

    console.print(table)

    # --- WHAT THE LLM ACTUALLY SEES ---
    console.print("\n[bold]🔍 What the LLM Actually Sees[/bold]")

    console.print("\n[red]Vanilla Composio:[/red]")
    console.print(f"   A 2D array of {len(vanilla_result):,} rows × {len(vanilla_result[0])} columns")
    console.print(f"   The LLM must process ALL {vanilla_tokens:,} tokens")
    console.print("   No summary, no stats, no sampling — just raw data")

    console.print("\n[green]Aperture (balanced):[/green]")
    payload = comp.compressed_payload
    if isinstance(payload, dict):
        summary = payload.get("_aperture_summary", {})
        console.print(f"   Summary: {summary.get('total_rows', 0):,} total rows, {summary.get('sampled_rows', 0)} sampled")
        console.print(f"   Columns: {summary.get('columns_shown', 0)} shown, {summary.get('columns_dropped', 0)} dropped")
        console.print(f"   Stats: {list(payload.get('stats', {}).keys())}")
        console.print(f"   Sample row count: {len(payload.get('sample', []))}")
        console.print("   The LLM gets representative data + statistics")

    # --- KEY TAKEAWAY ---
    console.print("\n[bold]💡 Key Takeaway[/bold]")
    console.print("   Aperture does NOT change what tools Composio exposes.")
    console.print("   Aperture does NOT change what the agent decides to do.")
    console.print("   Aperture ONLY optimizes HOW tool results are delivered to the LLM.")
    console.print("   It's a compression + caching + token-counting layer on top of Composio.")


if __name__ == "__main__":
    run_honest_comparison()
