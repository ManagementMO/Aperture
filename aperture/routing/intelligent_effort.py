"""Intelligent effort allocation — auto-selects compression/schema depth based on
task complexity, context window pressure, and token budget.

This is Aperture's "Claude effort levels for Composio": the system automatically
determines how much schema detail and compression aggressiveness a tool call
needs, rather than forcing the developer to manually pick low/medium/high."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from aperture.tokenization import count_tokens


class TaskComplexity(Enum):
    SIMPLE = "simple"          # Single lookup, known entity, no reasoning
    MODERATE = "moderate"      # Filtered search, some context needed
    COMPLEX = "complex"        # Analysis, categorization, multi-step reasoning
    DEEP = "deep"              # Full audit, cross-reference, synthesis


@dataclass
class EffortDecision:
    """The result of intelligent effort analysis."""

    complexity: TaskComplexity
    effort_mode: str           # "low", "medium", "high", or "shadow"
    compression_mode: str      # "off", "shadow", "safe", "balanced"
    schema_depth: str          # "minimal", "standard", "full"
    reasoning: str             # Human-readable explanation
    confidence: float          # 0.0-1.0
    estimated_savings: int     # Predicted tokens to save
    critical_fields: list[str]  # Fields that MUST be preserved


# Keywords that signal complexity levels
_SIMPLE_SIGNALS = {
    "get", "fetch", "show", "display", "what is", "who is", "where is",
    "list", "count", "status", "check", "find", "lookup", "retrieve",
    "recent", "latest", "today", "now", "current",
}

_MODERATE_SIGNALS = {
    "search", "filter", "sort", "compare", "between", "last week",
    "summary", "overview", "highlight", "top", "most", "least",
    "unread", "open", "pending", "assigned to me",
}

_COMPLEX_SIGNALS = {
    "analyze", "categorize", "classify", "summarize", "extract",
    "identify patterns", "trends", "sentiment", "priority", "urgency",
    "correlate", "cross-reference", "audit", "review", "evaluate",
    "recommend", "suggest", "predict", "forecast",
}

_DEEP_SIGNALS = {
    "comprehensive", "deep dive", "full analysis", "root cause",
    "investigate", "synthesize", "thematic analysis", "longitudinal",
    "all time", "every", "complete history", "full context",
}

# Tool complexity baselines — some tools inherently return more data
_TOOL_COMPLEXITY = {
    "GITHUB_GET_A_REPOSITORY": TaskComplexity.SIMPLE,
    "GITHUB_GET_REPO": TaskComplexity.SIMPLE,
    "GITHUB_GET_ISSUE": TaskComplexity.SIMPLE,
    "GITHUB_GET_USER": TaskComplexity.SIMPLE,
    "GITHUB_LIST_ISSUES": TaskComplexity.MODERATE,
    "GITHUB_LIST_REPOSITORY_ISSUES": TaskComplexity.MODERATE,
    "GITHUB_LIST_PULL_REQUESTS": TaskComplexity.MODERATE,
    "GITHUB_LIST_COMMITS": TaskComplexity.MODERATE,
    "GITHUB_SEARCH_REPOS": TaskComplexity.MODERATE,
    "GMAIL_SEARCH_EMAILS": TaskComplexity.MODERATE,
    "GMAIL_FETCH_EMAILS": TaskComplexity.SIMPLE,
    "SLACK_SEARCH_MESSAGES": TaskComplexity.MODERATE,
    "SLACK_LIST_CHANNELS": TaskComplexity.SIMPLE,
    "SLACK_GET_USER": TaskComplexity.SIMPLE,
    "NOTION_SEARCH_PAGES": TaskComplexity.MODERATE,
    "NOTION_GET_PAGE": TaskComplexity.SIMPLE,
}

# Critical fields per tool — never drop these regardless of effort
_CRITICAL_FIELDS = {
    "GITHUB_GET_A_REPOSITORY": ["name", "description", "stargazers_count", "language", "open_issues_count", "html_url"],
    "GITHUB_GET_REPO": ["name", "description", "stargazers_count", "language", "open_issues_count"],
    "GITHUB_LIST_ISSUES": ["title", "state", "number", "body", "user", "labels"],
    "GITHUB_LIST_REPOSITORY_ISSUES": ["title", "state", "number", "body", "user", "labels"],
    "GITHUB_LIST_PULL_REQUESTS": ["title", "state", "number", "body", "user", "head", "base"],
    "GITHUB_LIST_COMMITS": ["sha", "commit", "author", "message"],
    "GMAIL_SEARCH_EMAILS": ["snippet", "payload", "threadId"],
    "SLACK_SEARCH_MESSAGES": ["text", "user", "ts", "channel"],
}


def _analyze_query(query: str | None) -> TaskComplexity:
    """Analyze the user's natural language query for complexity signals."""
    if not query:
        return TaskComplexity.MODERATE

    query_lower = query.lower()

    # Count signal matches
    deep_score = sum(1 for s in _DEEP_SIGNALS if s in query_lower)
    complex_score = sum(1 for s in _COMPLEX_SIGNALS if s in query_lower)
    moderate_score = sum(1 for s in _MODERATE_SIGNALS if s in query_lower)
    simple_score = sum(1 for s in _SIMPLE_SIGNALS if s in query_lower)

    # Presence of numbers often means specificity (simple)
    if re.search(r'\b\d+\b', query_lower):
        simple_score += 0.5

    # Length heuristic — longer queries tend to be more complex
    if len(query_lower) > 100:
        complex_score += 1
    elif len(query_lower) < 30:
        simple_score += 1

    scores = {
        TaskComplexity.DEEP: deep_score * 3,
        TaskComplexity.COMPLEX: complex_score * 2,
        TaskComplexity.MODERATE: moderate_score,
        TaskComplexity.SIMPLE: simple_score,
    }

    return max(scores, key=scores.get)


