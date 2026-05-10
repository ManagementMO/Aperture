"""Token counting primitives."""

from __future__ import annotations

from aperture.tokenization.anthropic_tokenizer import count_anthropic_tokens, is_enabled
from aperture.tokenization.serializers import stable_serialize_payload
from aperture.tokenization.tokenizer_registry import select_tokenizer
from aperture.types import TokenCount

# Default cl100k fallback when tiktoken can't load the encoding or when the
# Anthropic API path is disabled / unavailable. The chars/4 heuristic is
# accurate to within ~10% on English prose; we mark it `approximate=True`
# so downstream telemetry can distinguish real counts from estimates.
_DEFAULT_FALLBACK_ENCODING = "cl100k_base"


def _fallback_count(text: str) -> int:
    # Conservative approximation for environments without provider tokenizers.
    return max(1, (len(text) + 3) // 4)


def _tiktoken_count(text: str, encoding_name: str) -> int | None:
    """Return real tiktoken count, or None on failure (caller falls back)."""

    try:
        import tiktoken

        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        return None


def count_tokens_for_payload(
    payload: object,
    model: str | None = None,
    tokenizer_hint: str | None = None,
) -> TokenCount:
    """Return token count, tokenizer name, approximation flag, and byte size.

    Resolution order for Anthropic-family models (anthropic_count_tokens):
        1. If APERTURE_USE_ANTHROPIC_TOKENIZER=true and ANTHROPIC_API_KEY set
           → call `client.messages.count_tokens(...)` for a real count.
        2. Else → cl100k_base via tiktoken (close approximation, ~5-10% error).
        3. Else → chars/4 fallback. All non-(1) paths set `approximate=True`.

    Resolution order for everything else (cl100k_base, o200k_base, etc.):
        1. tiktoken with the registered encoding.
        2. cl100k_base via tiktoken.
        3. chars/4 fallback.
    """

    serialized = stable_serialize_payload(payload)
    selection = select_tokenizer(model, tokenizer_hint)
    approximate = selection.approximate

    tokens: int | None = None
    tokenizer_name = selection.tokenizer

    if selection.tokenizer.startswith("anthropic_"):
        # Path 1: real Anthropic tokenizer (opt-in).
        if is_enabled() and model:
            anthropic_count = count_anthropic_tokens(serialized, model)
            if anthropic_count is not None:
                tokens = anthropic_count
                approximate = False
                tokenizer_name = "anthropic_count_tokens"
        # Path 2: tiktoken cl100k fallback for Claude models when Anthropic path
        # is unavailable. More accurate than chars/4; still marked approximate.
        if tokens is None:
            tokens = _tiktoken_count(serialized, _DEFAULT_FALLBACK_ENCODING)
            if tokens is not None:
                tokenizer_name = f"{_DEFAULT_FALLBACK_ENCODING} (claude-fallback)"
                approximate = True
        # Path 3: chars/4 last-resort.
        if tokens is None:
            tokens = _fallback_count(serialized)
            approximate = True
    else:
        # OpenAI-family models: tiktoken with registered encoding, then cl100k
        # fallback, then chars/4.
        tokens = _tiktoken_count(serialized, selection.tokenizer)
        if tokens is None and selection.tokenizer != _DEFAULT_FALLBACK_ENCODING:
            tokens = _tiktoken_count(serialized, _DEFAULT_FALLBACK_ENCODING)
            approximate = True
        if tokens is None:
            tokens = _fallback_count(serialized)
            approximate = True

    return TokenCount(
        tokens=tokens,
        tokenizer=tokenizer_name,
        tokenizer_is_approximate=approximate,
        payload_bytes=len(serialized.encode("utf-8")),
    )

