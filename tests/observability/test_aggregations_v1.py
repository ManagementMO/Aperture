"""Tests for v3.1-shape aggregators."""

from __future__ import annotations

import pytest

from aperture.observability.aggregations import (
    aggregate_cache_events_v1,
    aggregate_token_events_v1,
)


def _token_row(
    *,
    timestamp: str,
    meta_tool_slug: str = "COMPOSIO_SEARCH_TOOLS",
    toolkit_slug: str | None = None,
    user_id: str | None = "u1",
    session_id: str | None = "s1",
    session_turn: int | None = 1,
    input_tokens_contributed: int = 100,
) -> dict:
    return {
        "timestamp": timestamp,
        "meta_tool_slug": meta_tool_slug,
        "toolkit_slug": toolkit_slug,
        "user_id": user_id,
        "session_id": session_id,
        "session_turn": session_turn,
        "tool_slug": None,
        "model": "gpt-4o",
        "input_tokens_contributed": input_tokens_contributed,
    }


def test_token_aggregation_groups_by_meta_tool_slug():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", meta_tool_slug="COMPOSIO_SEARCH_TOOLS", input_tokens_contributed=300),
        _token_row(timestamp="2026-05-09T00:01:00Z", meta_tool_slug="COMPOSIO_SEARCH_TOOLS", input_tokens_contributed=200),
        _token_row(timestamp="2026-05-09T00:02:00Z", meta_tool_slug="COMPOSIO_GET_TOOL_SCHEMAS", input_tokens_contributed=150),
    ]
    result = aggregate_token_events_v1(rows, group_by="meta_tool_slug")
    assert result["total_groups"] == 2
    # Sorted desc by total
    assert result["data"][0]["group_value"] == "COMPOSIO_SEARCH_TOOLS"
    assert result["data"][0]["total_input_tokens_contributed"] == 500
    assert result["data"][0]["total_calls"] == 2
    assert result["data"][0]["average_per_call"] == 250.0
    assert result["data"][1]["group_value"] == "COMPOSIO_GET_TOOL_SCHEMAS"


def test_token_aggregation_filters_by_dt_window():
    rows = [
        _token_row(timestamp="2026-05-08T00:00:00Z", input_tokens_contributed=100),
        _token_row(timestamp="2026-05-09T00:00:00Z", input_tokens_contributed=200),
        _token_row(timestamp="2026-05-10T00:00:00Z", input_tokens_contributed=300),
    ]
    result = aggregate_token_events_v1(
        rows,
        group_by="meta_tool_slug",
        dt_gt="2026-05-09T00:00:00Z",
        dt_lt="2026-05-09T23:59:59Z",
    )
    assert result["data"][0]["total_input_tokens_contributed"] == 200


def test_token_aggregation_filters_by_user_id():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", user_id="u1", input_tokens_contributed=100),
        _token_row(timestamp="2026-05-09T00:01:00Z", user_id="u2", input_tokens_contributed=200),
    ]
    result = aggregate_token_events_v1(rows, group_by="user_id", user_id="u1")
    assert result["total_groups"] == 1
    assert result["data"][0]["group_value"] == "u1"


def test_token_aggregation_pagination():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", meta_tool_slug=f"TOOL_{i}", input_tokens_contributed=i * 10)
        for i in range(1, 6)
    ]
    page_1 = aggregate_token_events_v1(rows, group_by="meta_tool_slug", page=1, page_size=2)
    page_2 = aggregate_token_events_v1(rows, group_by="meta_tool_slug", page=2, page_size=2)
    assert len(page_1["data"]) == 2
    assert len(page_2["data"]) == 2
    assert page_1["total_groups"] == 5
    # No overlap
    p1_keys = {row["group_value"] for row in page_1["data"]}
    p2_keys = {row["group_value"] for row in page_2["data"]}
    assert p1_keys.isdisjoint(p2_keys)


def test_token_aggregation_groups_by_date():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", input_tokens_contributed=100),
        _token_row(timestamp="2026-05-09T12:00:00Z", input_tokens_contributed=200),
        _token_row(timestamp="2026-05-10T00:00:00Z", input_tokens_contributed=300),
    ]
    result = aggregate_token_events_v1(rows, group_by="date")
    by_date = {row["group_value"]: row["total_input_tokens_contributed"] for row in result["data"]}
    assert by_date["2026-05-09"] == 300
    assert by_date["2026-05-10"] == 300