def _analyze_tool(tool_slug: str, arguments: dict) -> TaskComplexity:
    """Analyze tool call patterns for complexity."""
    base = _TOOL_COMPLEXITY.get(tool_slug, TaskComplexity.MODERATE)

    # Arguments can shift complexity
    if "per_page" in arguments and arguments["per_page"] > 10:
        # Requesting lots of results → more complex
        if base == TaskComplexity.SIMPLE:
            return TaskComplexity.MODERATE
        elif base == TaskComplexity.MODERATE:
            return TaskComplexity.COMPLEX

    if "query" in arguments and len(arguments["query"]) > 30:
        # Complex search query
        if base == TaskComplexity.SIMPLE:
            return TaskComplexity.MODERATE

    if "labels" in arguments or "assignee" in arguments or "milestone" in arguments:
        # Filtered queries are more specific than bare lists
        return base  # Already accounted for in tool mapping

    return base


def _context_pressure_factor(context_used: int, context_limit: int = 128_000) -> float:
    """Return a pressure factor 0.0-1.0 based on context window usage."""
    ratio = context_used / context_limit
    if ratio < 0.1:
        return 0.0
    elif ratio < 0.3:
        return 0.2
    elif ratio < 0.5:
        return 0.4
    elif ratio < 0.7:
        return 0.6
    elif ratio < 0.9:
        return 0.8
    else:
        return 1.0


