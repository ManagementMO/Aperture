"""Token counting with model-specific tokenizer selection.

We resolve a model name to a tokenizer in three steps:

1. Exact match against a curated registry.
2. Prefix match (longest first), so `gpt-4o-2024-08-06` resolves to `gpt-4o`.
3. Fallback to `cl100k_base` with `approximate=True` so callers know.

Anthropic and Google do not publish a public tokenizer that we can ship in
`tiktoken`. For those we fall back to `cl100k_base`, which is known to be
within ~5–10% on prose, closer on code. The `approximate` flag stays True
so the dashboard can mark these counts as estimates.
"""

import tiktoken

from aperture.contracts import TokenCount
from aperture.tokenization.serializers import stable_json_dumps

# Curated model → tokenizer mapping. Most specific first (long prefixes win).
_REGISTRY: dict[str, str] = {
    # OpenAI gpt-5 family (preview names — bucketed under o200k for now)
    "gpt-5": "o200k_base",
    "gpt-5-mini": "o200k_base",
    "gpt-5-nano": "o200k_base",
    # OpenAI gpt-4 family
    "gpt-4.1": "o200k_base",
    "gpt-4.1-mini": "o200k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    # OpenAI o-series reasoning models
    "o3-mini": "o200k_base",
    "o3": "o200k_base",
    "o1-mini": "o200k_base",
    "o1": "o200k_base",
    # OpenAI legacy
    "gpt-3.5-turbo": "cl100k_base",
    "text-embedding-3-large": "cl100k_base",
    "text-embedding-3-small": "cl100k_base",
    # Anthropic — no public tokenizer, cl100k_base is the closest free
    # approximation (Claude tokenizes English text within ~5% of OpenAI BPE).
    "claude-opus-4-7": "cl100k_base",
    "claude-opus-4-6": "cl100k_base",
    "claude-opus-4-5": "cl100k_base",
    "claude-sonnet-4-6": "cl100k_base",
    "claude-sonnet-4-5": "cl100k_base",
    "claude-haiku-4-5": "cl100k_base",
    "claude-3-7-sonnet": "cl100k_base",
    "claude-3-5-sonnet": "cl100k_base",
    "claude-3-5-haiku": "cl100k_base",
    "claude-3-opus": "cl100k_base",
    "claude-3-sonnet": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    # Google Gemini — same fallback rationale
    "gemini-2.5-pro": "cl100k_base",
    "gemini-2.5-flash": "cl100k_base",
    "gemini-1.5-pro": "cl100k_base",
    "gemini-1.5-flash": "cl100k_base",
    # DeepSeek / Mistral / Llama — cl100k as a generic BPE estimate
    "deepseek-v3": "cl100k_base",
    "deepseek-r1": "cl100k_base",
    "mistral-large": "cl100k_base",
    "llama-3.1": "cl100k_base",
    "llama-3": "cl100k_base",
}

# Models for which we have an exact tokenizer (NOT approximate).
_EXACT_PREFIXES = ("gpt-", "o1", "o3", "text-embedding-")

_FALLBACK = "cl100k_base"


def _is_exact(model_key: str) -> bool:
    return model_key.startswith(_EXACT_PREFIXES)


def _resolve_encoder_name(model: str | None) -> tuple[str, bool]:
    """Return (encoder_name, is_approximate)."""
    if model is None:
        return _FALLBACK, True

    if model in _REGISTRY:
        return _REGISTRY[model], not _is_exact(model)

    # Prefix match — longest key first so `gpt-4o-2024-08-06` → `gpt-4o`.
    for key in sorted(_REGISTRY.keys(), key=len, reverse=True):
        if model.startswith(key):
            return _REGISTRY[key], not _is_exact(key)

    return _FALLBACK, True


def count_tokens(payload: object, model: str | None = None) -> TokenCount:
    """Count tokens for a payload using the best available tokenizer.

    Args:
        payload: Any JSON-serializable object (or a raw string).
        model: Model name hint. Falls back to `cl100k_base` with the
            `approximate` flag set when the model is unknown or doesn't have
            a public tokenizer (Claude, Gemini, etc.).

    Returns:
        TokenCount with the integer token count, the tokenizer used, and a
        flag indicating whether the count is approximate.
    """
    encoder_name, approximate = _resolve_encoder_name(model)
    text = payload if isinstance(payload, str) else stable_json_dumps(payload)

    try:
        enc = tiktoken.get_encoding(encoder_name)
    except KeyError:
        enc = tiktoken.get_encoding(_FALLBACK)
        approximate = True

    tokens = len(enc.encode(text))
    return TokenCount(tokens=tokens, tokenizer=encoder_name, approximate=approximate)