def test_token_aggregation_rejects_invalid_group_by():
    with pytest.raises(ValueError):
        aggregate_token_events_v1([], group_by="nonsense_field")


def test_token_aggregation_order_direction_desc_largest_first():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", meta_tool_slug="TOOL_A", input_tokens_contributed=500),
        _token_row(timestamp="2026-05-09T00:01:00Z", meta_tool_slug="TOOL_B", input_tokens_contributed=100),
    ]
    result = aggregate_token_events_v1(rows, group_by="meta_tool_slug", order_direction="desc")
    assert [r["group_value"] for r in result["data"]] == ["TOOL_A", "TOOL_B"]


def test_token_aggregation_order_direction_asc_smallest_first():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", meta_tool_slug="TOOL_A", input_tokens_contributed=500),
        _token_row(timestamp="2026-05-09T00:01:00Z", meta_tool_slug="TOOL_B", input_tokens_contributed=100),
    ]
    result = aggregate_token_events_v1(rows, group_by="meta_tool_slug", order_direction="asc")
    assert [r["group_value"] for r in result["data"]] == ["TOOL_B", "TOOL_A"]


def test_token_aggregation_order_by_name_alphabetical():
    rows = [
        _token_row(timestamp="2026-05-09T00:00:00Z", meta_tool_slug="ZEBRA", input_tokens_contributed=500),
        _token_row(timestamp="2026-05-09T00:01:00Z", meta_tool_slug="ALPHA", input_tokens_contributed=100),
    ]
    asc = aggregate_token_events_v1(rows, group_by="meta_tool_slug", order_by="name", order_direction="asc")
    desc = aggregate_token_events_v1(rows, group_by="meta_tool_slug", order_by="name", order_direction="desc")
    assert [r["group_value"] for r in asc["data"]] == ["ALPHA", "ZEBRA"]
    assert [r["group_value"] for r in desc["data"]] == ["ZEBRA", "ALPHA"]


def test_token_aggregation_rejects_invalid_order_direction():
    with pytest.raises(ValueError):
        aggregate_token_events_v1([], group_by="meta_tool_slug", order_direction="random")


def test_token_aggregation_rejects_invalid_pagination():
    with pytest.raises(ValueError):
        aggregate_token_events_v1([], group_by="meta_tool_slug", page=0)
    with pytest.raises(ValueError):
        aggregate_token_events_v1([], group_by="meta_tool_slug", page_size=0)


def _cache_row(
    *,
    timestamp: str,
    tool_slug: str = "GITHUB_GET_REPO",
    cache_status: str = "hit",
    api_call_avoided: int = 1,
    tokens_saved_estimate: int = 100,
    user_id: str | None = "u1",
) -> dict:
    return {
        "timestamp": timestamp,
        "tool_slug": tool_slug,
        "cache_status": cache_status,
        "toolkit_slug": "github",
        "user_id": user_id,
        "api_call_avoided": api_call_avoided,
        "tokens_saved_estimate": tokens_saved_estimate,
    }


def test_cache_aggregation_groups_by_tool_slug():
    rows = [
        _cache_row(timestamp="2026-05-09T00:00:00Z", tool_slug="A", cache_status="hit", tokens_saved_estimate=100),
        _cache_row(timestamp="2026-05-09T00:01:00Z", tool_slug="A", cache_status="miss", api_call_avoided=0, tokens_saved_estimate=0),
        _cache_row(timestamp="2026-05-09T00:02:00Z", tool_slug="B", cache_status="hit", tokens_saved_estimate=50),
    ]
    result = aggregate_cache_events_v1(rows, group_by="tool_slug")
    by_tool = {row["group_value"]: row for row in result["data"]}
    assert by_tool["A"]["hits"] == 1
    assert by_tool["A"]["misses"] == 1
    assert by_tool["A"]["api_calls_avoided"] == 1
    assert by_tool["A"]["tokens_saved"] == 100
    assert by_tool["B"]["hits"] == 1
    assert by_tool["B"]["tokens_saved"] == 50
