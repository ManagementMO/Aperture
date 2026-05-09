"""Markdown and JSON-ready observability reports."""

from __future__ import annotations

from aperture.observability.aggregations import (
    aggregate_cache_savings,
    aggregate_compression_savings,
    aggregate_schema_savings,
    aggregate_tokens_by_tool,
)
from aperture.types import CacheEvent, SchemaOptimizationResult, TokenAttributionEvent


def _table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_No data._\n"
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        output.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(output) + "\n"


def top_expensive_tools_report(events: list[TokenAttributionEvent]) -> str:
    """Return a Markdown report of top token-contributing tools."""

    totals = aggregate_tokens_by_tool(events)
    rows = [[tool, tokens] for tool, tokens in totals.items()]
    return "# Tool Output Cost Report\n\n" + _table(["Tool", "Input Tokens"], rows)


def compression_savings_report(events: list[TokenAttributionEvent]) -> str:
    """Return a Markdown report of compression savings by tool."""

    totals = aggregate_compression_savings(events)
    rows = [[tool, tokens] for tool, tokens in totals.items()]
    return "# Compression Savings Report\n\n" + _table(["Tool", "Tokens Saved"], rows)


def cache_savings_report(events: list[CacheEvent]) -> str:
    """Return a Markdown report of cache savings by tool."""

    totals = aggregate_cache_savings(events)
    rows = [[tool, data["hits"], data["api_calls_avoided"], data["tokens_saved"]] for tool, data in totals.items()]
    return "# Cache Savings Report\n\n" + _table(["Tool", "Hits", "API Calls Avoided", "Tokens Saved"], rows)


def session_cost_report(events: list[TokenAttributionEvent]) -> str:
    """Return a Markdown report of token cost by session."""

    totals: dict[str, int] = {}
    for event in events:
        key = event.session_id or "unknown"
        totals[key] = totals.get(key, 0) + event.input_tokens_contributed
    rows = [[session, tokens] for session, tokens in sorted(totals.items(), key=lambda item: item[1], reverse=True)]
    return "# Session Cost Report\n\n" + _table(["Session", "Input Tokens"], rows)


def schema_savings_report(results: list[SchemaOptimizationResult]) -> str:
    """Return a Markdown report of accepted schema savings."""

    totals = aggregate_schema_savings(results)
    rows = [[tool, tokens] for tool, tokens in totals.items()]
    return "# Schema Savings Report\n\n" + _table(["Tool", "Tokens Saved"], rows)

