"""Anthropic API spend tracking + budget cap for the schema optimizer.

Plan decision #4: validator runs on Haiku with Sonnet spot-check, total
budget ≤$50. This module owns the meter. It reads Anthropic's `usage`
fields off `messages.create()` responses, computes USD using the published
per-model rates, and aborts the validator loop when the cap is hit.

Pricing (USD per 1M tokens) from anthropic.com/pricing as of late 2025.
Update when Anthropic publishes new tiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Pricing per 1M tokens. Two entries per model: input, output.
# cache_read / cache_write surcharges are NOT applied here — the validator
# doesn't use prompt caching (each call has unique tools+prompt) so the
# actual cache_creation_input_tokens is normally 0.
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":   {"input": 1.00,  "output": 5.00},
    "claude-haiku-3-5":   {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4-5":  {"input": 3.00,  "output": 15.00},
    "claude-opus-4-7":    {"input": 15.00, "output": 75.00},
    "default":            {"input": 3.00,  "output": 15.00},
}


def _pricing_for(model: str) -> dict[str, float]:
    if model in _PRICING:
        return _PRICING[model]
    for key in sorted(_PRICING.keys(), key=len, reverse=True):
        if key != "default" and model.startswith(key):
            return _PRICING[key]
    return _PRICING["default"]


@dataclass
class BudgetEntry:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class BudgetTracker:
    """Tracks Anthropic spend across a validator run.

    Usage:
        tracker = BudgetTracker(cap_usd=50.0)
        ...
        # After each anthropic call:
        tracker.record_usage(response.usage, model="claude-haiku-4-5")
        if tracker.exhausted():
            raise BudgetExhausted(tracker.summary())
    """

    cap_usd: float = 50.0
    entries: list[BudgetEntry] = field(default_factory=list)
    total_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def record_usage(self, usage: Any, model: str) -> BudgetEntry:
        """Record one Anthropic call's `response.usage`.

        `usage` may be the SDK's Usage object or a dict (replay mode).
        Returns the BudgetEntry recorded.
        """
        in_tokens = self._field(usage, "input_tokens", 0)
        out_tokens = self._field(usage, "output_tokens", 0)
        # Cache-read tokens are MUCH cheaper; if Anthropic reports them, fold
        # them in at 0.10x base. cache_creation tokens billed at 1.25x base.
        cache_read = self._field(usage, "cache_read_input_tokens", 0)
        cache_write = self._field(usage, "cache_creation_input_tokens", 0)

        prices = _pricing_for(model)
        cost = (
            in_tokens * prices["input"]
            + out_tokens * prices["output"]
            + cache_read * prices["input"] * 0.10
            + cache_write * prices["input"] * 1.25
        ) / 1_000_000

        entry = BudgetEntry(
            model=model,
            input_tokens=in_tokens + cache_read + cache_write,
            output_tokens=out_tokens,
            cost_usd=round(cost, 6),
        )
        self.entries.append(entry)
        self.total_usd = round(self.total_usd + cost, 6)
        self.total_input_tokens += entry.input_tokens
        self.total_output_tokens += entry.output_tokens
        return entry

    def exhausted(self) -> bool:
        return self.total_usd >= self.cap_usd

    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.total_usd)

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.entries),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_usd": round(self.total_usd, 4),
            "cap_usd": self.cap_usd,
            "remaining_usd": round(self.remaining_usd(), 4),
            "by_model": self._by_model(),
        }

    def _by_model(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
            bucket = out.setdefault(
                entry.model,
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += entry.input_tokens
            bucket["output_tokens"] += entry.output_tokens
            bucket["cost_usd"] = round(bucket["cost_usd"] + entry.cost_usd, 6)
        return out

    @staticmethod
    def _field(usage: Any, name: str, default: int = 0) -> int:
        if usage is None:
            return default
        if isinstance(usage, dict):
            return int(usage.get(name, default))
        return int(getattr(usage, name, default) or default)


class BudgetExhausted(RuntimeError):
    """Raised when validator runs out of budget mid-loop."""
