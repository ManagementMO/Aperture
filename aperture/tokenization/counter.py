"""Token counting with model-specific tokenizer selection."""

import tiktoken

from aperture.contracts import TokenCount
from aperture.tokenization.serializers import stable_json_dumps

# Model -> tokenizer mapping
_REGISTRY: dict[str, str] = {
    "gpt-4": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4.1": "o200k_base",
    "gpt-3.5-turbo": "cl100k_base",
}

_FALLBACK = "cl100k_base"


def _resolve_encoder_name(model: str | None) -> tuple[str, bool]:
    """Return (encoder_name, is_approximate)."""
    if model is None:
        return _FALLBACK, True

    # Exact match
    if model in _REGISTRY:
        return _REGISTRY[model], False

    # Prefix match (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
    for key in sorted(_REGISTRY.keys(), key=len, reverse=True):
        if model.startswith(key):
            return _REGISTRY[key], False

    return _FALLBACK, True


def count_tokens(payload: object, model: str | None = None) -> TokenCount:
    """Count tokens for a payload using the best available tokenizer.

    Args:
        payload: Any JSON-serializable object.
        model: Model name hint (e.g., "gpt-4o"). Falls back to cl100k_base.

    Returns:
        TokenCount with tokens, tokenizer name, and approximate flag.
    """
    encoder_name, approximate = _resolve_encoder_name(model)
    text = stable_json_dumps(payload)

    try:
        enc = tiktoken.get_encoding(encoder_name)
    except KeyError:
        enc = tiktoken.get_encoding(_FALLBACK)
        approximate = True

    tokens = len(enc.encode(text))
    return TokenCount(tokens=tokens, tokenizer=encoder_name, approximate=approximate)
