"""End-to-end vanilla Composio vs Aperture comparisons.

Each test runs the same tool call through both paths and asserts:
  1. Aperture's tokens < vanilla tokens (savings exist)
  2. Quality probes pass (the signal an agent would extract is preserved)
  3. Cache hits return early without re-compressing

Numbers are deterministic — same input → same compressed output → same tokens.
"""

import pytest

from aperture.benchmarks.vanilla_vs_aperture import (
    BenchCache,
    compare_call,
    run_all,
    scenario_dataset_summarize,
    scenario_research_repo,
    scenario_triage_bugs,
)


@pytest.mark.parametrize(
    "tool_slug,arguments,min_savings_pct",
    [
        ("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}, 60),
        ("GITHUB_LIST_ISSUES", {"per_page": 5}, 50),
        ("GITHUB_LIST_PULL_REQUESTS", {"per_page": 3}, 50),
        ("GITHUB_LIST_COMMITS", {"per_page": 5}, 30),
        ("GMAIL_SEARCH_EMAILS", {"query": "bug", "max_results": 3}, 70),
        ("SLACK_SEARCH_MESSAGES", {"query": "bug", "count": 4}, 50),
    ],
)
def test_per_tool_savings_and_quality(tool_slug, arguments, min_savings_pct):
    result = compare_call(tool_slug, arguments, mode="balanced")
    assert result.aperture_tokens < result.raw_tokens, (
        f"{tool_slug}: aperture {result.aperture_tokens} not less than raw {result.raw_tokens}"
    )
    assert result.saved_percent >= min_savings_pct, (
        f"{tool_slug}: only {result.saved_percent:.1f}% saved, expected >= {min_savings_pct}%"
    )
    assert result.quality_passed, (
        f"{tool_slug} quality regression: "
        f"{[k for k, v in result.quality.items() if not v]}"
    )


@pytest.mark.parametrize(
    "dataset_tool,arguments,min_savings_pct",
    [
        ("NOTION_SEARCH_NOTION_PAGE", {"query": ""}, 60),
        ("LINEAR_GET_LINEAR_USER_ISSUES", {}, 30),
        ("SUPABASE_FETCH_TABLE_ROWS", {"table": "users"}, 70),
    ],
)
def test_dataset_compression(dataset_tool, arguments, min_savings_pct):
    result = compare_call(dataset_tool, arguments, mode="balanced")
    assert result.aperture_tokens < result.raw_tokens
    assert result.saved_percent >= min_savings_pct
    assert result.quality_passed, (
        f"{dataset_tool} quality regression: "
        f"{[k for k, v in result.quality.items() if not v]}"
    )


def test_cache_hit_on_second_call():
    cache = BenchCache()
    args = {"owner": "composioHQ", "repo": "composio"}

    first = compare_call("GITHUB_GET_A_REPOSITORY", args, cache=cache)
    second = compare_call("GITHUB_GET_A_REPOSITORY", args, cache=cache)
    assert first.cache_status == "miss"
    assert second.cache_status == "hit"
    # Cache hit must return the *compressed* payload (same tokens as first call).
    assert second.aperture_tokens == first.aperture_tokens


def test_writes_are_not_cached():
    cache = BenchCache()
    first = compare_call("GMAIL_SEND_EMAIL", {"to": "a@b.com"}, cache=cache)
    second = compare_call("GMAIL_SEND_EMAIL", {"to": "a@b.com"}, cache=cache)
    assert first.cache_status == "not_cacheable"
    assert second.cache_status == "not_cacheable"


def test_aggressive_saves_more_than_balanced():
    bal = compare_call("GITHUB_LIST_ISSUES", {"per_page": 5}, mode="balanced")
    agg = compare_call("GITHUB_LIST_ISSUES", {"per_page": 5}, mode="aggressive")
    assert agg.aperture_tokens <= bal.aperture_tokens, (
        f"aggressive {agg.aperture_tokens} should be ≤ balanced {bal.aperture_tokens}"
    )


def test_research_scenario_savings():
    sc = scenario_research_repo(mode="balanced")
    assert sc.saved_percent >= 50
    assert sc.quality_passed
    # The repeated repo fetch must hit cache.
    cache_hits = sum(1 for c in sc.calls if c.cache_status == "hit")
    assert cache_hits >= 1


def test_triage_scenario_savings():
    sc = scenario_triage_bugs(mode="balanced")
    assert sc.saved_percent >= 60
    assert sc.quality_passed


def test_dataset_scenario_savings():
    sc = scenario_dataset_summarize(mode="balanced")
    assert sc.saved_percent >= 50
    assert sc.quality_passed


def test_all_scenarios_quality_passes():
    results = run_all(mode="balanced")
    for sc in results:
        assert sc.quality_passed, f"{sc.name} regressed quality"
