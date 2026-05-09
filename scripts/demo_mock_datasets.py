#!/usr/bin/env python3
"""Demo: Aperture compression on mock datasets for Notion, Linear, Supabase.

Run repeatedly to test compression nonstop — no API calls needed.

Usage:
    uv run python scripts/demo_mock_datasets.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aperture.compression.engine import compress_tool_output
from aperture.tokenization.counter import count_tokens

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def demo_file(label: str, filename: str, tool_slug: str, modes: list[str] | None = None) -> None:
    """Run compression demo on a single mock dataset."""
    modes = modes or ["off", "safe", "balanced", "low"]

    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"  File: {filename}")
    print(f"{'=' * 70}")

    path = os.path.join(DATA_DIR, filename)
    with open(path) as f:
        data = json.load(f)

    raw_tc = count_tokens(data)
    raw_tokens = raw_tc.tokens
    print(f"  Raw payload: {len(json.dumps(data)):,} chars | {raw_tokens:,} tokens")
    print(f"  Rows/items:  {len(data):,}")
    print()
    print(f"  {'Mode':<12} {'Tokens':>10} {'Reduction':>10} {'Context %':>10} {'Latency':>10}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10}")

    for mode in modes:
        t0 = time.perf_counter()
        result = compress_tool_output(data, tool_slug, mode=mode, model="gpt-4o")
        t1 = time.perf_counter()

        compressed = result.compressed_payload
        comp_tc = count_tokens(compressed)
        comp_tokens = comp_tc.tokens
        reduction = (1 - comp_tokens / raw_tokens) * 100 if raw_tokens else 0
        context_pct = comp_tokens / 128_000 * 100

        print(
            f"  {mode:<12} "
            f"{comp_tokens:>10,} "
            f"{reduction:>9.1f}% "
            f"{context_pct:>9.1f}% "
            f"{((t1 - t0) * 1000):>8.1f}ms"
        )

    # Show summary from balanced mode
    result = compress_tool_output(data, tool_slug, mode="balanced", model="gpt-4o")
    summary = result.compressed_payload.get("_aperture_summary", {})
    print()
    print(f"  Balanced mode summary: {json.dumps(summary, indent=4)}")


def main() -> None:
    demo_file(
        "NOTION — 500 pages with rich properties",
        "notion_pages_500.json",
        "NOTION_SEARCH_NOTION_PAGE",
    )
    demo_file(
        "LINEAR — 200 issues with full metadata",
        "linear_issues_200.json",
        "LINEAR_GET_LINEAR_USER_ISSUES",
    )
    demo_file(
        "SUPABASE — 1,000 user rows with nested metadata",
        "supabase_users_1000.json",
        "SUPABASE_FETCH_TABLE_ROWS",
    )

    print("\n" + "=" * 70)
    print("  All done! Test nonstop with these local files.")
    print("=" * 70)


if __name__ == "__main__":
    main()
