"""Tests for the expanded tokenizer registry."""

from aperture.tokenization import count_tokens


class TestTokenizerRegistry:
    def test_gpt_4o_uses_o200k(self):
        result = count_tokens("hello world", model="gpt-4o")
        assert result.tokenizer == "o200k_base"
        assert result.approximate is False

    def test_gpt_4o_dated_variant_resolves(self):
        result = count_tokens("hello", model="gpt-4o-2024-08-06")
        assert result.tokenizer == "o200k_base"
        assert result.approximate is False

    def test_claude_falls_back_with_approximate_flag(self):
        result = count_tokens("hello", model="claude-opus-4-7")
        assert result.tokenizer == "cl100k_base"
        assert result.approximate is True

    def test_claude_dated_variant(self):
        result = count_tokens("hello", model="claude-3-5-sonnet-20241022")
        assert result.tokenizer == "cl100k_base"
        assert result.approximate is True

    def test_gemini_falls_back_with_approximate_flag(self):
        result = count_tokens("hello", model="gemini-2.5-flash")
        assert result.tokenizer == "cl100k_base"
        assert result.approximate is True

    def test_o3_uses_o200k(self):
        result = count_tokens("hello", model="o3-mini")
        assert result.tokenizer == "o200k_base"
        assert result.approximate is False

    def test_unknown_model_fallback_marked_approximate(self):
        result = count_tokens("hello", model="some-future-model-9000")
        assert result.tokenizer == "cl100k_base"
        assert result.approximate is True

    def test_string_input_works(self):
        # `count_tokens("plain string", ...)` shouldn't double-encode through
        # JSON — a plain string just gets tokenized directly.
        plain = count_tokens("hello world", model="gpt-4o")
        wrapped = count_tokens({"text": "hello world"}, model="gpt-4o")
        assert plain.tokens < wrapped.tokens
