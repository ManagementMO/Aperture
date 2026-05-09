"""Context window budget manager — tracks token usage across an agent run and
adjusts compression aggressiveness dynamically.

Think of it like a gas gauge: as the agent's context window fills up,
Aperture automatically squeezes more out of each tool call to prevent
hitting the limit."""

from __future__ import annotations

from dataclasses import dataclass, field

from aperture.tokenization import count_tokens


@dataclass
class BudgetSnapshot:
    """A point-in-time view of the context window budget."""

    limit: int = 128_000
    used: int = 0
    reserved: int = 0  # Reserved for system prompt, reasoning, etc.
    tool_calls: int = 0
    tool_tokens: int = 0
    compression_savings: int = 0
    cache_hits: int = 0

    @property
    def available(self) -> int:
        return max(0, self.limit - self.used - self.reserved)

    @property
    def pressure(self) -> float:
        """0.0 = empty, 1.0 = full."""
        consumed = self.used + self.reserved
        return min(consumed / self.limit, 1.0)

    @property
    def status(self) -> str:
        p = self.pressure
        if p < 0.1:
            return "healthy"
        elif p < 0.3:
            return "moderate"
        elif p < 0.5:
            return "elevated"
        elif p < 0.7:
            return "high"
        elif p < 0.9:
            return "critical"
        else:
            return "overflow"

    def to_dict(self) -> dict:
        return {
            "limit": self.limit,
            "used": self.used,
            "reserved": self.reserved,
            "available": self.available,
            "pressure": round(self.pressure, 3),
            "status": self.status,
            "tool_calls": self.tool_calls,
            "tool_tokens": self.tool_tokens,
            "compression_savings": self.compression_savings,
            "cache_hits": self.cache_hits,
        }


class ContextBudgetManager:
    """Tracks and manages the LLM context window budget across a run.

    Usage:
        budget = ContextBudgetManager(limit=128_000, reserved=8_000)
        budget.add_tool_call(raw_payload, compressed_payload, cache_hit)
        if budget.snapshot.pressure > 0.7:
            # Tell Aperture to be more aggressive
            ...
    """

    def __init__(self, limit: int = 128_000, reserved: int = 8_000):
        self._limit = limit
        self._reserved = reserved
        self._tool_calls: list[dict] = []
        self._total_raw = 0
        self._total_compressed = 0
        self._cache_hits = 0

    def add_tool_call(
        self,
        tool_slug: str,
        raw_payload: object,
        compressed_payload: object,
        cache_hit: bool = False,
    ) -> BudgetSnapshot:
        """Record a tool call and return the updated budget snapshot."""
        raw_tokens = count_tokens(raw_payload).tokens
        compressed_tokens = count_tokens(compressed_payload).tokens
        savings = raw_tokens - compressed_tokens

        self._tool_calls.append({
            "tool_slug": tool_slug,
            "raw_tokens": raw_tokens,
            "compressed_tokens": compressed_tokens,
            "savings": savings,
            "cache_hit": cache_hit,
        })
        self._total_raw += raw_tokens
        self._total_compressed += compressed_tokens
        if cache_hit:
            self._cache_hits += 1

        return self.snapshot

    @property
    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            limit=self._limit,
            used=self._total_compressed,
            reserved=self._reserved,
            tool_calls=len(self._tool_calls),
            tool_tokens=self._total_compressed,
            compression_savings=self._total_raw - self._total_compressed,
            cache_hits=self._cache_hits,
        )

    def get_recommendation(self) -> str:
        """Return a human-readable recommendation based on current pressure."""
        snap = self.snapshot
        if snap.status == "overflow":
            return "CRITICAL: Context window nearly full. Enable maximum compression, drop non-critical fields, or truncate history."
        elif snap.status == "critical":
            return "WARNING: Context window at 70-90%. Switch to low effort mode for remaining calls."
        elif snap.status == "high":
            return "ELEVATED: Context window at 50-70%. Consider more aggressive compression."
        elif snap.status == "elevated":
            return "MODERATE: Context window at 30-50%. Monitor remaining budget."
        else:
            return f"HEALTHY: {snap.available:,} tokens available ({(1-snap.pressure)*100:.0f}% free)."

    def history(self) -> list[dict]:
        """Return the full history of tool calls for analysis."""
        return self._tool_calls.copy()
