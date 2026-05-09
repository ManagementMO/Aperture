"""Tests for the optional model-tier field classifier.

These run hermetically — no real network calls. Provider availability is
mocked via env vars so the classifier picks `none` and returns empty sets.
"""

import os

import pytest

from aperture.compression import field_classifier
from aperture.compression.field_classifier import (
    _candidate_fields,
    _parse_keeps,
    classifier_health,
    classify_fields,
    clear_cache,
)


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "none")
    clear_cache()
    yield
    clear_cache()


class TestCandidateExtraction:
    def test_only_denied_names_are_candidates(self):
        cands = _candidate_fields(["title", "avatar_url", "user.gravatar_id", "id"])
        assert "avatar_url" in cands
        assert "gravatar_id" in cands
        assert "title" not in cands
        assert "id" not in cands  # not in denial list

    def test_dedupes(self):
        cands = _candidate_fields(["avatar_url", "user.avatar_url"])
        assert cands.count("avatar_url") == 1


class TestParseKeeps:
    def test_json_array(self):
        keeps = _parse_keeps('Output: ["avatar_url", "clone_url"]', {"avatar_url", "clone_url", "node_id"})
        assert keeps == {"avatar_url", "clone_url"}

    def test_only_allowed_names_pass_through(self):
        keeps = _parse_keeps('["avatar_url", "made_up_field"]', {"avatar_url"})
        assert keeps == {"avatar_url"}

    def test_prose_response_rejected(self):
        # Tiny models love to write Python. Rejecting prose entirely is
        # safer than greedy substring matching.
        keeps = _parse_keeps("the agent needs avatar_url here", {"avatar_url", "node_id"})
        assert keeps == set()
        keeps = _parse_keeps("def foo(): return ['avatar_url']", {"avatar_url"})
        assert keeps == set()

    def test_invalid_json_returns_empty(self):
        keeps = _parse_keeps("[broken json", {"avatar_url"})
        assert keeps == set()

    def test_extra_prose_around_array_still_parses(self):
        keeps = _parse_keeps('Output: ["avatar_url"] ', {"avatar_url"})
        assert keeps == {"avatar_url"}


class TestClassifyFields:
    def test_disabled_returns_empty(self):
        result = classify_fields("X", "do something", ["avatar_url"], enabled=False)
        assert result.keeps == set()
        assert not result.available

    def test_no_ask_returns_empty(self):
        result = classify_fields("X", "", ["avatar_url"])
        assert result.keeps == set()

    def test_no_candidates_returns_empty(self):
        # Field names that aren't in the denial list aren't candidates.
        result = classify_fields("X", "find them", ["title", "id"])
        assert result.keeps == set()

    def test_provider_none_returns_empty(self, monkeypatch):
        monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "none")
        result = classify_fields("X", "show avatars", ["avatar_url"])
        assert result.keeps == set()

    def test_no_credentials_returns_empty(self):
        # No HF token, no Anthropic key — provider auto-degrades.
        result = classify_fields("X", "show avatars", ["avatar_url"], provider="huggingface")
        assert result.keeps == set()
        assert not result.available

    def test_cache_records_traces(self, monkeypatch):
        monkeypatch.setenv("APERTURE_CLASSIFIER_PROVIDER", "huggingface")
        clear_cache()
        # First call — degrades, caches empty.
        classify_fields("GH", "show avatars", ["avatar_url"], provider="huggingface")
        # Second call — cached.
        result = classify_fields("GH", "show avatars", ["avatar_url"], provider="huggingface")
        assert result.cached


class TestClassifierHealth:
    def test_health_reports_provider_state(self):
        h = classifier_health()
        assert h["selected_provider"] in ("huggingface", "anthropic", "none")
        assert "hf_default_model" in h
        assert "anthropic_default_model" in h

    def test_health_reports_cache_size(self):
        clear_cache()
        h = classifier_health()
        assert h["cache_entries"] == 0


class TestPromptShape:
    """The HF prompt is few-shot because we use the base (non-instruct) Gemma.
    Make sure the structure stays stable so a model swap doesn't break it."""

    def test_few_shot_prompt_has_three_examples(self):
        from aperture.compression.field_classifier import _hf_few_shot_prompt
        prompt = _hf_few_shot_prompt("FOO_BAR", "do the thing", ["avatar_url"])
        assert prompt.count("TOOL:") >= 4  # 3 exemplars + the live request
        assert prompt.count("KEEP:") >= 4
        assert prompt.endswith("KEEP:")

    def test_anthropic_prompt_includes_candidates(self):
        from aperture.compression.field_classifier import _anthropic_prompt
        prompt = _anthropic_prompt("FOO", "task", ["avatar_url", "node_id"])
        assert "avatar_url" in prompt
        assert "node_id" in prompt
