"""Real agent loop: Claude (tool-use) + Composio (tool execution) + Aperture (interception).

Optimizations baked in:

1. **Module-level caches** for the Composio tool list, connected accounts,
   and active user_id. First request pays the cold cost; the rest is free.
2. **Parallel tool execution** when Claude returns multiple tool_use blocks
   in one turn. ThreadPoolExecutor; the slowest call pins the wall clock.
3. **Anthropic prompt caching** on the tools array + system prompt. After
   the first call we read 80-90% off the schema cost on every iteration.
4. **Per-model pricing** (Haiku/Sonnet/Opus) tracked from response.usage,
   so we can show actual USD spent and what the un-Aperture'd version
   would have cost on the same number of tools.
5. **Model-assisted field policy** — the small Llama classifier on the side
   gets to rescue denial-list fields the user's ask actually needs.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from aperture.agent.tool_cache import (
    composio_cost_estimate,
    is_read_only_mode,
    is_write_tool,
)
from aperture.cache.interceptor import CachedExecutor
from aperture.compression.engine import compress_tool_output
from aperture.compression.rtk_inspired import (
    Tier,
    classify_tier,
    render_ultra_summary,
)
from aperture.contracts import ApertureRunConfig
from aperture.routing.effort_modes import get_effort_config
from aperture.routing.intelligent_effort import select_effort
from aperture.tokenization import count_tokens

# Default toolkit allowlist.
_DEFAULT_TOOLKITS = (
    "github",
    "gmail",
    "slack",
    "notion",
    "linear",
    "googlesheets",
    "googlecalendar",
    "googledrive",
    "supabase",
    "linkedin",
    "reddit",
    "composio_search",   # Composio's web-search bundle (no auth)
    "codeinterpreter",   # Python sandbox (no auth)
    "hackernews",        # HN aggregator (no auth)
    "weathermap",        # OpenWeatherMap (no auth)
)

# Curated read-only tool slugs per toolkit.
_CURATED_TOOL_SLUGS: dict[str, list[str]] = {
    "github": [
        "GITHUB_FIND_REPOSITORIES",
        "GITHUB_GET_A_REPOSITORY",
        "GITHUB_GET_AN_ISSUE",
        "GITHUB_FIND_PULL_REQUESTS",
        "GITHUB_LIST_COMMITS",
        "GITHUB_LIST_REPOSITORY_LANGUAGES",
        "GITHUB_GET_THE_AUTHENTICATED_USER",
    ],
    "gmail": [
        "GMAIL_SEARCH_EMAILS",
        "GMAIL_FETCH_EMAILS",
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
        "GMAIL_LIST_THREADS",
    ],
    "linear": [
        "LINEAR_GET_ALL_LINEAR_TEAMS",
        "LINEAR_GET_LINEAR_ISSUE",
        "LINEAR_GET_CURRENT_USER",
        "LINEAR_GET_USERS_BY_EMAIL",
    ],
    "notion": [
        "NOTION_FETCH_DATA",
        "NOTION_FETCH_DATABASE",
        "NOTION_FETCH_BLOCK_CONTENTS",
        "NOTION_FETCH_COMMENTS",
        "NOTION_QUERY_DATABASE",
    ],
    "googlesheets": [
        # Discovery — without this the agent can't find the user's sheets.
        "GOOGLESHEETS_SEARCH_SPREADSHEETS",
        "GOOGLESHEETS_LIST_TABLES",
        "GOOGLESHEETS_FIND_WORKSHEET_BY_TITLE",
        # Read.
        "GOOGLESHEETS_GET_BATCH_VALUES",
        "GOOGLESHEETS_GET_SHEET_NAMES",
        "GOOGLESHEETS_BATCH_GET",
    ],
    "googlecalendar": [
        # Read-only browse + lookup. The CURRENT_DATE_TIME tool is critical
        # for "today / this week / next month" asks — agent shouldn't guess.
        "GOOGLECALENDAR_GET_CURRENT_DATE_TIME",
        "GOOGLECALENDAR_LIST_CALENDARS",
        "GOOGLECALENDAR_EVENTS_LIST",
        "GOOGLECALENDAR_EVENTS_LIST_ALL_CALENDARS",
        "GOOGLECALENDAR_EVENTS_GET",
        "GOOGLECALENDAR_FIND_EVENT",
        "GOOGLECALENDAR_FIND_FREE_SLOTS",
    ],
    "googledrive": [
        # Discovery + read. FIND_FILE is the comprehensive search; the
        # downloader is what gets actual contents for "summarize this doc".
        "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_FIND_FOLDER",
        "GOOGLEDRIVE_GET_FILE_METADATA",
        "GOOGLEDRIVE_DOWNLOAD_FILE",
        "GOOGLEDRIVE_LIST_CHILDREN_V2",
        "GOOGLEDRIVE_GET_ABOUT",
    ],
    "linkedin": [
        # Read-only profile + network. Useful for "what's on my LinkedIn"
        # and "look up Person X" type asks.
        "LINKEDIN_GET_MY_INFO",
        "LINKEDIN_GET_PERSON",
        "LINKEDIN_GET_COMPANY_INFO",
        "LINKEDIN_GET_NETWORK_SIZE",
        "LINKEDIN_GET_ORG_PAGE_STATS",
    ],
    "reddit": [
        # Public Reddit browse + search.
        "REDDIT_SEARCH_ACROSS_SUBREDDITS",
        "REDDIT_GET_SUBREDDITS_SEARCH",
        "REDDIT_GET_R_TOP",
        "REDDIT_GET",                        # listing of posts
        "REDDIT_GET_REDDIT_USER_ABOUT",
        "REDDIT_RETRIEVE_SPECIFIC_COMMENT",
    ],
    "slack": [
        "SLACK_LIST_ALL_USERS",
        "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS",
        "SLACK_FETCH_CONVERSATION_HISTORY",
    ],
    "supabase": [
        # SQL access — the workhorse for "fetch rows from <table>" asks.
        "SUPABASE_BETA_RUN_SQL_QUERY",
        # Schema introspection so the agent can plan queries it doesn't
        # already know the table layout for.
        "SUPABASE_LIST_TABLES",
        "SUPABASE_GET_TABLE_SCHEMAS",
        "SUPABASE_GET_DATABASE_METADATA",
        # Project context — useful when the user asks "which projects do I have"
        "SUPABASE_LIST_ALL_PROJECTS",
        "SUPABASE_GET_PROJECT",
        # Storage / functions — read-only browse.
        "SUPABASE_LIST_BUCKETS",
        "SUPABASE_LIST_FUNCTIONS",
    ],
    "youtube": [
        # YouTube is connected on this account. Read-only browse only.
        "YOUTUBE_SEARCH",
        "YOUTUBE_VIDEO_DETAILS",
        "YOUTUBE_LIST_USER_PLAYLISTS",
    ],
    "composio_search": [
        # General-purpose web search. The agent picks one of these when
        # the user asks something Composio's connected SaaS tools can't
        # answer (e.g. "top 10 richest people", "current weather in Tokyo",
        # "latest AAPL price"). NO_AUTH — works out of the box.
        "COMPOSIO_SEARCH_TAVILY",      # general LLM-friendly search
        "COMPOSIO_SEARCH_DUCK_DUCK_GO",  # general web fallback
        "COMPOSIO_SEARCH_NEWS",        # news / current events
        "COMPOSIO_SEARCH_FINANCE",     # stocks / market data
        "COMPOSIO_SEARCH_FETCH_URL_CONTENT",  # extract clean page text
        "COMPOSIO_SEARCH_GOOGLE_MAPS", # places / location queries
        "COMPOSIO_SEARCH_FLIGHTS",     # travel queries
        "COMPOSIO_SEARCH_HOTELS",      # travel queries
        "COMPOSIO_SEARCH_SHOPPING",    # product / price comparison
        "COMPOSIO_SEARCH_SCHOLAR",     # academic papers
        "COMPOSIO_SEARCH_IMAGE",       # images on the open web
        "COMPOSIO_SEARCH_TRENDS",      # search-volume / trending topics
    ],
    "codeinterpreter": [
        # Python sandbox — NO_AUTH. Lets the agent actually compute things
        # ("average X grouped by Y", "what's the median value in this CSV"),
        # convert formats, run regex, etc. Massive unlock for analytical
        # asks where the answer requires real computation, not just lookup.
        "CODEINTERPRETER_CREATE_SANDBOX",
        "CODEINTERPRETER_EXECUTE_CODE",
        "CODEINTERPRETER_RUN_TERMINAL_CMD",
    ],
    "hackernews": [
        # NO_AUTH. The HN firehose for "what's hot in tech" asks. Story
        # lookups go through GET_ITEM_WITH_ID — IDs come from the list
        # endpoints first.
        "HACKERNEWS_GET_TOP_STORIES",
        "HACKERNEWS_GET_BEST_STORIES",
        "HACKERNEWS_GET_NEW_STORIES",
        "HACKERNEWS_GET_ASK_STORIES",
        "HACKERNEWS_GET_SHOW_STORIES",
        "HACKERNEWS_SEARCH_POSTS",
        "HACKERNEWS_GET_ITEM_WITH_ID",
        "HACKERNEWS_GET_USER_BY_USERNAME",
    ],
    "weathermap": [
        # NO_AUTH. Two-step: geocode the city, then pull current weather.
        "WEATHERMAP_GEOCODE_LOCATION",
        "WEATHERMAP_WEATHER",
    ],
}

_DEFAULT_MODEL = os.getenv("APERTURE_AGENT_MODEL") or "claude-haiku-4-5"
_MAX_ITERATIONS = int(os.getenv("APERTURE_AGENT_MAX_STEPS", "6"))
_MAX_TOKENS = int(os.getenv("APERTURE_AGENT_MAX_TOKENS", "1024"))
_TOOL_PARALLELISM = int(os.getenv("APERTURE_AGENT_PARALLEL", "5"))
# Anthropic 200k context cap. We triage messages once we cross
# _CONTEXT_BUDGET so the request lands well under the cap (leave room
# for tools array + system prompt + max_tokens output).
_CONTEXT_HARD_CAP = int(os.getenv("APERTURE_CONTEXT_CAP", "200000"))
_CONTEXT_BUDGET = int(os.getenv("APERTURE_CONTEXT_BUDGET", "160000"))


# ---------------------------------------------------------------------------
# Per-model pricing (USD per 1M tokens). Source: anthropic.com/pricing.
# Update when Anthropic publishes new tiers. Cache values are roughly
# 10% of input for read, ~125% of input for write.
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25,
    },
    "claude-haiku-3-5": {
        "input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-sonnet-4-5": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-opus-4-7": {
        "input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75,
    },
    "claude-opus-4-6": {
        "input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75,
    },
    # Generic fallback when the model name doesn't match.
    "default": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75,
    },
}


def _pricing_for(model: str) -> dict[str, float]:
    if model in _PRICING:
        return _PRICING[model]
    # Match by family
    for key in sorted(_PRICING.keys(), key=len, reverse=True):
        if key != "default" and model.startswith(key):
            return _PRICING[key]
    return _PRICING["default"]


# ---------------------------------------------------------------------------
# Context-overflow triage. Runs BEFORE every messages.create() call so we
# never hit Anthropic's 200k cap with an unrecoverable 400.
#
# Strategy:
# 1. Estimate token count of the messages array (cheap ~bytes/4 heuristic).
# 2. If above _CONTEXT_BUDGET, walk OLDEST tool_result blocks and replace
#    their content with a short placeholder. The agent's later turns can
#    still reference them by tool_use_id; the values are gone but the
#    structure stays intact.
# 3. If after triage we're STILL above the hard cap, raise so the agent
#    loop returns a clean error instead of letting Anthropic 400 us.
# ---------------------------------------------------------------------------

class ContextOverflowError(RuntimeError):
    """Raised when triage cannot bring the messages array under the cap."""


def _estimate_messages_tokens(messages: list[dict]) -> int:
    """Fast estimator — sum string lengths / 4. Within ±15% of true BPE
    count and 100x faster than running tiktoken on every iteration."""
    total = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("content") or block.get("text") or ""
                    if isinstance(text, str):
                        total += len(text)
                    else:
                        total += len(json.dumps(text, default=str))
                    # Tool args / id fields cost a little too.
                    for k in ("input", "name", "tool_use_id"):
                        v = block.get(k)
                        if v is not None:
                            total += len(json.dumps(v, default=str))
    return total // 4


def _triage_messages(
    messages: list[dict], budget_tokens: int
) -> tuple[list[dict], int]:
    """Replace oldest tool_result block contents with size-summary
    placeholders until under budget. Returns (messages, blocks_triaged)."""
    triaged = 0
    triage_threshold_chars = budget_tokens * 4

    def _current_size() -> int:
        return sum(
            len(m.get("content") if isinstance(m.get("content"), str)
                else json.dumps(m.get("content"), default=str))
            for m in messages
        )

    if _current_size() <= triage_threshold_chars:
        return messages, 0

    for msg in messages[:-1]:
        if _current_size() <= triage_threshold_chars:
            break
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            original = block.get("content")
            if not isinstance(original, str) or len(original) < 4000:
                continue
            placeholder = (
                f"[earlier tool result, ~{len(original)//4:,} tokens, "
                f"trimmed by Aperture to keep the conversation under the model's "
                f"context cap. The tool_use_id is preserved.]"
            )
            block["content"] = placeholder
            triaged += 1
            if _current_size() <= triage_threshold_chars:
                break
    return messages, triaged


# ---------------------------------------------------------------------------
# Process-level caches. The Composio SDK is sync, so we just keep dicts.
# ---------------------------------------------------------------------------

_COMPOSIO_CLIENT: Any = None
_USER_ID_CACHE: str | None = None
_TOOLKITS_CACHE: list[str] | None = None
_TOOL_LIST_CACHE: dict[tuple[str, ...], list[dict]] = {}
_CONNECTED_ACCOUNTS_CACHE: dict[str, dict[str, str]] = {}

# ---------------------------------------------------------------------------
# Whole-question result cache. Hit means the EXACT same ask within the TTL —
# we skip Claude, skip Composio, skip everything. The agent's previous result
# is returned with `served_from_cache=True` so the dashboard can render the
# free win. Compression has already happened on the cached payload.
# ---------------------------------------------------------------------------

_RESULT_CACHE: dict[str, tuple[float, "AgentRunResult"]] = {}
_RESULT_CACHE_TTL = int(os.getenv("APERTURE_RESULT_CACHE_TTL", "300"))   # 5 min
_RESULT_CACHE_MAX = int(os.getenv("APERTURE_RESULT_CACHE_MAX", "200"))


def _result_cache_key(ask: str, model: str, effort_mode: str) -> str:
    return f"{model}::{effort_mode}::{(ask or '').strip().lower()}"


def _result_cache_get(key: str) -> "AgentRunResult | None":
    entry = _RESULT_CACHE.get(key)
    if entry is None:
        return None
    expires_at, result = entry
    if time.time() > expires_at:
        _RESULT_CACHE.pop(key, None)
        return None
    return result


def _result_cache_put(key: str, result: "AgentRunResult") -> None:
    if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
        # Evict oldest. Cheap O(n) — TTL keeps n small in practice.
        oldest = min(_RESULT_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _RESULT_CACHE.pop(oldest, None)
    _RESULT_CACHE[key] = (time.time() + _RESULT_CACHE_TTL, result)


def _prune_result_cache() -> None:
    now = time.time()
    expired = [
        key for key, (expires_at, _) in _RESULT_CACHE.items()
        if now > expires_at
    ]
    for key in expired:
        _RESULT_CACHE.pop(key, None)


def clear_result_cache() -> int:
    n = len(_RESULT_CACHE)
    _RESULT_CACHE.clear()
    return n


def result_cache_stats() -> dict[str, Any]:
    _prune_result_cache()
    now = time.time()
    items = []
    for key, (expires_at, result) in _RESULT_CACHE.items():
        items.append({
            "ask": result.ask,
            "model": result.model,
            "effort_mode": result.effort_mode,
            "tool_calls": len(result.steps),
            "cache_key": key,
            "age_seconds": round(max(0.0, _RESULT_CACHE_TTL - (expires_at - now)), 1),
            "ttl_remaining_seconds": round(max(0.0, expires_at - now), 1),
        })
    return {
        "entries": len(_RESULT_CACHE),
        "ttl_seconds": _RESULT_CACHE_TTL,
        "max_entries": _RESULT_CACHE_MAX,
        "items": sorted(items, key=lambda item: item["age_seconds"]),
    }


# Has the schema cache been warmed in this process? Set on first
# successful Anthropic request.
_PROMPT_CACHE_WARMED: bool = False


def prewarm_prompt_cache(model: str | None = None) -> dict:
    """Fire a tiny Anthropic request so the schema + system prompt land
    in the prompt cache before the first user request. Saves ~$0.02 of
    cache_write tax on the first user-facing call.

    Returns a dict the dashboard can render (warmed?, ms, cost)."""
    global _PROMPT_CACHE_WARMED
    if _PROMPT_CACHE_WARMED:
        return {"warmed": True, "skipped": True}
    if not (os.getenv("ANTHROPIC_API_KEY") and os.getenv("COMPOSIO_API_KEY")):
        return {"warmed": False, "reason": "missing keys"}

    try:
        import anthropic  # type: ignore
        user_id = _resolved_user_id()
        toolkits = _resolved_toolkits(user_id)
        tool_list = _resolved_tool_list(user_id, toolkits)
        if not tool_list:
            return {"warmed": False, "reason": "no tools"}

        cached_tools: list[dict] = []
        for i, t in enumerate(tool_list):
            copy = dict(t)
            if i == len(tool_list) - 1:
                copy["cache_control"] = {"type": "ephemeral"}
            cached_tools.append(copy)
        cached_system = [
            {"type": "text", "text": _SYSTEM_PROMPT,
             "cache_control": {"type": "ephemeral"}}
        ]

        selected = model or _DEFAULT_MODEL
        client = anthropic.Anthropic()
        t = time.perf_counter()
        resp = client.messages.create(
            model=selected,
            max_tokens=4,            # essentially nothing
            system=cached_system,
            tools=cached_tools,
            messages=[{"role": "user", "content": "ok"}],
        )
        elapsed_ms = (time.perf_counter() - t) * 1000

        usage = getattr(resp, "usage", None)
        cw = getattr(usage, "cache_creation_input_tokens", 0) if usage else 0
        out = getattr(usage, "output_tokens", 0) if usage else 0
        pricing = _pricing_for(selected)
        cost = (cw * pricing["cache_write"] + out * pricing["output"]) / 1_000_000
        _PROMPT_CACHE_WARMED = True
        return {
            "warmed": True,
            "elapsed_ms": round(elapsed_ms, 0),
            "cache_write_tokens": cw,
            "warm_cost_usd": round(cost, 6),
            "model": selected,
        }
    except Exception as exc:
        return {"warmed": False, "reason": f"{type(exc).__name__}: {exc}"}


def _composio_client():
    global _COMPOSIO_CLIENT
    if _COMPOSIO_CLIENT is None:
        from composio import Composio
        from composio_anthropic import AnthropicProvider

        api_key = os.getenv("COMPOSIO_API_KEY")
        kwargs = {"provider": AnthropicProvider()}
        if api_key:
            kwargs["api_key"] = api_key
        try:
            _COMPOSIO_CLIENT = Composio(**kwargs)
        except TypeError:
            # Older SDK builds read COMPOSIO_API_KEY from the environment and
            # do not accept api_key as a constructor argument.
            _COMPOSIO_CLIENT = Composio(provider=AnthropicProvider())
    return _COMPOSIO_CLIENT


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _connected_account_ids_by_toolkit(user_id: str) -> dict[str, str]:
    if user_id in _CONNECTED_ACCOUNTS_CACHE:
        return _CONNECTED_ACCOUNTS_CACHE[user_id]

    accounts = _composio_client().connected_accounts.list(user_ids=[user_id])
    out: dict[str, str] = {}
    for account in accounts.items:
        if _obj_get(account, "status") != "ACTIVE":
            continue
        toolkit = _obj_get(account, "toolkit")
        toolkit_slug = _normalize_toolkit_slug(str(_obj_get(toolkit, "slug") or ""))
        account_id = (
            _obj_get(account, "id")
            or _obj_get(account, "connected_account_id")
            or _obj_get(account, "uuid")
        )
        if toolkit_slug and account_id:
            out[str(toolkit_slug).lower()] = str(account_id)
    _CONNECTED_ACCOUNTS_CACHE[user_id] = out
    return out


def _connected_account_id_for_tool(user_id: str, tool_slug: str) -> str | None:
    toolkit = tool_slug.split("_", 1)[0].lower()
    return _connected_account_ids_by_toolkit(user_id).get(toolkit)


def _resolved_user_id() -> str:
    global _USER_ID_CACHE
    if _USER_ID_CACHE:
        return _USER_ID_CACHE
    client = _composio_client()
    explicit = os.getenv("COMPOSIO_USER_ID")
    if explicit:
        try:
            accounts = client.connected_accounts.list(user_ids=[explicit])
            if accounts.items:
                _USER_ID_CACHE = explicit
                return explicit
        except Exception:
            pass
    accounts = client.connected_accounts.list()
    for a in accounts.items:
        if a.status == "ACTIVE":
            _USER_ID_CACHE = a.user_id
            return a.user_id
    raise RuntimeError("No active Composio connected accounts found.")


# Toolkits that don't require a connection — composio's search bundle and
# the python sandbox both work out of the box, so they should ALWAYS be
# in the resolved list regardless of what the user has hooked up.
_NO_AUTH_TOOLKITS: frozenset[str] = frozenset({
    "composio_search",
    "codeinterpreter",
    "hackernews",
    "weathermap",
})


def _resolved_toolkits(user_id: str) -> list[str]:
    global _TOOLKITS_CACHE
    if _TOOLKITS_CACHE is not None:
        return _TOOLKITS_CACHE
    accounts = _composio_client().connected_accounts.list(user_ids=[user_id])
    connected = {
        _normalize_toolkit_slug(a.toolkit.slug)
        for a in accounts.items
        if a.status == "ACTIVE"
    }
    # Always include no-auth toolkits — they have no connection to look up.
    connected = connected | _NO_AUTH_TOOLKITS
    _TOOLKITS_CACHE = [t for t in _DEFAULT_TOOLKITS if t in connected]
    return _TOOLKITS_CACHE


def _normalize_toolkit_slug(slug: str) -> str:
    normalized = (slug or "").strip().lower().replace("-", "_")
    aliases = {
        "google_sheets": "googlesheets",
        "google_sheet": "googlesheets",
        "sheets": "googlesheets",
    }
    return aliases.get(normalized, normalized)


def _toolkits_for_ask(ask: str, connected_toolkits: list[str]) -> list[str]:
    """Constrain obvious single-domain asks before the model chooses tools."""
    lowered = f" {(ask or '').lower()} "
    requested: list[str] = []
    signals: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("gmail", ("gmail", "email", "emails", "mail", "inbox", "thread", "threads")),
        ("slack", ("slack", "channel", "channels", "dm ", "dms", "message", "messages")),
        (
            "github",
            (
                "github", "repo", "repos", "repository", "repositories", "commit",
                "pr ", "pull request", "issue",
            ),
        ),
        ("googlesheets", ("google sheet", "googlesheet", "spreadsheet", "sheet ", "sheets")),
        ("notion", ("notion", "page", "pages", "database", "workspace doc", "docs")),
        ("linear", ("linear", "ticket", "tickets", "linear issue")),
        ("supabase", ("supabase", "sql", "database", "table", "rows")),
    )
    for toolkit, terms in signals:
        if toolkit in connected_toolkits and any(term in lowered for term in terms):
            requested.append(toolkit)

    return requested or connected_toolkits


def _ask_requires_connected_tool(ask: str) -> bool:
    lowered = f" {(ask or '').lower()} "
    source_terms = (
        "gmail", "email", "emails", "mail", "inbox",
        "slack", "channel", "message", "messages",
        "github", "repo", "repository", "commit", "pull request", "pr ", "issue",
        "google sheet", "googlesheet", "spreadsheet", "sheet ", "sheets", "rows",
        "notion", "page", "pages", "database",
        "linear", "ticket", "supabase", "sql", "table",
    )
    action_terms = (
        "read", "pull", "fetch", "get", "list", "show", "summarize", "summary",
        "search", "find", "scan", "triage", "overview", "last", "first", "recent",
    )
    return any(term in lowered for term in source_terms) and any(
        term in lowered for term in action_terms
    )


def _tool_prompt_for_ask(ask: str, toolkits: list[str]) -> str:
    if "googlesheets" in toolkits:
        return (
            "You must use the Google Sheets tools for this request. Do not answer "
            "from general knowledge or assumptions. If the sheet/range is ambiguous, "
            "use the available Google Sheets discovery/read tools first, then answer "
            "from the tool result."
        )
    return (
        "You must use the connected tool that matches the user's data source before "
        "answering. Do not answer from general knowledge or assumptions."
    )


def _resolved_tool_list(user_id: str, toolkits: list[str]) -> list[dict]:
    global _TOOL_LIST_CACHE
    cache_key = tuple(toolkits)
    if cache_key in _TOOL_LIST_CACHE:
        return _TOOL_LIST_CACHE[cache_key]
    client = _composio_client()
    wanted_slugs: list[str] = []
    for tk in toolkits:
        wanted_slugs.extend(_CURATED_TOOL_SLUGS.get(tk, []))
    out: list[dict] = []
    seen: set[str] = set()
    if wanted_slugs:
        try:
            curated = client.tools.get(user_id=user_id, tools=wanted_slugs)
            for t in curated:
                name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                if name and name not in seen:
                    out.append(t)
                    seen.add(name)
        except Exception:
            pass
    _TOOL_LIST_CACHE[cache_key] = out
    return out


# ---------------------------------------------------------------------------
# Per-step record returned to the dashboard.
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    tool: str
    arguments: dict
    successful: bool
    error: str | None
    raw_tokens: int
    sent_tokens: int
    saved_tokens: int
    saved_percent: float
    raw_bytes: int
    sent_bytes: int
    strategy: str
    llm_format: str
    omitted_fields: list[str]
    policy_reason_counts: dict[str, int]
    policy_promotions: list[dict[str, str]]
    classifier_used: bool
    classifier_keeps: list[str]
    raw_preview: str
    compressed_preview: str
    elapsed_ms: float
    ultra_summary: str | None = None
    tier: str = Tier.FULL.value
    # Tool-call cache behavior for this step:
    #   "miss"            — Composio was called, result cached
    #   "hit"             — served from tool cache, Composio NOT billed
    #   "write_uncached"  — write tool, deliberately bypassed cache
    #   "blocked_write"   — read-only mode rejected this write
    cache_status: str = "miss"
    cache_age_seconds: float = 0.0
    composio_cost_avoided_usd: float = 0.0
    effort_mode: str = "medium"
    compression_mode: str = "balanced"


@dataclass
class CostBreakdown:
    """Real USD cost from the Anthropic side, plus what it would have cost
    if Aperture weren't compressing tool results."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    actual_usd: float = 0.0
    # Counterfactual: same iterations but raw (uncompressed) tool results
    # would have hit the Anthropic input ledger.
    raw_input_tokens: int = 0
    counterfactual_usd: float = 0.0
    # Convenience: what we saved in dollars.
    saved_usd: float = 0.0