def select_effort(
    tool_slug: str,
    arguments: dict,
    user_query: str | None = None,
    context_used: int = 0,
    context_limit: int = 128_000,
    previous_calls: list[dict] | None = None,
) -> EffortDecision:
    """Intelligently select effort mode for a tool call.

    This is the core of Aperture's "auto" mode. It analyzes:
    1. What the user is asking for (query complexity)
    2. What tool is being called (tool complexity baseline)
    3. How much context window is left (pressure factor)
    4. Whether this is a repeated pattern (cache likelihood)

    Returns an EffortDecision with reasoning and confidence.
    """
    # Step 1: Analyze task complexity
    query_complexity = _analyze_query(user_query)
    tool_complexity = _analyze_tool(tool_slug, arguments)

    # Blend — the more complex of the two wins
    complexity_order = [TaskComplexity.SIMPLE, TaskComplexity.MODERATE, TaskComplexity.COMPLEX, TaskComplexity.DEEP]
    query_idx = complexity_order.index(query_complexity)
    tool_idx = complexity_order.index(tool_complexity)
    blended_idx = max(query_idx, tool_idx)
    blended_complexity = complexity_order[blended_idx]

    # Step 2: Context pressure adjustment
    pressure = _context_pressure_factor(context_used, context_limit)

    # Step 3: Determine effort mode
    # Base mapping
    if blended_complexity == TaskComplexity.SIMPLE:
        effort_mode = "low"
        compression_mode = "safe"
        schema_depth = "minimal"
        base_savings = 0.75
    elif blended_complexity == TaskComplexity.MODERATE:
        effort_mode = "medium"
        compression_mode = "balanced"
        schema_depth = "standard"
        base_savings = 0.60
    elif blended_complexity == TaskComplexity.COMPLEX:
        effort_mode = "high"
        compression_mode = "safe"
        schema_depth = "full"
        base_savings = 0.40
    else:  # DEEP
        effort_mode = "high"
        compression_mode = "off"
        schema_depth = "full"
        base_savings = 0.20

    # Pressure override — if context is tight, be more aggressive
    if pressure > 0.5 and effort_mode != "low":
        if effort_mode == "high":
            effort_mode = "medium"
            compression_mode = "balanced"
            schema_depth = "standard"
        elif effort_mode == "medium":
            effort_mode = "low"
            compression_mode = "safe"
            schema_depth = "minimal"
        base_savings = min(base_savings + pressure * 0.3, 0.85)

    # Step 4: Cache likelihood — if we've called this before, compress more
    # (the cached version will be available if needed)
    if previous_calls:
        same_tool_count = sum(1 for c in previous_calls if c.get("tool_slug") == tool_slug)
        if same_tool_count > 1:
            base_savings = min(base_savings + 0.1, 0.90)

    # Step 5: Build reasoning
    reasons = []
    if query_complexity != TaskComplexity.MODERATE:
        reasons.append(f"query complexity: {query_complexity.value}")
    if tool_complexity != TaskComplexity.MODERATE:
        reasons.append(f"tool complexity: {tool_complexity.value}")
    if pressure > 0.3:
        reasons.append(f"context pressure: {pressure:.0%}")
    if not reasons:
        reasons.append("default moderate profile")

    reasoning = f"Auto-selected {effort_mode} effort because " + ", ".join(reasons)

    # Step 6: Estimate savings
    # Rough heuristic: typical Composio response sizes
    typical_sizes = {
        "GITHUB_GET_A_REPOSITORY": 1800,
        "GITHUB_GET_REPO": 1800,
        "GITHUB_LIST_ISSUES": 8500,
        "GITHUB_LIST_REPOSITORY_ISSUES": 8500,
        "GITHUB_LIST_PULL_REQUESTS": 9500,
        "GITHUB_LIST_COMMITS": 5000,
        "GMAIL_SEARCH_EMAILS": 1600,
        "SLACK_SEARCH_MESSAGES": 900,
    }
    typical = typical_sizes.get(tool_slug, 3000)
    estimated_savings = int(typical * base_savings)

    # Step 7: Critical fields
    critical = _CRITICAL_FIELDS.get(tool_slug, [])

    return EffortDecision(
        complexity=blended_complexity,
        effort_mode=effort_mode,
        compression_mode=compression_mode,
        schema_depth=schema_depth,
        reasoning=reasoning,
        confidence=0.7 + (0.1 if query_complexity == tool_complexity else 0.0) - (pressure * 0.1),
        estimated_savings=estimated_savings,
        critical_fields=critical,
    )
