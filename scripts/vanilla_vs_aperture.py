"""CLI: run vanilla Composio vs Aperture comparisons and print a report.

Usage:
    uv run python scripts/vanilla_vs_aperture.py
    uv run python scripts/vanilla_vs_aperture.py --mode aggressive
    uv run python scripts/vanilla_vs_aperture.py --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aperture.benchmarks.vanilla_vs_aperture import run_all  # noqa: E402


def _fmt_usd(amount: float) -> str:
    if amount >= 0.01:
        return f"${amount:.4f}"
    return f"${amount * 100:.4f}¢"


def print_report(results, mode: str) -> None:
    print(f"\n{'=' * 76}")
    print(f"  Vanilla Composio vs Aperture  —  mode={mode}")
    print(f"{'=' * 76}\n")

    grand_raw = 0
    grand_apt = 0
    grand_quality = True

    for sc in results:
        print(f"  ▸ {sc.name}: {sc.description}")
        print(f"  {'-' * 70}")
        print(
            f"  {'tool':<35} {'vanilla':>9} {'aperture':>9} {'saved':>8} {'fmt':<5} {'cache':<7}"
        )
        for c in sc.calls:
            saved_str = f"{c.saved_percent:.0f}%"
            print(
                f"  {c.tool_slug:<35} "
                f"{c.raw_tokens:>9,} "
                f"{c.aperture_tokens:>9,} "
                f"{saved_str:>8} "
                f"{c.llm_format:<5} "
                f"{c.cache_status:<7}"
            )
        print(
            f"  {'TOTAL':<35} "
            f"{sc.total_raw:>9,} "
            f"{sc.total_aperture:>9,} "
            f"{sc.saved_percent:>7.0f}% "
            f"  {_fmt_usd(sc.total_raw_cost)} → {_fmt_usd(sc.total_aperture_cost)}"
        )
        if not sc.quality_passed:
            print(f"  ⚠  quality regression in this scenario:")
            for c in sc.calls:
                for k, v in c.quality.items():
                    if not v:
                        print(f"     {c.tool_slug}: {k}")
        else:
            print(f"  ✓  quality probes pass for every call")
        print()
        grand_raw += sc.total_raw
        grand_apt += sc.total_aperture
        grand_quality = grand_quality and sc.quality_passed

    grand_saved = grand_raw - grand_apt
    grand_pct = (grand_saved / grand_raw * 100) if grand_raw else 0
    grand_raw_cost = grand_raw * 2.50 / 1_000_000
    grand_apt_cost = grand_apt * 2.50 / 1_000_000

    print(f"  {'=' * 70}")
    print(f"  TOTAL  raw={grand_raw:,}  aperture={grand_apt:,}  saved={grand_saved:,} ({grand_pct:.1f}%)")
    print(f"         cost {_fmt_usd(grand_raw_cost)} → {_fmt_usd(grand_apt_cost)}  (saved {_fmt_usd(grand_raw_cost - grand_apt_cost)} per run)")
    print(f"         quality: {'PASS' if grand_quality else 'REGRESSION'}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        default="balanced",
        choices=["off", "safe", "balanced", "low", "aggressive"],
        help="Aperture compression mode",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    results = run_all(mode=args.mode)

    if args.json:
        out = []
        for sc in results:
            out.append({
                "name": sc.name,
                "description": sc.description,
                "calls": [asdict(c) for c in sc.calls],
                "total_raw_tokens": sc.total_raw,
                "total_aperture_tokens": sc.total_aperture,
                "tokens_saved": sc.total_saved,
                "saved_percent": sc.saved_percent,
                "raw_cost_usd": sc.total_raw_cost,
                "aperture_cost_usd": sc.total_aperture_cost,
                "quality_passed": sc.quality_passed,
            })
        print(json.dumps(out, indent=2, default=str))
        return 0

    print_report(results, args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