@dataclass
class AgentRunResult:
    ask: str
    answer: str
    model: str
    effort_mode: str = "medium"
    steps: list[StepRecord] = field(default_factory=list)
    total_raw_tokens: int = 0
    total_sent_tokens: int = 0
    total_elapsed_ms: float = 0.0
    iterations: int = 0
    stopped_reason: str = "end_turn"
    error: str | None = None
    cost: CostBreakdown | None = None
    served_from_cache: bool = False
    cached_age_seconds: float = 0.0
    # Composio side: tool calls actually billed vs. served from local cache.
    composio_calls_made: int = 0
    composio_calls_avoided: int = 0
    composio_cost_avoided_usd: float = 0.0
    # Context-overflow triage: how many earlier tool_result blocks did we
    # have to trim so the conversation stayed under Anthropic's 200k cap?
    context_triaged_blocks: int = 0
    context_overflowed: bool = False
    # Prompt rewriter — if Groq normalized the ask before sending to Claude,
    # we surface both so the UI can show the cleanup.
    original_ask: str | None = None
    ask_was_rewritten: bool = False


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, n: int = 800) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _github_list_commits_retry_args(
    tool_slug: str,
    args: dict,
    response: object,
    ask: str = "",
) -> dict | None:
    """Retry a common GitHub branch-name miss inside one dashboard step.

    Some repos still use `master`. If the model honors a user's "main branch"
    wording literally, GitHub returns a 404 for commit listing. Retrying with
    `master` avoids showing the user a failed tool step followed by the same
    tool succeeding one turn later.
    """
    if tool_slug != "GITHUB_LIST_COMMITS" or not _is_not_found_response(response):
        return None

    retry = _normalize_github_list_commits_args(tool_slug, args, ask)
    if retry != args:
        return retry

    return None


