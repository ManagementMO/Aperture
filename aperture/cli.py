"""Command line entry points for Aperture."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aperture.benchmarks.report import write_benchmark_outputs
from aperture.benchmarks.runner import run_benchmarks_from_path
from aperture.integration.live_check import live_check_from_env
from aperture.integration.composio_adapter import ComposioToolExecutor
from aperture.schema_optimizer.reports import write_schema_optimization_report


def benchmark_main() -> None:
    """Run deterministic Aperture benchmarks from JSONL tasks."""

    parser = argparse.ArgumentParser(description="Run Aperture fixture benchmarks.")
    parser.add_argument("--tasks", default="aperture/benchmarks/tasks", help="Task JSONL file or directory.")
    parser.add_argument("--out", default="reports", help="Output directory for reports.")
    parser.add_argument(
        "--modes",
        nargs="*",
        default=["raw", "aperture_compressed", "aperture_cached", "aperture_full", "shadow"],
        help="Benchmark modes to run.",
    )
    args = parser.parse_args()

    runs = run_benchmarks_from_path(Path(args.tasks), args.modes)
    write_benchmark_outputs(runs, Path(args.out))


def schema_report_main() -> None:
    """Generate schema optimization report from fixture/live schemas."""

    parser = argparse.ArgumentParser(description="Generate Aperture schema optimization report.")
    parser.add_argument("--out", default="reports/schema_optimization_report.md")
    args = parser.parse_args()
    write_schema_optimization_report(Path(args.out))


def live_check_main() -> None:
    """Run live Composio validation using environment configuration."""

    parser = argparse.ArgumentParser(description="Run live Composio validation through Aperture.")
    parser.add_argument("--out", default="reports/live_composio_check.json")
    parser.add_argument("--execute", action="store_true", help="Execute COMPOSIO_TOOL_SLUG after fetching schemas.")
    parser.add_argument("--tool-router", action="store_true", help="Also validate Composio Tool Router session/search.")
    args = parser.parse_args()
    try:
        if args.tool_router:
            import os

            os.environ["COMPOSIO_USE_TOOL_ROUTER"] = "true"
        result = live_check_from_env(Path(args.out), execute=args.execute)
    except Exception as exc:
        print(f"Live Composio check failed: {exc}", file=sys.stderr)
        print(
            "Required: COMPOSIO_API_KEY and COMPOSIO_USER_ID. "
            "For --execute also set COMPOSIO_TOOL_SLUG, COMPOSIO_TOOL_ARGS, "
            "and usually COMPOSIO_CONNECTED_ACCOUNT_ID.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print(f"Wrote live Composio check to {args.out}")
    print(f"Schema fetch ok: {result['schema_fetch_ok']}")
    if result.get("execution"):
        cache_hits = sum(1 for event in result["cache_events"] if event["cache_status"] == "hit")
        print(f"Execution ok. Cache hits: {cache_hits}")
    if result.get("tool_router"):
        print("Tool Router session/search ok")


def connect_main() -> None:
    """Create a Composio SDK Tool Router connection request."""

    parser = argparse.ArgumentParser(description="Create a Composio connection request through the SDK.")
    parser.add_argument("toolkit", help="Toolkit slug, for example github")
    parser.add_argument("--callback-url", default=None)
    parser.add_argument("--alias", default=None)
    args = parser.parse_args()
    try:
        request = ComposioToolExecutor().authorize_toolkit(
            args.toolkit,
            callback_url=args.callback_url,
            alias=args.alias,
        )
    except Exception as exc:
        print(f"Composio connection request failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(request)
