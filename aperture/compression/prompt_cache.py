"""Prompt-caching optimizer.

The big providers (Anthropic, OpenAI, Google) all cache repeated prompt
prefixes. Anthropic supports up to **4** explicit `cache_control`
breakpoints with two TTL tiers (5min, 1hour). The trick is to place the
breakpoints so each layer of stability gets its own cache entry — that
way changing the user message doesn't invalidate the tool definitions,
and changing the tool definitions doesn't invalidate the system prompt.

Layout we emit (most stable → most dynamic):

    [system]                 ─┐
    [tool_schemas]           ─┼─ 1h TTL (breakpoint #1: end of schemas)
    [static_context]         ─┴─ 1h TTL (breakpoint #2: end of static context)
    [tool_results]           ─┐
    [user_messages] (history)─┴─ 5m TTL (breakpoint #3: end of completed turn)
    [user_messages] (current)──── 5m TTL (breakpoint #4: rolling, only when >20 blocks)

Reference: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

# Anthropic minimums. Below these the API silently does not cache — we don't
# bill the cache tier for prompts that won't actually be cached.
_MIN_CACHEABLE_TOKENS = {
    "claude-haiku": 2048,
    "claude-sonnet": 1024,
    "claude-opus": 1024,
    "default": 1024,
}

_TTL_LABEL = Literal["5m", "1h"]


@dataclass
class CacheBlock:
    """One block of prompt content with caching metadata."""

    content: str
    block_type: str  # system | schema | static_context | tool_result | user_message | dynamic
    cacheable: bool = True
    estimated_tokens: int = 0
    ttl: _TTL_LABEL = "5m"
    prefix_hash: str | None = None


@dataclass
class CacheBreakpoint:
    """A cache_control point in the prompt."""

    block_index: int
    ttl: _TTL_LABEL
    reason: str


@dataclass
class CacheOptimizedPrompt:
    """Prompt rendered for optimal cache hit rates."""

    blocks: list[CacheBlock]
    breakpoints: list[CacheBreakpoint] = field(default_factory=list)
    provider: str = "anthropic"
    min_cacheable_tokens: int = 1024

    def to_provider_format(self) -> list[dict[str, Any]]:
        if self.provider == "anthropic":
            return self._to_anthropic_format()
        return [
            {"role": _block_role(b.block_type), "content": b.content}
            for b in self.blocks
        ]

    def _to_anthropic_format(self) -> list[dict[str, Any]]:
        breakpoint_indices = {bp.block_index: bp for bp in self.breakpoints}
        messages: list[dict[str, Any]] = []
        for i, block in enumerate(self.blocks):
            msg: dict[str, Any] = {
                "role": _block_role(block.block_type),
                "content": block.content,
            }
            if i in breakpoint_indices:
                bp = breakpoint_indices[i]
                msg["cache_control"] = {"type": "ephemeral", "ttl": bp.ttl}
            messages.append(msg)
        return messages


def _block_role(block_type: str) -> str:
    return {
        "system": "system",
        "schema": "system",
        "static_context": "system",
        "tool_result": "user",
        "user_message": "user",
        "dynamic": "user",
    }.get(block_type, "user")


def _model_min_tokens(model: str | None) -> int:
    if not model:
        return _MIN_CACHEABLE_TOKENS["default"]
    lowered = model.lower()
    for key, val in _MIN_CACHEABLE_TOKENS.items():
        if key in lowered:
            return val
    return _MIN_CACHEABLE_TOKENS["default"]


def _stable_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _format_tool_result(result: object) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def build_cache_optimized_prompt(
    system_prompt: str | None,
    tool_schemas: list[str],
    static_context: list[str],
    tool_results: list[Any],
    user_messages: list[str],
    provider: str = "anthropic",
    model: str | None = None,
    history_turn_count: int = 0,
) -> CacheOptimizedPrompt:
    """Build a prompt with multi-tier breakpoints.

    `history_turn_count` is the number of *completed* assistant turns so far.
    Once we cross ~20 blocks Anthropic's lookback window expires the static
    breakpoint, so we add a rolling 5m breakpoint after the latest history.
    """
    blocks: list[CacheBlock] = []

    if system_prompt:
        blocks.append(CacheBlock(
            content=system_prompt,
            block_type="system",
            cacheable=True,
            ttl="1h",
        ))

    schema_start = len(blocks)
    for schema in tool_schemas:
        blocks.append(CacheBlock(
            content=schema,
            block_type="schema",
            cacheable=True,
            ttl="1h",
        ))
    schema_end = len(blocks) - 1 if len(blocks) > schema_start else None

    context_start = len(blocks)
    for ctx in static_context:
        blocks.append(CacheBlock(
            content=ctx,
            block_type="static_context",
            cacheable=True,
            ttl="1h",
        ))
    context_end = len(blocks) - 1 if len(blocks) > context_start else None

    # Tool results are content blocks: same identity → cacheable on the next
    # turn. We tag them cacheable; the rolling 5m breakpoint after them does
    # the work.
    for result in tool_results:
        blocks.append(CacheBlock(
            content=_format_tool_result(result),
            block_type="tool_result",
            cacheable=True,
            ttl="5m",
        ))

    history_end = len(blocks) - 1 if tool_results else None

    for msg in user_messages:
        blocks.append(CacheBlock(
            content=msg,
            block_type="user_message",
            cacheable=False,
            ttl="5m",
        ))

    # Stable prefix hashes for hot-path detection.
    prefix_acc = []
    for block in blocks:
        prefix_acc.append(block.content)
        block.prefix_hash = _stable_hash("\n".join(prefix_acc))

    breakpoints: list[CacheBreakpoint] = []
    if schema_end is not None:
        breakpoints.append(CacheBreakpoint(schema_end, "1h", "end of tool_schemas"))
    if context_end is not None and context_end != schema_end:
        breakpoints.append(CacheBreakpoint(context_end, "1h", "end of static_context"))
    if history_end is not None:
        breakpoints.append(CacheBreakpoint(history_end, "5m", "end of prior turn"))

    # Rolling 5m breakpoint on the last user message — only useful in long
    # sessions where the lookback window would otherwise expire.
    if history_turn_count > 20 and user_messages and len(breakpoints) < 4:
        breakpoints.append(CacheBreakpoint(len(blocks) - 1, "5m", "rolling"))

    breakpoints = breakpoints[:4]

    return CacheOptimizedPrompt(
        blocks=blocks,
        breakpoints=breakpoints,
        provider=provider,
        min_cacheable_tokens=_model_min_tokens(model),
    )


def estimate_savings(
    prompt: CacheOptimizedPrompt,
    cache_hit_rate: float = 0.9,
    expected_turns: int = 8,
    provider: str = "anthropic",
) -> dict[str, Any]:
    """Cost model with explicit warm/cold paths.

    First call pays the write multiplier (1.25× for 5m, 2× for 1h).
    Subsequent warm calls pay the read multiplier (0.10×).
    Below the model's minimum, blocks are silently skipped by the API — we
    don't pretend they cache.
    """
    cacheable_5m = 0
    cacheable_1h = 0
    dynamic = 0

    for block in prompt.blocks:
        tokens = block.estimated_tokens
        if not block.cacheable:
            dynamic += tokens
        elif block.ttl == "1h":
            cacheable_1h += tokens
        else:
            cacheable_5m += tokens

    # If the combined cacheable prefix is below the model's threshold the API
    # won't actually cache anything — fold those tokens back into `dynamic`.
    skipped_below_threshold = 0
    if cacheable_1h + cacheable_5m < prompt.min_cacheable_tokens:
        skipped_below_threshold = cacheable_1h + cacheable_5m
        dynamic += skipped_below_threshold
        cacheable_1h = 0
        cacheable_5m = 0

    if provider == "anthropic":
        read_mult = 0.10
        write_mult_5m = 1.25
        write_mult_1h = 2.00
    elif provider == "openai":
        read_mult = 0.50
        write_mult_5m = write_mult_1h = 1.0
    else:
        read_mult = 0.25
        write_mult_5m = write_mult_1h = 1.0

    cold_cost = (
        cacheable_1h * write_mult_1h
        + cacheable_5m * write_mult_5m
        + dynamic
    )
    warm_cost_per_turn = (
        (cacheable_1h + cacheable_5m) * cache_hit_rate * read_mult
        + (cacheable_1h + cacheable_5m) * (1 - cache_hit_rate)
        + dynamic
    )

    naive_cost = (cacheable_1h + cacheable_5m + dynamic) * expected_turns
    actual_cost = cold_cost + warm_cost_per_turn * (expected_turns - 1)
    saved = max(0, naive_cost - actual_cost)
    savings_pct = (saved / naive_cost * 100) if naive_cost > 0 else 0

    return {
        "total_tokens": cacheable_1h + cacheable_5m + dynamic,
        "cacheable_tokens": cacheable_1h + cacheable_5m,
        "cacheable_1h_tokens": cacheable_1h,
        "cacheable_5m_tokens": cacheable_5m,
        "dynamic_tokens": dynamic,
        "skipped_below_threshold": skipped_below_threshold,
        "min_cacheable_tokens": prompt.min_cacheable_tokens,
        "estimated_cache_hit_rate": cache_hit_rate,
        "expected_turns": expected_turns,
        "first_call_cost": round(cold_cost, 0),
        "warm_call_cost": round(warm_cost_per_turn, 0),
        "naive_cost": round(naive_cost, 0),
        "amortized_cost": round(actual_cost, 0),
        "tokens_saved": round(saved, 0),
        "savings_percent": round(savings_pct, 1),
        "breakpoints": [
            {"index": bp.block_index, "ttl": bp.ttl, "reason": bp.reason}
            for bp in prompt.breakpoints
        ],
        "provider": provider,
    }