def _normalize_github_list_commits_args(
    tool_slug: str,
    args: dict,
    ask: str = "",
) -> dict:
    if tool_slug != "GITHUB_LIST_COMMITS":
        return args

    retry = dict(args)
    changed = False
    for key in ("sha", "branch", "ref", "commit_sha"):
        value = retry.get(key)
        if isinstance(value, str) and _looks_like_main_ref(value):
            retry[key] = "master"
            changed = True

    if not changed and "main branch" in (ask or "").lower():
        retry["sha"] = "master"
        changed = True

    if changed:
        return retry
    return args


def _normalize_tool_args(tool_slug: str, args: dict, ask: str = "") -> dict:
    normalized = _normalize_gmail_payload_args(tool_slug, args, ask)
    normalized = _normalize_github_list_commits_args(tool_slug, normalized, ask)
    return normalized


def _normalize_gmail_payload_args(tool_slug: str, args: dict, ask: str = "") -> dict:
    """Avoid asking Composio/Gmail for raw MIME payloads unless needed.

    Gmail summary/read asks need readable message text, not Gmail's full MIME
    tree. Some models choose `include_payload: true`; that makes Composio
    return a huge raw `payload` alongside the already flattened message text.
    """
    if tool_slug not in {
        "GMAIL_FETCH_EMAILS",
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        "GMAIL_SEARCH_EMAILS",
    }:
        return args

    lowered = (ask or "").lower()
    wants_raw_payload = any(
        term in lowered
        for term in (
            "raw",
            "mime",
            "payload",
            "source",
            "base64",
            "attachment",
            "attachments",
            "headers",
        )
    )
    if wants_raw_payload or args.get("include_payload") is False:
        return args

    normalized = dict(args)
    normalized["include_payload"] = False
    return normalized


