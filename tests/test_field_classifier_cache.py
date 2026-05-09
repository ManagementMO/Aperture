"""Cache freshness contract tests.

The classifier cache MUST never inject stale data into the compression
pipeline. These tests assert the four guarantees:

    1. Expired entries are evicted on read (TTL).
    2. Entries cached against a different candidate set are evicted.
    3. Bumping the prompt version invalidates the entire cache automatically.
    4. Timed-out model calls are NEVER cached.
"""

from __future__ import annotations

import time

import pytest

from aperture.compression import field_classifier
from aperture.compression.field_classifier import (
    _CACHE,
    _cache_get,
    _cache_put,
    _cache_key,
    cache_stats,
    classify_fields,
    clear_cache,
)


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    """Each test gets a clean cache and `none` provider so we never reach the
    real network."""
    monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "none")
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    clear_cache()
    yield
    clear_cache()


class TestTTLEviction:
    def test_fresh_entry_returns(self):
        _cache_put("k1", {"avatar_url"}, ["avatar_url", "node_id"], ttl_seconds=10)
        result = _cache_get("k1", ["avatar_url", "node_id"])
        assert result == frozenset({"avatar_url"})

    def test_expired_entry_evicted(self):
        _cache_put("k2", {"avatar_url"}, ["avatar_url", "node_id"], ttl_seconds=0)
        # ttl=0 means already expired by the time we read.
        time.sleep(0.001)
        result = _cache_get("k2", ["avatar_url", "node_id"])
        assert result is None
        assert "k2" not in _CACHE
        assert cache_stats()["expired_evictions"] >= 1


class TestCandidateDriftEviction:
    def test_extra_candidate_invalidates(self):
        _cache_put("k", {"avatar_url"}, ["avatar_url", "node_id"], ttl_seconds=60)
        # A new field appeared in the schema → cache entry is now stale.
        result = _cache_get("k", ["avatar_url", "node_id", "new_field"])
        assert result is None
        assert "k" not in _CACHE
        assert cache_stats()["stale_evictions"] >= 1

    def test_missing_candidate_invalidates(self):
        # Cached keep references a field that no longer exists.
        _cache_put("k", {"avatar_url", "ghost"}, ["avatar_url", "ghost"], ttl_seconds=60)
        # Re-read with a candidate list that's missing `ghost`.
        result = _cache_get("k", ["avatar_url"])
        assert result is None
        assert "k" not in _CACHE


class TestPromptVersionInvalidation:
    def test_key_changes_when_version_changes(self, monkeypatch):
        old_key = _cache_key("hf", "m", "TOOL", "ask", ["f1", "f2"])
        monkeypatch.setattr(field_classifier, "_PROMPT_VERSION", "v999-test")
        new_key = _cache_key("hf", "m", "TOOL", "ask", ["f1", "f2"])
        assert old_key != new_key


class TestTimeoutNotCached:
    def test_timed_out_call_does_not_create_cache_entry(self, monkeypatch):
        # Force the HF path to be selected, with a fake credential.
        monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "huggingface")
        monkeypatch.setenv("HF_API_TOKEN", "test")

        called = {"count": 0}

        def fake_classify_hf(*args, **kwargs):
            called["count"] += 1
            # (keeps, raw_reply, latency_ms, cost, timed_out)
            return set(), "took too long", 999.0, 0.0, True

        monkeypatch.setattr(field_classifier, "_classify_hf", fake_classify_hf)
        clear_cache()

        candidates = ["avatar_url", "node_id"]
        r1 = classify_fields("TOOL", "do something", candidates)
        assert r1.keeps == set()
        assert called["count"] == 1
        # No entry — next call must hit the model again.
        assert cache_stats()["entries"] == 0
        assert cache_stats()["timeout_evictions"] >= 1

        r2 = classify_fields("TOOL", "do something", candidates)
        assert called["count"] == 2  # model called again, not cached
        assert r2.keeps == set()


class TestNonTimeoutCached:
    def test_successful_call_is_cached(self, monkeypatch):
        monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "huggingface")
        monkeypatch.setenv("HF_API_TOKEN", "test")

        called = {"count": 0}

        def fake_classify_hf(*args, **kwargs):
            called["count"] += 1
            return {"avatar_url"}, '["avatar_url"]', 120.0, 0.0, False

        monkeypatch.setattr(field_classifier, "_classify_hf", fake_classify_hf)
        clear_cache()

        candidates = ["avatar_url", "node_id"]
        r1 = classify_fields("TOOL", "do something", candidates)
        assert r1.keeps == {"avatar_url"}
        assert called["count"] == 1
        assert cache_stats()["entries"] == 1

        r2 = classify_fields("TOOL", "do something", candidates)
        assert r2.cached is True
        assert called["count"] == 1  # cache hit — model NOT called again
        assert r2.keeps == {"avatar_url"}


class TestNoStaleInjection:
    """End-to-end: a stale cached keep set must never reach the engine."""

    def test_drifted_candidate_triggers_remiss_not_stale_keep(self, monkeypatch):
        monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "huggingface")
        monkeypatch.setenv("HF_API_TOKEN", "test")

        call_log = []

        def fake_classify_hf(tool_slug, ask, candidates, model, timeout_ms=275):
            call_log.append(set(candidates))
            return {candidates[0]}, "ok", 50.0, 0.0, False

        monkeypatch.setattr(field_classifier, "_classify_hf", fake_classify_hf)
        clear_cache()

        # First call — caches `{avatar_url}` against `[avatar_url, node_id]`.
        classify_fields("TOOL", "task", ["avatar_url", "node_id"])
        assert cache_stats()["entries"] == 1

        # Schema drifted: `node_id` was renamed to `nodeId`. The cached entry
        # now references a field-set that doesn't match the new candidate
        # list. Cache must REMISS — not return the stale entry.
        result = classify_fields("TOOL", "task", ["avatar_url", "nodeId"])
        assert len(call_log) == 2  # model called again, not stale-served
        # And the new keeps must come from the fresh classification, not the
        # cached `{avatar_url}` (which still happens to also match here, but
        # the eviction path was the one that ran).
        assert result.cached is False
