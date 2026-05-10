"""Tests for TokenizerService — async tokenizer with LRU cache."""

from __future__ import annotations

import pytest

from aperture.proxy.tokenize import TokenizerService


@pytest.mark.asyncio
async def test_count_returns_token_count_with_correct_shape():
    svc = TokenizerService()
    count = await svc.count("hello world", model="gpt-4o")
    assert count.tokens > 0
    assert count.tokenizer
    assert isinstance(count.tokenizer_is_approximate, bool)
    assert count.payload_bytes > 0


@pytest.mark.asyncio
async def test_count_caches_repeated_calls():
    svc = TokenizerService()
    await svc.count({"a": 1, "b": 2}, model="gpt-4o")
    await svc.count({"a": 1, "b": 2}, model="gpt-4o")
    stats = svc.stats()
    assert stats["hits"] >= 1
    assert stats["entries"] >= 1


@pytest.mark.asyncio
async def test_distinct_payloads_produce_distinct_cache_entries():
    svc = TokenizerService()
    await svc.count({"a": 1}, model="gpt-4o")
    await svc.count({"a": 2}, model="gpt-4o")
    stats = svc.stats()
    assert stats["entries"] >= 2


@pytest.mark.asyncio
async def test_distinct_models_produce_distinct_cache_entries():
    svc = TokenizerService()
    await svc.count({"a": 1}, model="gpt-4o")
    await svc.count({"a": 1}, model="claude-haiku-4-5")
    stats = svc.stats()
    assert stats["entries"] >= 2


@pytest.mark.asyncio
async def test_schedule_count_invokes_callback():
    svc = TokenizerService()
    seen = []

    def on_done(count):
        seen.append(count.tokens)

    task = svc.schedule_count("hello", model="gpt-4o", on_complete=on_done)
    await task
    assert len(seen) == 1
    assert seen[0] > 0


@pytest.mark.asyncio
async def test_schedule_count_swallows_callback_exceptions():
    svc = TokenizerService()

    def boom(_count):
        raise RuntimeError("callback fail")

    task = svc.schedule_count("hello", model="gpt-4o", on_complete=boom)
    # Must not raise even though the callback does.
    result = await task
    assert result is not None  # tokenization itself succeeded