def _looks_like_main_ref(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in {"main", "main branch", "refs/heads/main", "origin/main"}


def _is_not_found_response(response: object) -> bool:
    payload = response
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return "not found" in payload.lower() or '"status":"404"' in payload.lower()
    if isinstance(payload, dict):
        if payload.get("successful") is False or payload.get("success") is False:
            payload = payload.get("data") or payload.get("error") or payload
        if isinstance(payload, str):
            return _is_not_found_response(payload)
        if isinstance(payload, dict):
            status = str(payload.get("status") or payload.get("status_code") or "")
            message = str(payload.get("message") or payload.get("error") or "").lower()
            return status == "404" or "not found" in message
    else:
        successful = getattr(payload, "successful", getattr(payload, "success", True))
        if successful is False:
            data = getattr(payload, "data", None) or getattr(payload, "error", None)
            return _is_not_found_response(data)
    return False


def _execute_tool(
    block: Any, ask: str, user_id: str, effort_mode: str
) -> tuple[StepRecord, dict]:
    """Run one Composio tool, compress the result, build a StepRecord and
    the tool_result block to hand back to Claude. Designed to run in a
    thread pool — never raises."""
    client = _composio_client()
    slug = block.name
    args = _normalize_tool_args(slug, dict(block.input or {}), ask)
    started = time.perf_counter()
    connected_account_id = _connected_account_id_for_tool(user_id, slug)

    # READ-ONLY MODE — refuse any write tool BEFORE Composio sees it.
    # Sends a clean error back to Claude so it can recover. No bill.
    if is_read_only_mode() and is_write_tool(slug):
        msg = (
            f"refused: {slug} is a write/side-effect tool and Aperture is "
            f"in read-only mode (APERTURE_READ_ONLY=1). No call was made."
        )
        step = StepRecord(
            tool=slug, arguments=args, successful=False,
            error=msg,
            raw_tokens=0, sent_tokens=0, saved_tokens=0, saved_percent=0,
            raw_bytes=0, sent_bytes=0, strategy="blocked", llm_format="json",
            omitted_fields=[], policy_reason_counts={}, policy_promotions=[],
            classifier_used=False, classifier_keeps=[],
            raw_preview="", compressed_preview="",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            tier=Tier.PASSTHROUGH.value,
            cache_status="blocked_write",
            composio_cost_avoided_usd=composio_cost_estimate(slug),
            effort_mode=effort_mode,
            compression_mode="off",
        )
        return step, {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": msg,
            "is_error": True,
        }

    def execute_live():
        live_args = args
        result = client.tools.execute(
            slug,
            live_args,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )
        retry_args = _github_list_commits_retry_args(slug, live_args, result, ask)
        if retry_args is not None:
            return client.tools.execute(
                slug,
                retry_args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        return result

    try:
        exec_result, aperture_cache_event = CachedExecutor().execute(
            slug,
            args,
            execute_live,
            ApertureRunConfig(
                run_id=f"agent-{slug}-{block.id}",
                user_id=user_id,
                connected_account_id=connected_account_id,
                model="gpt-4o",
            ),
        )
    except Exception as exc:
        step = StepRecord(
            tool=slug, arguments=args, successful=False,
            error=f"{type(exc).__name__}: {exc}",
            raw_tokens=0, sent_tokens=0, saved_tokens=0, saved_percent=0,
            raw_bytes=0, sent_bytes=0, strategy="error", llm_format="json",
            omitted_fields=[], policy_reason_counts={}, policy_promotions=[],
            classifier_used=False, classifier_keeps=[],
            raw_preview="", compressed_preview="",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            tier=Tier.PASSTHROUGH.value,
            effort_mode=effort_mode,
            compression_mode="off",
        )
        return step, {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"error: {exc}",
            "is_error": True,
        }

    # Unwrap Composio's {data, error, successful} envelope.
    if isinstance(exec_result, dict):
        successful = bool(exec_result.get("successful", True))
        error_msg = exec_result.get("error") if not successful else None
        payload = exec_result.get("data", exec_result)
    else:
        successful = bool(getattr(exec_result, "successful", True))
        error_msg = getattr(exec_result, "error", None) if not successful else None
        payload = getattr(exec_result, "data", exec_result)
    if isinstance(payload, dict) and set(payload.keys()) == {"data"}:
        payload = payload["data"]
    raw_payload = (
        payload if isinstance(
            payload, (dict, list, str, int, float, bool, type(None))
        ) else str(payload)
    )

    # Use compact separators end-to-end so that:
    #   (a) raw_tokens (counted via stable_json_dumps which is also compact)
    #       and sent_tokens (counted from the literal string) are
    #       apples-to-apples — no phantom whitespace tokens.
    #   (b) the model genuinely receives fewer tokens. Default json.dumps
    #       inserts ", " and ": " which BPE tokenizes as extra tokens; for
    #       a 1k-row table that adds ~20k tokens of pure whitespace.
    _COMPACT = (",", ":")
    raw_serialized = json.dumps(
        raw_payload, default=str, ensure_ascii=False, separators=_COMPACT,
    )
    raw_tokens = count_tokens(raw_payload, model="gpt-4o").tokens

    # SHAPE ADAPTER — when the payload is a thin wrapper around a list of
    # rows (SUPABASE_BETA_RUN_SQL_QUERY returns {command, result: [...],
    # rows_affected, ...}), unwrap the list so the engine's tabular path
    # actually fires. Without this, our compressor sees a dict and skips
    # TOON / type-grouping entirely. Header is reattached after.
    payload_for_compression = raw_payload
    sql_wrapper_meta: dict | None = None
    if (
        isinstance(raw_payload, dict)
        and isinstance(raw_payload.get("result"), list)
        and raw_payload["result"]
        and isinstance(raw_payload["result"][0], dict)
    ):
        payload_for_compression = raw_payload["result"]
        sql_wrapper_meta = {
            k: v for k, v in raw_payload.items()
            if k != "result" and v is not None and v != ""
        }

    if effort_mode == "auto":
        decision = select_effort(
            tool_slug=slug,
            arguments=args,
            user_query=ask,
            context_used=0,
        )
        effective_effort_mode = decision.effort_mode
        compression_mode = decision.compression_mode
    else:
        effective_effort_mode = effort_mode
        compression_mode = get_effort_config(effort_mode).compression_mode

    compressed = compress_tool_output(
        payload_for_compression, slug,
        mode=compression_mode, model="gpt-4o",
        ask=ask,
        field_policy_mode="static" if compression_mode == "off" else "model_assisted",
    )

    body_payload = compressed.llm_string or json.dumps(
        compressed.compressed_payload, default=str,
        ensure_ascii=False, separators=_COMPACT,
    )

    # If we unwrapped a SQL response, reattach the metadata as a one-line
    # header (much cheaper than reserializing the entire wrapper).
    if sql_wrapper_meta:
        meta_str = json.dumps(
            sql_wrapper_meta, default=str, ensure_ascii=False, separators=_COMPACT,
        )
        body_payload = f"{meta_str}\n{body_payload}"

    # RTK-inspired ultra-summary: prepend a tiny symbol-encoded headline so
    # the model can answer single-fact questions without reading the body.
    # STRICTLY ADDITIVE — body is bit-identical with or without it.
    # Disable with `APERTURE_ULTRA_SUMMARY=0` if you want pure shortening.
    # Skip on already-tiny payloads (the headline would just be bloat).
    ultra_enabled = os.getenv("APERTURE_ULTRA_SUMMARY", "1") not in ("0", "false", "False", "")
    summary = (
        render_ultra_summary(raw_payload, slug)
        if ultra_enabled and compression_mode != "off" and raw_tokens >= 250
        else None
    )
    summary_line = summary.line if summary else None
    if summary_line:
        sent_payload = f"≡ {summary_line}\n{body_payload}"
    else:
        sent_payload = body_payload

    sent_tokens = count_tokens(sent_payload, model="gpt-4o").tokens

    # 3-tier degradation marker — Full when we shipped the model-assisted
    # compressed body; Degraded when we fell back; Passthrough is reserved
    # for the exception arm above.
    tier = classify_tier(
        raised=False,
        fell_back=compressed.strategy.startswith("inplace_safe")
                  and not compressed.strategy.endswith("_balanced"),
        probe_pass=1, probe_total=1,
    )

    if aperture_cache_event.cache_status == "hit":
        cache_status = "hit"
        composio_avoided = composio_cost_estimate(slug)
    elif is_write_tool(slug):
        cache_status = "write_uncached"
        composio_avoided = 0.0
    else:
        cache_status = aperture_cache_event.cache_status
        composio_avoided = 0.0

    step = StepRecord(
        tool=slug,
        arguments=args,
        successful=successful,
        error=error_msg,
        raw_tokens=raw_tokens,
        sent_tokens=sent_tokens,
        saved_tokens=max(0, raw_tokens - sent_tokens),
        saved_percent=(
            round((raw_tokens - sent_tokens) / raw_tokens * 100, 1) if raw_tokens else 0.0
        ),
        raw_bytes=len(raw_serialized.encode("utf-8")),
        sent_bytes=len(sent_payload.encode("utf-8")),
        strategy=compressed.strategy,
        llm_format=compressed.llm_format,
        omitted_fields=list(compressed.omitted_fields)[:30],
        policy_reason_counts=dict(compressed.policy_reason_counts),
        policy_promotions=list(compressed.policy_promotions)[:20],
        classifier_used=compressed.classifier_used,
        classifier_keeps=list(compressed.classifier_keeps),
        raw_preview=_truncate(raw_serialized),
        compressed_preview=_truncate(sent_payload),
        elapsed_ms=(time.perf_counter() - started) * 1000,
        ultra_summary=summary_line,
        tier=tier.value,
        cache_status=cache_status,
        cache_age_seconds=0.0,
        composio_cost_avoided_usd=round(composio_avoided, 4),
        effort_mode=effective_effort_mode,
        compression_mode=compression_mode,
    )
    tool_result_block = {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": sent_payload,
        "is_error": not successful,
    }
    return step, tool_result_block


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Prompt rewriter — small, cheap pre-stage that runs the user's raw ask
# through Groq's Llama-3.1-8B and normalizes failure-prone phrasings:
#
#   • "main branch" → drops the branch reference (most repos default to
#     master / develop / next, agent will auto-pick correct one)
#   • "my emails" → "my last 3 Gmail emails" (agent loop without a count
#     tends to over-fetch)
#   • "supabase rows" → adds "discover project, then list tables, then
#     query a populated one" so the agent stops asking for project IDs
#
# The rewriter NEVER changes the user's intent — it only tightens phrasing
# the downstream Claude agent struggled with in past runs. Failures are
# silent (returns the original ask).
# ---------------------------------------------------------------------------

_REWRITER_SYSTEM = (
    "You normalize an end-user's natural-language ask into a clean, "
    "unambiguous task for a tool-using AI agent. Output ONLY the rewritten "
    "ask, nothing else — no preamble, no quotes, no explanation. RULES:\n"
    "1. If the ask names a specific GitHub branch ('main', 'master'), "
    "remove that constraint — let the agent use the repo's default branch.\n"
    "2. If the ask says 'last N' for emails/messages/commits without a "
    "specific number, default to 3.\n"
    "3. If the ask references the user's Supabase/database without a "
    "project or table, add: '(discover the active project and any "
    "non-empty table first)'.\n"
    "4. If the ask is already clean, return it unchanged.\n"
    "5. Keep it under 30 words."
)


def _rewrite_ask(ask: str) -> tuple[str, bool]:
    """Returns (rewritten_ask, was_rewritten). Falls back to original on
    any failure — never blocks the request."""
    if not ask or len(ask) > 500:
        return ask, False
    if not os.getenv("GROQ_API_KEY"):
        return ask, False
    if os.getenv("APERTURE_DISABLE_REWRITER", "0") in ("1", "true"):
        return ask, False
    try:
        import httpx
        token = os.getenv("GROQ_API_KEY")
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": _REWRITER_SYSTEM},
                {"role": "user", "content": ask},
            ],
            "max_tokens": 80,
            "temperature": 0.1,
        }
        with httpx.Client(timeout=httpx.Timeout(1.5, connect=1.0)) as c:
            resp = c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code != 200:
            return ask, False
        text = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip surrounding quotes the model sometimes adds
        text = text.strip().strip('"').strip("'").strip()
        if not text or len(text) > 400:
            return ask, False
        # If the rewriter only modified casing/whitespace, treat as no-op.
        if text.lower().strip() == ask.lower().strip():
            return ask, False
        return text, True
    except Exception:
        return ask, False


