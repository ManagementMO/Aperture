"""Vanilla Composio vs Aperture — head-to-head comparison harness.

Same tool call, two paths:

    Vanilla:  Composio → raw JSON → LLM
    Aperture: Composio → normalize → compress → cache (compressed) → LLM

Reports per-call tokens, latency, dollar cost (gpt-4o pricing), and quality
probes (does the compressed output still contain the signal an agent would
have used?). Multi-turn scenarios show cache hits returning the already-
compressed payload — the second call pays warm tokens, not raw.

Numbers are deterministic — every count comes from `tiktoken` (gpt-4o).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from aperture.cache.policy import is_cacheable
from aperture.compression.engine import compress_tool_output
from aperture.demo.scenarios import get_mock_result
from aperture.tokenization import count_tokens

# OpenAI gpt-4o input pricing (USD per 1M tokens, Dec 2024).
_GPT4O_INPUT_USD_PER_1M = 2.50


@dataclass
class CallResult:
    tool_slug: str
    arguments: dict[str, Any]
    raw_tokens: int
    aperture_tokens: int
    raw_cost_usd: float
    aperture_cost_usd: float
    cost_saved_usd: float
    tokens_saved: int
    saved_percent: float
    llm_format: str
    cache_status: str
    latency_ms: float
    quality: dict[str, bool] = field(default_factory=dict)
    quality_passed: bool = True


@dataclass
class ScenarioResult:
    name: str
    description: str
    calls: list[CallResult] = field(default_factory=list)

    @property
    def total_raw(self) -> int:
        return sum(c.raw_tokens for c in self.calls)

    @property
    def total_aperture(self) -> int:
        return sum(c.aperture_tokens for c in self.calls)

    @property
    def total_saved(self) -> int:
        return self.total_raw - self.total_aperture

    @property
    def saved_percent(self) -> float:
        return (self.total_saved / self.total_raw * 100) if self.total_raw else 0.0

    @property
    def total_raw_cost(self) -> float:
        return self.total_raw * _GPT4O_INPUT_USD_PER_1M / 1_000_000

    @property
    def total_aperture_cost(self) -> float:
        return self.total_aperture * _GPT4O_INPUT_USD_PER_1M / 1_000_000

    @property
    def quality_passed(self) -> bool:
        return all(c.quality_passed for c in self.calls)


# ---------------------------------------------------------------------------
# Bench cache: stores compressed payloads (not raw) so a cache hit on the
# second turn means the LLM never sees the raw data again. Independent of
# `aperture/cache/store.py` (which stores raw at the executor layer).
# ---------------------------------------------------------------------------

@dataclass
class _CachedCompression:
    compressed_payload: object
    aperture_tokens: int
    llm_format: str


class BenchCache:
    """In-memory compressed-payload cache, scoped to a single scenario run."""

    def __init__(self) -> None:
        self._store: dict[str, _CachedCompression] = {}

    def _key(self, tool_slug: str, arguments: dict[str, Any]) -> str:
        args_str = json.dumps(arguments, sort_keys=True, default=str)
        digest = hashlib.sha256(args_str.encode("utf-8")).hexdigest()[:16]
        return f"{tool_slug}:{digest}"

    def get(self, tool_slug: str, arguments: dict[str, Any]) -> _CachedCompression | None:
        if not is_cacheable(tool_slug):
            return None
        return self._store.get(self._key(tool_slug, arguments))

    def put(self, tool_slug: str, arguments: dict[str, Any], entry: _CachedCompression) -> None:
        if not is_cacheable(tool_slug):
            return
        self._store[self._key(tool_slug, arguments)] = entry


# ---------------------------------------------------------------------------
# Quality probes — check the compressed payload still contains the signal an
# agent would extract from the raw response.
# ---------------------------------------------------------------------------

def _stringify(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    # `ensure_ascii=False` keeps em-dash, smart quotes, and other unicode
    # intact so substring probes don't trip on `—` escapes.
    return json.dumps(payload, default=str, ensure_ascii=False)


def _contains(haystack: str, needle: str) -> bool:
    return bool(needle) and needle.lower() in haystack.lower()


def _gh_repo_quality(raw: dict, compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    return {
        "name preserved": _contains(text, raw.get("name", "")),
        "stars preserved": str(raw.get("stargazers_count", "")) in text,
        "language preserved": _contains(text, raw.get("language", "")),
        "description preserved": _contains(text, (raw.get("description") or "")[:30]),
    }


def _gh_issues_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    sample = raw[:5]  # quality on the first 5 (rest are sampled away anyway)
    return {
        "first 5 titles preserved": all(_contains(text, issue["title"]) for issue in sample),
        "states preserved": all(_contains(text, issue["state"]) for issue in sample),
        "first assignee login preserved": (
            _contains(text, raw[0]["assignee"]["login"]) if raw and raw[0].get("assignee") else True
        ),
    }


def _gh_pulls_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    sample = raw[:5]
    return {
        "titles preserved": all(_contains(text, pr["title"]) for pr in sample),
        "states preserved": all(_contains(text, pr["state"]) for pr in sample),
    }


def _gh_commits_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    sample = raw[:5]
    # Commit messages can be multi-line; check the first line of each.
    return {
        "messages preserved": all(
            _contains(text, c["commit"]["message"].splitlines()[0]) for c in sample
        ),
    }


def _gmail_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)

    def header(msg, name):
        for h in msg.get("payload", {}).get("headers", []):
            if h.get("name") == name:
                return h.get("value", "")
        return ""

    subjects = [header(t["messages"][0], "Subject") for t in raw if t.get("messages")]
    senders = [header(t["messages"][0], "From") for t in raw if t.get("messages")]
    snippets = [t["messages"][0].get("snippet", "") for t in raw if t.get("messages")]
    return {
        "all subjects preserved": all(_contains(text, s) for s in subjects if s),
        "all senders preserved": all(
            _contains(text, s.split("<")[0].strip()) for s in senders if s
        ),
        "snippets preserved": all(
            _contains(text, s.split("...")[0].strip()) for s in snippets if s
        ),
    }


def _slack_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    return {
        "all message text preserved": all(
            _contains(text, msg["text"][:50]) for msg in raw if msg.get("text")
        ),
    }


def _linear_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    sample = raw[:5]
    return {
        "identifiers preserved": all(_contains(text, item["identifier"]) for item in sample),
        "titles preserved": all(_contains(text, item["title"][:30]) for item in sample),
    }


def _notion_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    sample = raw[:5]
    titles = [_extract_notion_title(p) for p in sample]
    return {
        "first 5 titles preserved": all(_contains(text, t[:30]) for t in titles if t),
    }


def _extract_notion_title(page: dict) -> str:
    title_prop = page.get("properties", {}).get("title", {})
    title_arr = title_prop.get("title", [])
    if title_arr and isinstance(title_arr[0], dict):
        return title_arr[0].get("text", {}).get("content", "")
    return ""


def _supabase_quality(raw: list[dict], compressed: object) -> dict[str, bool]:
    text = _stringify(compressed)
    # Aperture deliberately samples — only the first few records survive.
    # Probe on the IDs/emails of those sampled records, not the full input.
    return {
        "sampled emails preserved": (
            sum(1 for u in raw[:50] if u.get("email") and _contains(text, u["email"])) >= 5
        ),
        "first record id preserved": _contains(text, str(raw[0].get("id", ""))) if raw else True,
    }


_QUALITY_PROBES: dict[str, Callable[[Any, object], dict[str, bool]]] = {
    "GITHUB_GET_A_REPOSITORY": _gh_repo_quality,
    "GITHUB_LIST_ISSUES": _gh_issues_quality,
    "GITHUB_LIST_REPOSITORY_ISSUES": _gh_issues_quality,
    "GITHUB_LIST_PULL_REQUESTS": _gh_pulls_quality,
    "GITHUB_LIST_COMMITS": _gh_commits_quality,
    "GMAIL_SEARCH_EMAILS": _gmail_quality,
    "SLACK_SEARCH_MESSAGES": _slack_quality,
    "LINEAR_GET_LINEAR_USER_ISSUES": _linear_quality,
    "NOTION_SEARCH_NOTION_PAGE": _notion_quality,
    "SUPABASE_FETCH_TABLE_ROWS": _supabase_quality,
}


def _run_quality(tool_slug: str, raw: object, compressed: object) -> tuple[dict[str, bool], bool]:
    probe = _QUALITY_PROBES.get(tool_slug)
    if probe is None:
        return {}, True
    try:
        results = probe(raw, compressed)
    except Exception as exc:
        return {f"probe error: {exc}": False}, False
    return results, all(results.values())


# ---------------------------------------------------------------------------
# Single-call comparison
# ---------------------------------------------------------------------------

def compare_call(
    tool_slug: str,
    arguments: dict[str, Any],
    cache: BenchCache | None = None,
    mode: str = "balanced",
) -> CallResult:
    """Run one tool call through both paths and return a comparison."""
    cache = cache if cache is not None else BenchCache()

    raw = get_mock_result(tool_slug, arguments)
    raw_tokens = count_tokens(raw, model="gpt-4o").tokens

    start = time.perf_counter()
    cached = cache.get(tool_slug, arguments)
    if cached is not None:
        compressed_payload = cached.compressed_payload
        aperture_tokens = cached.aperture_tokens
        llm_format = cached.llm_format
        cache_status = "hit"
    else:
        result = compress_tool_output(raw, tool_slug, mode=mode, model="gpt-4o")
        compressed_payload = result.compressed_payload
        aperture_tokens = result.compressed_tokens
        llm_format = result.llm_format
        if is_cacheable(tool_slug):
            cache.put(tool_slug, arguments, _CachedCompression(
                compressed_payload=compressed_payload,
                aperture_tokens=aperture_tokens,
                llm_format=llm_format,
            ))
            cache_status = "miss"
        else:
            cache_status = "not_cacheable"
    latency_ms = (time.perf_counter() - start) * 1000

    quality, passed = _run_quality(tool_slug, raw, compressed_payload)

    raw_cost = raw_tokens * _GPT4O_INPUT_USD_PER_1M / 1_000_000
    aperture_cost = aperture_tokens * _GPT4O_INPUT_USD_PER_1M / 1_000_000

    return CallResult(
        tool_slug=tool_slug,
        arguments=arguments,
        raw_tokens=raw_tokens,
        aperture_tokens=aperture_tokens,
        raw_cost_usd=raw_cost,
        aperture_cost_usd=aperture_cost,
        cost_saved_usd=raw_cost - aperture_cost,
        tokens_saved=max(0, raw_tokens - aperture_tokens),
        saved_percent=((raw_tokens - aperture_tokens) / raw_tokens * 100) if raw_tokens else 0.0,
        llm_format=llm_format,
        cache_status=cache_status,
        latency_ms=latency_ms,
        quality=quality,
        quality_passed=passed,
    )


# ---------------------------------------------------------------------------
# Multi-turn scenarios
# ---------------------------------------------------------------------------

def scenario_research_repo(mode: str = "balanced") -> ScenarioResult:
    """Repo overview → issues → PRs → re-check repo (cache hit on turn 4)."""
    cache = BenchCache()
    sc = ScenarioResult(
        name="research_repo",
        description="Repo overview → issues → PRs → re-check repo (cache hit on turn 4)",
    )
    for slug, args in [
        ("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}),
        ("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "per_page": 5}),
        ("GITHUB_LIST_PULL_REQUESTS", {"owner": "composioHQ", "repo": "composio", "per_page": 3}),
        ("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}),
    ]:
        sc.calls.append(compare_call(slug, args, cache=cache, mode=mode))
    return sc


def scenario_triage_bugs(mode: str = "balanced") -> ScenarioResult:
    """GitHub issues → Gmail customer reports → Slack chatter."""
    cache = BenchCache()
    sc = ScenarioResult(
        name="triage_bugs",
        description="GitHub issues → Gmail customer reports → Slack chatter",
    )
    for slug, args in [
        ("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "labels": "bug", "per_page": 5}),
        ("GMAIL_SEARCH_EMAILS", {"query": "composio bug", "max_results": 3}),
        ("SLACK_SEARCH_MESSAGES", {"query": "bug OR error", "count": 4}),
    ]:
        sc.calls.append(compare_call(slug, args, cache=cache, mode=mode))
    return sc


def scenario_dataset_summarize(mode: str = "balanced") -> ScenarioResult:
    """Bulk reads where Aperture's tabular path + TOON shine."""
    cache = BenchCache()
    sc = ScenarioResult(
        name="dataset_summarize",
        description="Notion / Linear / Supabase bulk reads (where Aperture's tabular path shines)",
    )
    for slug, args in [
        ("NOTION_SEARCH_NOTION_PAGE", {"query": ""}),
        ("LINEAR_GET_LINEAR_USER_ISSUES", {}),
        ("SUPABASE_FETCH_TABLE_ROWS", {"table": "users"}),
    ]:
        sc.calls.append(compare_call(slug, args, cache=cache, mode=mode))
    return sc


SCENARIOS: list[Callable[[str], ScenarioResult]] = [
    scenario_research_repo,
    scenario_triage_bugs,
    scenario_dataset_summarize,
]


def run_all(mode: str = "balanced") -> list[ScenarioResult]:
    return [scenario(mode) for scenario in SCENARIOS]
