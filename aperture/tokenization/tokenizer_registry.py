"""Tokenizer selection for supported model families."""

from __future__ import annotations

from dataclasses import dataclass


TOKENIZER_BY_MODEL = {
    "gpt-4.1": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-5": "o200k_base",
    "gpt-5-mini": "o200k_base",
    "claude-sonnet-4": "anthropic_count_tokens",
    "claude-3-5-sonnet": "anthropic_count_tokens",
    "unknown": "cl100k_base",
}


@dataclass(frozen=True)
class TokenizerSelection:
    tokenizer: str
    approximate: bool


def select_tokenizer(model: str | None = None, tokenizer_hint: str | None = None) -> TokenizerSelection:
    """Select a tokenizer name and whether the count should be considered approximate."""

    if tokenizer_hint:
        return TokenizerSelection(tokenizer_hint, tokenizer_hint == "fallback")
    if not model:
        return TokenizerSelection(TOKENIZER_BY_MODEL["unknown"], True)
    if model in TOKENIZER_BY_MODEL:
        tokenizer = TOKENIZER_BY_MODEL[model]
        return TokenizerSelection(tokenizer, tokenizer.startswith("anthropic_"))
    model_lower = model.lower()
    if "gpt-4o" in model_lower or "gpt-5" in model_lower:
        return TokenizerSelection("o200k_base", False)
    if "gpt" in model_lower:
        return TokenizerSelection("cl100k_base", False)
    if "claude" in model_lower:
        return TokenizerSelection("anthropic_count_tokens", True)
    return TokenizerSelection(TOKENIZER_BY_MODEL["unknown"], True)