_SYSTEM_PROMPT = (
    "You are an assistant with access to the user's connected tools. "
    "Use the smallest set of tool calls possible. When you have enough "
    "information, give a short, direct answer. Do not call tools "
    "speculatively. Be literal: if the user gives an exact value (a row "
    "count, a date, an owner/repo) honor it verbatim — do not infer.\n\n"
    "Respect source boundaries: if the user explicitly asks for Gmail/email, "
    "use Gmail tools only; if they ask for Slack, use Slack tools only. "
    "Do not broaden a single-source ask into another app.\n\n"
    "Web search: COMPOSIO_SEARCH_TAVILY / DUCK_DUCK_GO / NEWS / FINANCE / "
    "FETCH_URL_CONTENT / GOOGLE_MAPS / FLIGHTS / HOTELS / SHOPPING / SCHOLAR "
    "/ IMAGE / TRENDS are general web tools — use them when the question "
    "is about the *world* (top-10 lists, current events, stock prices, "
    "places, prices, papers, trending) rather than the user's connected "
    "SaaS data. Do NOT say you 'don't have access' — try a search tool first.\n\n"
    "Computation: CODEINTERPRETER_CREATE_SANDBOX + CODEINTERPRETER_EXECUTE_CODE "
    "let you run real Python. Use them when the user's ask requires actual "
    "computation that pushes beyond what a single SQL query or API call "
    "would give (multi-step transforms, statistical work, regex over text, "
    "format conversion). Don't reach for code if a single tool call answers "
    "the question.\n\n"
    "DISCOVERY: when the user references their data without naming a "
    "project, table, repo, etc., USE THE TOOLS to discover it — don't "
    "ask the user for IDs they expect you to look up. Examples:\n"
    "  • 'rows from supabase' → SUPABASE_LIST_ALL_PROJECTS, then "
    "SUPABASE_LIST_TABLES on the project, then SUPABASE_BETA_RUN_SQL_QUERY.\n"
    "  • 'my notion docs' → NOTION_FETCH_DATA / NOTION_QUERY_DATABASE.\n"
    "  • 'my linear issues' → LINEAR_GET_LINEAR_USER_ISSUES.\n"
    "  • 'my repos' → GITHUB_FIND_REPOSITORIES with no owner filter.\n"
    "  • 'my google sheet / first N rows of my sheet' → "
    "GOOGLESHEETS_SEARCH_SPREADSHEETS first to discover the sheet ID, "
    "then GOOGLESHEETS_BATCH_GET with that ID and a range like 'A1:Z50'.\n"
    "  • 'my calendar today / next week / free slots' → call "
    "GOOGLECALENDAR_GET_CURRENT_DATE_TIME first to get the user's actual "
    "current time, THEN GOOGLECALENDAR_EVENTS_LIST_ALL_CALENDARS or "
    "FIND_FREE_SLOTS with explicit timeMin/timeMax based on it.\n"
    "  • 'find / summarize my Drive doc' → GOOGLEDRIVE_FIND_FILE with a "
    "name query, then GOOGLEDRIVE_DOWNLOAD_FILE for content.\n"
    "  • 'my LinkedIn profile / connections' → LINKEDIN_GET_MY_INFO; "
    "for someone else, LINKEDIN_GET_PERSON with their public id.\n"
    "  • 'what's hot on Reddit / search r/X' → REDDIT_GET_R_TOP for a "
    "specific subreddit, REDDIT_SEARCH_ACROSS_SUBREDDITS for queries.\n"
    "  • 'top stories on Hacker News' → HACKERNEWS_GET_TOP_STORIES "
    "returns IDs; then HACKERNEWS_GET_ITEM_WITH_ID for each (3-5 max).\n"
    "  • 'weather in <city>' → WEATHERMAP_GEOCODE_LOCATION for the "
    "lat/lon, then WEATHERMAP_WEATHER with those coordinates.\n"
    "Asking the user for project IDs they obviously don't have memorized "
    "is a failure mode — discover them.\n\n"
    "Repository disambiguation: when the user names a project without "
    "an owner, prefer the canonical org. Known canonical owners:\n"
    "  composio, composio sdk → composiohq/composio\n"
    "  anthropic sdk → anthropics/anthropic-sdk-python\n"
    "  openai sdk → openai/openai-python\n"
    "  langchain → langchain-ai/langchain\n"
    "Use GITHUB_GET_A_REPOSITORY directly with the canonical "
    "owner/repo pair. ONLY use GITHUB_FIND_REPOSITORIES if you have "
    "no plausible canonical owner.\n\n"
    "GitHub branch handling: a user saying 'main branch' might be wrong — "
    "many repos use 'master', 'develop', or a custom default like 'next'. "
    "RULES:\n"
    "  1. For GITHUB_LIST_COMMITS, OMIT the `sha` parameter on the first "
    "attempt — GitHub uses the default branch automatically.\n"
    "  2. If the user explicitly asked for a specific branch and you got "
    "a 404, call GITHUB_GET_A_REPOSITORY first, read `default_branch`, "
    "then retry with `sha=<default_branch>`.\n"
    "  3. NEVER retry the same call with the same args after a 404 — that "
    "wastes tool budget. Change the strategy.\n\n"
    "Error recovery: if a tool returns an error or 404, do NOT call the "
    "same tool with the same arguments again. Either drop a parameter, "
    "discover a missing piece, or stop and answer with what you have."
)


