"""Tests for tokenization modules."""

import pytest

from aperture.tokenization import count_tokens, stable_json_dumps


class TestStableJsonDumps:
    def test_deterministic_sorting(self):
        a = {"z": 1, "a": 2, "b": {"c": 3, "a": 4}}
        b = {"b": {"a": 4, "c": 3}, "a": 2, "z": 1}
        assert stable_json_dumps(a) == stable_json_dumps(b)

    def test_unicode_preserved(self):
        payload = {"message": "Hello 世界 🌍"}
        result = stable_json_dumps(payload)
        assert "世界" in result
        assert "🌍" in result

    def test_compact_separators(self):
        payload = {"a": 1, "b": 2}
        result = stable_json_dumps(payload)
        assert ", " not in result  # no spaces after commas
        assert ": " not in result  # no spaces after colons

    def test_dataclass_support(self):
        from dataclasses import dataclass

        @dataclass
        class Item:
            name: str
            value: int

        payload = {"item": Item("test", 42)}
        result = stable_json_dumps(payload)
        assert '"name":"test"' in result


class TestCountTokens:
    def test_basic_count(self):
        result = count_tokens({"test": "hello"})
        assert result.tokens > 0
        assert result.tokenizer == "cl100k_base"
        assert result.approximate is True  # no model hint

    def test_model_hint(self):
        result = count_tokens({"test": "hello"}, model="gpt-4o")
        assert result.tokens > 0
        assert result.tokenizer == "o200k_base"
        assert result.approximate is False

    def test_unknown_model_fallback(self):
        result = count_tokens({"test": "hello"}, model="some-unknown-model-v99")
        assert result.tokens > 0
        assert result.approximate is True

    def test_deterministic_count(self):
        payload = {"b": 2, "a": 1}
        r1 = count_tokens(payload)
        r2 = count_tokens(payload)
        assert r1.tokens == r2.tokens

    def test_empty_payload(self):
        result = count_tokens({})
        assert result.tokens >= 0
