"""Real agent loop: Claude (tool-use) + Composio (tool execution) + Aperture (interception).

Flow per request:

    user ask
       ↓
    Anthropic Claude with Composio tool schemas
       ↓
    Claude emits tool_use blocks
       ↓
    For each tool_use:
       Composio.execute(slug, arguments)         ← real API call
       record raw bytes / tokens
       compress_tool_output(raw, slug, ask, ...) ← Aperture
       record compressed bytes / tokens / what dropped
       send compressed result back to Claude as tool_result
       ↓
    Claude continues until stop_reason=end_turn
       ↓
    Return final answer + per-tool breakdown

Every step records what Aperture actually did to the payload — omitted
fields, policy promotions, strategy used, llm_format — so the dashboard
can show a real breakdown instead of pre-rendered numbers.
"""

from __future__ import annotations

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

# Curated read-only tool slugs per toolkit. Composio's GitHub toolkit alone
# exposes 500+ tools and most are writes / admin; sending all of them to
# Claude pollutes tool selection. Keeping ~5 well-scoped read tools per
# toolkit is what makes the agent actually find what it needs.
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


@dataclass
class StepRecord:
    """A single tool call's full breakdown for the dashboard."""

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


def _pick_user_id(client) -> str:
    """Use the configured user_id, or auto-discover the first active one."""
    explicit = os.getenv("COMPOSIO_USER_ID")
    if explicit:
        # If explicit user has connections, use it. Otherwise fall back.
        try:
            accounts = client.connected_accounts.list(user_ids=[explicit])
            if accounts.items:
                return explicit
        except Exception:
            pass
    accounts = client.connected_accounts.list()
    for a in accounts.items:
        if a.status == "ACTIVE":
            return a.user_id
    raise RuntimeError("No active Composio connected accounts found.")


def _allowed_toolkits(client, user_id: str) -> list[str]:
    """Return the intersection of our default allowlist and what's actually
    connected for this user."""
    accounts = client.connected_accounts.list(user_ids=[user_id])
    connected = {a.toolkit.slug for a in accounts.items if a.status == "ACTIVE"}
    return [t for t in _DEFAULT_TOOLKITS if t in connected]


def _truncate(text: str, n: int = 800) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def run_agent(ask: str, *, model: str | None = None) -> AgentRunResult:
    """Execute one ask with the full Claude + Composio + Aperture loop."""
    if not ask.strip():
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="empty ask")

    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error=f"missing dep: {exc}")

    try:
        from composio import Composio
        from composio_anthropic import AnthropicProvider
    except ImportError as exc:
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error=f"missing dep: {exc}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="ANTHROPIC_API_KEY not set in .env")
    if not os.getenv("COMPOSIO_API_KEY"):
        return AgentRunResult(ask=ask, answer="", model=model or _DEFAULT_MODEL,
                              error="COMPOSIO_API_KEY not set in .env")

    composio = Composio(provider=AnthropicProvider())
    selected_model = model or _DEFAULT_MODEL
    user_id = _pick_user_id(composio)
    toolkits = _allowed_toolkits(composio, user_id)
    if not toolkits:
        return AgentRunResult(ask=ask, answer="", model=selected_model,
                              error="no active connected toolkits")

    # Build a curated tool list from the connected toolkits. This is the
    # set Claude actually picks from. We then add semantic-search results
    # for the ask on top so unusual asks can still find a non-curated tool.
    wanted_slugs: list[str] = []
    for tk in toolkits:
        wanted_slugs.extend(_CURATED_TOOL_SLUGS.get(tk, []))

    tool_list: list[dict] = []
    seen_names: set[str] = set()
    if wanted_slugs:
        try:
            curated = composio.tools.get(
                user_id=user_id, tools=wanted_slugs,
            )
            for t in curated:
                name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                if name and name not in seen_names:
                    tool_list.append(t)
                    seen_names.add(name)
        except Exception:
            pass

    # Add up to 8 search-matched extras for off-curated asks.
    try:
        searched = composio.tools.get(
            user_id=user_id, toolkits=toolkits, search=ask, limit=8,
        )
        for t in searched:
            name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
            if name and name not in seen_names:
                tool_list.append(t)
                seen_names.add(name)
    except Exception:
        pass

    if not tool_list:
        return AgentRunResult(
            ask=ask, answer="", model=selected_model,
            error="No tools available. Connected toolkits: " + ", ".join(toolkits),
        )
    anthropic_client = anthropic.Anthropic()

    messages: list[dict] = [{"role": "user", "content": ask}]
    system_prompt = (
        "You are an assistant with access to the user's connected tools. "
        "Use the smallest set of tool calls possible. When you have enough "
        "information, give a short, direct answer. Do not call tools "
        "speculatively."
    )

    result = AgentRunResult(ask=ask, answer="", model=selected_model)
    started = time.perf_counter()

    for iteration in range(_MAX_ITERATIONS):
        result.iterations = iteration + 1
        try:
            response = anthropic_client.messages.create(
                model=selected_model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                tools=tool_list,
                messages=messages,
            )
        except Exception as exc:
            result.error = f"Anthropic call failed: {type(exc).__name__}: {exc}"
            result.stopped_reason = "error"
            break

        # Append assistant message verbatim so tool_result references resolve.
        messages.append({
            "role": "assistant",
            "content": [block.model_dump() for block in response.content],
        })

        if response.stop_reason != "tool_use":
            # Pull text from the response for the final answer.
            text_blocks = [b for b in response.content if b.type == "text"]
            result.answer = "".join(b.text for b in text_blocks).strip()
            result.stopped_reason = response.stop_reason or "end_turn"
            break

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_result_blocks: list[dict] = []
        for block in tool_use_blocks:
            slug = block.name
            args = dict(block.input or {})
            step_started = time.perf_counter()

            try:
                exec_result = composio.tools.execute(
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
                    elapsed_ms=(time.perf_counter() - step_started) * 1000,
                )
                result.steps.append(step)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"error: {exc}",
                    "is_error": True,
                })
                continue

            # Composio v3 returns {data, error, successful}. Unwrap to the
            # actual payload so Aperture measures the real response, not the
            # wrapper. Some responses double-wrap as {data: {data: ...}}.
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
                raw_payload,
                slug,
                mode="balanced",
                model="gpt-4o",
                ask=ask,
                field_policy_mode="ask_aware",
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
                    round((raw_tokens - sent_tokens) / raw_tokens * 100, 1)
                    if raw_tokens else 0.0
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
                elapsed_ms=(time.perf_counter() - step_started) * 1000,
            )
            result.steps.append(step)
            result.total_raw_tokens += raw_tokens
            result.total_sent_tokens += sent_tokens

            # Hand the COMPRESSED payload back to Claude.
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": sent_payload,
                "is_error": not successful,
            })

        if tool_result_blocks:
            messages.append({"role": "user", "content": tool_result_blocks})
        else:
            break
    else:
        result.stopped_reason = "max_iterations"

    result.total_elapsed_ms = (time.perf_counter() - started) * 1000
    return result