def run_agent(
    ask: str,
    *,
    model: str | None = None,
    effort_mode: str = "medium",
    bypass_cache: bool = False,
    on_event: "callable | None" = None,
) -> AgentRunResult:
    """Run the agent loop. Optional `on_event(kind, payload)` callback fires
    on every observable transition so a streaming endpoint can push events
    to the UI as they happen rather than waiting for the run to finish.
    Event kinds: 'start', 'iteration', 'step', 'cache_hit', 'final', 'error'.
    """
    if effort_mode not in {"off", "aggressive", "low", "medium", "high", "auto"}:
        effort_mode = "medium"

    if not ask.strip():
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              effort_mode=effort_mode,
                              error="empty ask")

    # PROMPT REWRITER — sub-2s Groq pass that normalizes failure-prone
    # phrasings before the expensive Claude loop sees the ask.
    original_ask = ask
    rewritten, did_rewrite = _rewrite_ask(ask)
    if did_rewrite:
        ask = rewritten
        if on_event:
            try:
                on_event("rewritten", {
                    "original": original_ask, "rewritten": rewritten,
                })
            except Exception:
                pass

    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              effort_mode=effort_mode,
                              error=f"missing dep: {exc}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              effort_mode=effort_mode,
                              error="ANTHROPIC_API_KEY not set in .env")
    if not os.getenv("COMPOSIO_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              effort_mode=effort_mode,
                              error="COMPOSIO_API_KEY not set in .env")

    selected_model = model or _DEFAULT_MODEL

    # Result cache short-circuit: same ask + same model within TTL = $0.
    cache_key = _result_cache_key(ask, selected_model, effort_mode)
    if not bypass_cache:
        cached = _result_cache_get(cache_key)
        if cached is not None:
            # Find when it was put: TTL minus remaining
            entry = _RESULT_CACHE.get(cache_key)
            age = 0.0
            if entry is not None:
                expires_at, _ = entry
                age = max(0.0, _RESULT_CACHE_TTL - (expires_at - time.time()))
            # Return a copy with cache fields set; do NOT mutate the cached.
            from copy import deepcopy
            replay = deepcopy(cached)
            replay.served_from_cache = True
            replay.cached_age_seconds = round(age, 1)
            replay.total_elapsed_ms = 0.0   # served instantly
            if on_event:
                try:
                    on_event("cache_hit", {
                        "ask": ask, "age_seconds": replay.cached_age_seconds,
                        "model": replay.model,
                    })
                    on_event("final", _result_for_event(replay))
                except Exception:
                    pass
            return replay

    try:
        user_id = _resolved_user_id()
        connected_toolkits = _resolved_toolkits(user_id)
        toolkits = _toolkits_for_ask(ask, connected_toolkits)
        tool_list = _resolved_tool_list(user_id, toolkits)
        tool_required = _ask_requires_connected_tool(ask)
    except Exception as exc:
        return AgentRunResult(ask=ask, answer="", model=selected_model,
                              effort_mode=effort_mode,
                              error=f"Composio setup failed: {exc}")

    if not tool_list:
        return AgentRunResult(
            ask=ask, answer="", model=selected_model, effort_mode=effort_mode,
            error="No tools available. Connected toolkits: " + ", ".join(toolkits),
        )

    # Mark the LAST tool with cache_control so Anthropic caches the tools
    # array + system prompt as a single prefix. Subsequent iterations within
    # 5min hit the cache at ~10% of the input cost.
    cached_tools: list[dict] = []
    for i, t in enumerate(tool_list):
        copy = dict(t)
        if i == len(tool_list) - 1:
            copy["cache_control"] = {"type": "ephemeral"}
        cached_tools.append(copy)

    cached_system = [
        {"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ]

    client = anthropic.Anthropic()
    user_content = ask
    if tool_required:
        user_content = f"{ask}\n\n{_tool_prompt_for_ask(ask, toolkits)}"
    messages: list[dict] = [{"role": "user", "content": user_content}]
    result = AgentRunResult(ask=ask, answer="", model=selected_model, effort_mode=effort_mode)
    if did_rewrite:
        result.original_ask = original_ask
        result.ask_was_rewritten = True
    cost = CostBreakdown(model=selected_model)
    started = time.perf_counter()
    no_tool_retry_used = False

    for iteration in range(_MAX_ITERATIONS):
        result.iterations = iteration + 1

        # PRE-FLIGHT: estimate the messages array tokens. If we're heading
        # toward Anthropic's 200k cap, triage older tool_result blocks
        # before sending. Better an agent that reads a placeholder than an
        # agent that 400s and returns nothing.
        est_tokens = _estimate_messages_tokens(messages)
        if est_tokens > _CONTEXT_BUDGET:
            messages, triaged = _triage_messages(messages, _CONTEXT_BUDGET)
            result.context_triaged_blocks += triaged
            est_tokens = _estimate_messages_tokens(messages)
        if est_tokens > _CONTEXT_HARD_CAP:
            result.context_overflowed = True
            result.error = (
                f"Context overflow: even after triaging earlier tool "
                f"results, the conversation is ~{est_tokens:,} tokens, "
                f"above the {_CONTEXT_HARD_CAP:,}-token cap. Try a more "
                f"aggressive effort_mode, or narrow the ask (e.g. add "
                f"WHERE / LIMIT to SQL, or fewer rows)."
            )
            result.stopped_reason = "context_overflow"
            break

        try:
            request: dict[str, Any] = {
                "model": selected_model,
                "max_tokens": _MAX_TOKENS,
                "system": cached_system,
                "tools": cached_tools,
                "messages": messages,
            }
            if tool_required and not result.steps:
                request["tool_choice"] = {"type": "any"}
            response = client.messages.create(**request)
        except Exception as exc:
            result.error = f"Anthropic call failed: {type(exc).__name__}: {exc}"
            result.stopped_reason = "error"
            break

        # Roll usage into the cost ledger.
        usage = getattr(response, "usage", None)
        if usage is not None:
            cost.input_tokens += getattr(usage, "input_tokens", 0) or 0
            cost.output_tokens += getattr(usage, "output_tokens", 0) or 0
            cost.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
            cost.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0

        messages.append({
            "role": "assistant",
            "content": [block.model_dump() for block in response.content],
        })

        if response.stop_reason != "tool_use":
            text_blocks = [b for b in response.content if b.type == "text"]
            result.answer = "".join(b.text for b in text_blocks).strip()
            result.stopped_reason = response.stop_reason or "end_turn"
            if tool_required and not result.steps and not no_tool_retry_used:
                no_tool_retry_used = True
                result.answer = ""
                messages.append({
                    "role": "user",
                    "content": (
                        "That response did not use any connected-data tool. "
                        f"{_tool_prompt_for_ask(ask, toolkits)}"
                    ),
                })
                continue
            break

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        # PARALLEL tool execution. Wall-clock = slowest tool, not the sum.
        with concurrent.futures.ThreadPoolExecutor(max_workers=_TOOL_PARALLELISM) as pool:
            futures = [
                pool.submit(_execute_tool, block, ask, user_id, effort_mode)
                for block in tool_use_blocks
            ]
            results_in_order = [f.result() for f in futures]

        tool_result_blocks: list[dict] = []
        for step, tr in results_in_order:
            result.steps.append(step)
            result.total_raw_tokens += step.raw_tokens
            result.total_sent_tokens += step.sent_tokens
            if step.cache_status == "hit":
                result.composio_calls_avoided += 1
                result.composio_cost_avoided_usd += step.composio_cost_avoided_usd
            elif step.cache_status in ("miss", "write_uncached", "not_cacheable", "bypass"):
                result.composio_calls_made += 1
            tool_result_blocks.append(tr)
            # Stream this step to any subscribed listener BEFORE the next
            # iteration starts. UI updates feel live instead of dumping at
            # end-of-run.
            if on_event:
                try:
                    on_event("step", _step_for_event(step, len(result.steps) - 1))
                except Exception:
                    pass

        if tool_result_blocks:
            messages.append({"role": "user", "content": tool_result_blocks})
        else:
            break
    else:
        result.stopped_reason = "max_iterations"

    # Counterfactual: how much would this have cost if the LLM had read the
    # raw Composio responses instead of Aperture-compressed ones?
    #
    # Same iterations, same output tokens, same SCHEMA-LEVEL prompt caching
    # (the cache lives on the schema + system prompt — tool results are
    # NEVER cached either way). The only delta is input_tokens grows by the
    # raw-vs-sent gap on every tool turn.
    pricing = _pricing_for(selected_model)

    actual_input_cost = (
        cost.input_tokens * pricing["input"]
        + cost.cache_read_tokens * pricing["cache_read"]
        + cost.cache_write_tokens * pricing["cache_write"]
    ) / 1_000_000
    actual_output_cost = cost.output_tokens * pricing["output"] / 1_000_000
    cost.actual_usd = round(actual_input_cost + actual_output_cost, 6)

    extra_input = max(0, result.total_raw_tokens - result.total_sent_tokens)
    cost.raw_input_tokens = cost.input_tokens + extra_input
    # Counterfactual keeps cache costs identical (tool results aren't cached
    # either way) — only the non-cached input grows.
    counterfactual_input_cost = (
        cost.raw_input_tokens * pricing["input"]
        + cost.cache_read_tokens * pricing["cache_read"]
        + cost.cache_write_tokens * pricing["cache_write"]
    ) / 1_000_000
    cost.counterfactual_usd = round(
        counterfactual_input_cost + actual_output_cost, 6
    )
    cost.saved_usd = round(cost.counterfactual_usd - cost.actual_usd, 6)
    result.cost = cost
    result.total_elapsed_ms = (time.perf_counter() - started) * 1000

    # Cache only successful, non-error results.
    if not result.error and result.answer:
        _result_cache_put(cache_key, result)

    if on_event:
        try:
            on_event("final", _result_for_event(result))
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Event payload helpers — flatten dataclasses into JSON-safe dicts the
# streaming endpoint can ship to the browser.
# ---------------------------------------------------------------------------

def _step_for_event(step: "StepRecord", index: int) -> dict:
    return {
        "index": index,
        "tool": step.tool,
        "successful": step.successful,
        "error": step.error,
        "raw_tokens": step.raw_tokens,
        "sent_tokens": step.sent_tokens,
        "saved_tokens": step.saved_tokens,
        "saved_percent": step.saved_percent,
        "raw_bytes": step.raw_bytes,
        "sent_bytes": step.sent_bytes,
        "strategy": step.strategy,
        "llm_format": step.llm_format,
        "elapsed_ms": round(step.elapsed_ms, 0),
        "cache_status": step.cache_status,
        "cache_age_seconds": step.cache_age_seconds,
        "composio_cost_avoided_usd": step.composio_cost_avoided_usd,
        "tier": step.tier,
        "ultra_summary": step.ultra_summary,
        "raw_preview": step.raw_preview,
        "compressed_preview": step.compressed_preview,
        "omitted_fields": list(step.omitted_fields)[:30],
        "arguments": step.arguments,
    }


def _result_for_event(r: "AgentRunResult") -> dict:
    return {
        "ask": r.ask,
        "answer": r.answer,
        "model": r.model,
        "iterations": r.iterations,
        "stopped_reason": r.stopped_reason,
        "error": r.error,
        "served_from_cache": r.served_from_cache,
        "cached_age_seconds": r.cached_age_seconds,
        "total_raw_tokens": r.total_raw_tokens,
        "total_sent_tokens": r.total_sent_tokens,
        "total_elapsed_ms": round(r.total_elapsed_ms, 0),
        "composio_calls_made": r.composio_calls_made,
        "composio_calls_avoided": r.composio_calls_avoided,
        "composio_cost_avoided_usd": r.composio_cost_avoided_usd,
        "context_triaged_blocks": getattr(r, "context_triaged_blocks", 0),
        "original_ask": getattr(r, "original_ask", None),
        "ask_was_rewritten": getattr(r, "ask_was_rewritten", False),
        "cost": (
            {
                "model": r.cost.model,
                "input_tokens": r.cost.input_tokens,
                "output_tokens": r.cost.output_tokens,
                "cache_read_tokens": r.cost.cache_read_tokens,
                "cache_write_tokens": r.cost.cache_write_tokens,
                "raw_input_tokens": r.cost.raw_input_tokens,
                "actual_usd": r.cost.actual_usd,
                "counterfactual_usd": r.cost.counterfactual_usd,
                "saved_usd": r.cost.saved_usd,
            }
            if r.cost
            else None
        ),
    }
