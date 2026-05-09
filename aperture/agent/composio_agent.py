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

from aperture.compression.engine import compress_tool_output
from aperture.tokenization import count_tokens


# Default toolkit allowlist.
_DEFAULT_TOOLKITS = (
    "github",
    "gmail",
    "slack",
    "notion",
    "linear",
    "googlesheets",
    "supabase",
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
        "GOOGLESHEETS_GET_BATCH_VALUES",
        "GOOGLESHEETS_GET_SHEET_NAMES",
        "GOOGLESHEETS_BATCH_GET",
    ],
    "slack": [
        "SLACK_LIST_ALL_USERS",
        "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS",
        "SLACK_FETCH_CONVERSATION_HISTORY",
    ],
}

_DEFAULT_MODEL = os.getenv("APERTURE_AGENT_MODEL") or "claude-haiku-4-5"
_MAX_ITERATIONS = int(os.getenv("APERTURE_AGENT_MAX_STEPS", "6"))
_MAX_TOKENS = int(os.getenv("APERTURE_AGENT_MAX_TOKENS", "1024"))
_TOOL_PARALLELISM = int(os.getenv("APERTURE_AGENT_PARALLEL", "5"))


# ---------------------------------------------------------------------------
# Per-model pricing (USD per 1M tokens). Source: anthropic.com/pricing.
# Update when Anthropic publishes new tiers. Cache values are roughly
# 10% of input for read, ~125% of input for write.
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":   {"input": 1.00,  "output": 5.00,  "cache_read": 0.10, "cache_write": 1.25},
    "claude-haiku-3-5":   {"input": 0.80,  "output": 4.00,  "cache_read": 0.08, "cache_write": 1.00},
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-5":  {"input": 3.00,  "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4-7":    {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
    "claude-opus-4-6":    {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
    # Generic fallback when the model name doesn't match.
    "default":            {"input": 3.00,  "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
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
# Process-level caches. The Composio SDK is sync, so we just keep dicts.
# ---------------------------------------------------------------------------

_COMPOSIO_CLIENT: Any = None
_USER_ID_CACHE: str | None = None
_TOOLKITS_CACHE: list[str] | None = None
_TOOL_LIST_CACHE: list[dict] | None = None


def _composio_client():
    global _COMPOSIO_CLIENT
    if _COMPOSIO_CLIENT is None:
        from composio import Composio
        from composio_anthropic import AnthropicProvider
        _COMPOSIO_CLIENT = Composio(provider=AnthropicProvider())
    return _COMPOSIO_CLIENT


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


def _resolved_toolkits(user_id: str) -> list[str]:
    global _TOOLKITS_CACHE
    if _TOOLKITS_CACHE is not None:
        return _TOOLKITS_CACHE
    accounts = _composio_client().connected_accounts.list(user_ids=[user_id])
    connected = {a.toolkit.slug for a in accounts.items if a.status == "ACTIVE"}
    _TOOLKITS_CACHE = [t for t in _DEFAULT_TOOLKITS if t in connected]
    return _TOOLKITS_CACHE


def _resolved_tool_list(user_id: str, toolkits: list[str]) -> list[dict]:
    global _TOOL_LIST_CACHE
    if _TOOL_LIST_CACHE is not None:
        return _TOOL_LIST_CACHE
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
    _TOOL_LIST_CACHE = out
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
    steps: list[StepRecord] = field(default_factory=list)
    total_raw_tokens: int = 0
    total_sent_tokens: int = 0
    total_elapsed_ms: float = 0.0
    iterations: int = 0
    stopped_reason: str = "end_turn"
    error: str | None = None
    cost: CostBreakdown | None = None


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, n: int = 800) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _execute_tool(
    block: Any, ask: str, user_id: str
) -> tuple[StepRecord, dict]:
    """Run one Composio tool, compress the result, build a StepRecord and
    the tool_result block to hand back to Claude. Designed to run in a
    thread pool — never raises."""
    client = _composio_client()
    slug = block.name
    args = dict(block.input or {})
    started = time.perf_counter()

    try:
        exec_result = client.tools.execute(
            slug, args, user_id=user_id,
            dangerously_skip_version_check=True,
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

    raw_serialized = json.dumps(raw_payload, default=str, ensure_ascii=False)
    raw_tokens = count_tokens(raw_payload, model="gpt-4o").tokens

    compressed = compress_tool_output(
        raw_payload, slug,
        mode="balanced", model="gpt-4o",
        ask=ask, field_policy_mode="model_assisted",
    )
    sent_tokens = compressed.compressed_tokens
    sent_payload = compressed.llm_string or json.dumps(
        compressed.compressed_payload, default=str, ensure_ascii=False
    )

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

_SYSTEM_PROMPT = (
    "You are an assistant with access to the user's connected tools. "
    "Use the smallest set of tool calls possible. When you have enough "
    "information, give a short, direct answer. Do not call tools "
    "speculatively. Be literal: if the user gives an exact value (a row "
    "count, a date, an owner/repo) honor it verbatim — do not infer.\n\n"
    "Repository disambiguation: when the user names a project without "
    "an owner, prefer the canonical org. Known canonical owners:\n"
    "  composio, composio sdk → composiohq/composio\n"
    "  anthropic sdk → anthropics/anthropic-sdk-python\n"
    "  openai sdk → openai/openai-python\n"
    "  langchain → langchain-ai/langchain\n"
    "Use GITHUB_GET_A_REPOSITORY directly with the canonical "
    "owner/repo pair. ONLY use GITHUB_FIND_REPOSITORIES if you have "
    "no plausible canonical owner."
)


def run_agent(ask: str, *, model: str | None = None) -> AgentRunResult:
    if not ask.strip():
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="empty ask")

    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error=f"missing dep: {exc}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="ANTHROPIC_API_KEY not set in .env")
    if not os.getenv("COMPOSIO_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="COMPOSIO_API_KEY not set in .env")

    selected_model = model or _DEFAULT_MODEL

    try:
        user_id = _resolved_user_id()
        toolkits = _resolved_toolkits(user_id)
        tool_list = _resolved_tool_list(user_id, toolkits)
    except Exception as exc:
        return AgentRunResult(ask=ask, answer="", model=selected_model,
                              error=f"Composio setup failed: {exc}")

    if not tool_list:
        return AgentRunResult(
            ask=ask, answer="", model=selected_model,
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
    messages: list[dict] = [{"role": "user", "content": ask}]
    result = AgentRunResult(ask=ask, answer="", model=selected_model)
    cost = CostBreakdown(model=selected_model)
    started = time.perf_counter()

    for iteration in range(_MAX_ITERATIONS):
        result.iterations = iteration + 1
        try:
            response = client.messages.create(
                model=selected_model,
                max_tokens=_MAX_TOKENS,
                system=cached_system,
                tools=cached_tools,
                messages=messages,
            )
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
            break

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        # PARALLEL tool execution. Wall-clock = slowest tool, not the sum.
        with concurrent.futures.ThreadPoolExecutor(max_workers=_TOOL_PARALLELISM) as pool:
            futures = [
                pool.submit(_execute_tool, block, ask, user_id)
                for block in tool_use_blocks
            ]
            results_in_order = [f.result() for f in futures]

        tool_result_blocks: list[dict] = []
        for step, tr in results_in_order:
            result.steps.append(step)
            result.total_raw_tokens += step.raw_tokens
            result.total_sent_tokens += step.sent_tokens
            tool_result_blocks.append(tr)

        if tool_result_blocks:
            messages.append({"role": "user", "content": tool_result_blocks})
        else:
            break
    else:
        result.stopped_reason = "max_iterations"

    # Counterfactual: how much would this have cost if the LLM had read the
    # raw Composio responses instead of the Aperture-compressed ones? Same
    # iterations / output tokens, but the input tokens balloon by the
    # difference between raw and sent tool tokens.
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
    counterfactual_input_cost = (
        cost.raw_input_tokens * pricing["input"]
    ) / 1_000_000
    # Counterfactual doesn't use prompt caching either — full price on input.
    cost.counterfactual_usd = round(
        counterfactual_input_cost + actual_output_cost, 6
    )
    cost.saved_usd = round(cost.counterfactual_usd - cost.actual_usd, 6)
    result.cost = cost
    result.total_elapsed_ms = (time.perf_counter() - started) * 1000
    return result
