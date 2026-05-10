"""Tests for the BudgetTracker."""

from __future__ import annotations

import pytest

from aperture.schema_optimizer.budget import BudgetTracker


class _FakeUsage:
    def __init__(self, input_tokens=0, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens


def test_records_usage_per_call():
    tracker = BudgetTracker(cap_usd=50.0)
    tracker.record_usage(_FakeUsage(input_tokens=10_000, output_tokens=2_000), model="claude-haiku-4-5")
    summary = tracker.summary()
    assert summary["calls"] == 1
    # Haiku: input $1/1M, output $5/1M → 10_000 * 1/1M + 2_000 * 5/1M = 0.01 + 0.01 = 0.02
    assert summary["total_usd"] == pytest.approx(0.02, abs=1e-6)


def test_summary_groups_by_model():
    tracker = BudgetTracker(cap_usd=50.0)
    tracker.record_usage(_FakeUsage(input_tokens=1000, output_tokens=200), model="claude-haiku-4-5")
    tracker.record_usage(_FakeUsage(input_tokens=1000, output_tokens=200), model="claude-sonnet-4-5")
    by_model = tracker.summary()["by_model"]
    assert "claude-haiku-4-5" in by_model
    assert "claude-sonnet-4-5" in by_model
    assert by_model["claude-haiku-4-5"]["calls"] == 1
    # Sonnet costs more than Haiku for the same tokens
    assert by_model["claude-sonnet-4-5"]["cost_usd"] > by_model["claude-haiku-4-5"]["cost_usd"]


def test_handles_dict_usage_for_replay_mode():
    tracker = BudgetTracker(cap_usd=50.0)
    tracker.record_usage({"input_tokens": 5000, "output_tokens": 1000}, model="claude-haiku-4-5")
    assert tracker.total_usd > 0


def test_handles_none_usage_safely():
    tracker = BudgetTracker(cap_usd=50.0)
    entry = tracker.record_usage(None, model="claude-haiku-4-5")
    assert entry.input_tokens == 0
    assert entry.output_tokens == 0
    assert entry.cost_usd == 0.0


def test_exhausted_when_cap_hit():
    tracker = BudgetTracker(cap_usd=0.005)
    tracker.record_usage(_FakeUsage(input_tokens=10_000, output_tokens=2_000), model="claude-haiku-4-5")
    assert tracker.exhausted() is True
    assert tracker.remaining_usd() == 0.0


def test_unknown_model_uses_default_pricing():
    tracker = BudgetTracker(cap_usd=50.0)
    tracker.record_usage(_FakeUsage(input_tokens=1000, output_tokens=200), model="claude-mystery-99")
    # Default pricing kicks in. Just confirm a real cost was recorded.
    assert tracker.total_usd > 0


def test_cache_read_tokens_charged_at_discount():
    """cache_read tokens are 0.10x base — should be cheaper than identical
    input_tokens at the full rate."""
    tracker_full = BudgetTracker(cap_usd=50.0)
    tracker_cached = BudgetTracker(cap_usd=50.0)
    tracker_full.record_usage(_FakeUsage(input_tokens=10_000), model="claude-haiku-4-5")
    tracker_cached.record_usage(
        _FakeUsage(input_tokens=0, cache_read_input_tokens=10_000),
        model="claude-haiku-4-5",
    )
    assert tracker_cached.total_usd < tracker_full.total_usd
    assert tracker_cached.total_usd == pytest.approx(tracker_full.total_usd * 0.10, rel=0.01)
