"""Token counting primitives."""

from __future__ import annotations

from aperture.tokenization.serializers import stable_serialize_payload
from aperture.tokenization.tokenizer_registry import select_tokenizer
from aperture.types import TokenCount


def _fallback_count(text: str) -> int:
    # Conservative approximation for environments without provider tokenizers.
    return max(1, (len(text) + 3) // 4)


def count_tokens_for_payload(
    payload: object,
    model: str | None = None,
    tokenizer_hint: str | None = None,
) -> TokenCount:
    """Return token count, tokenizer name, approximation flag, and byte size."""

    serialized = stable_serialize_payload(payload)
    selection = select_tokenizer(model, tokenizer_hint)
    approximate = selection.approximate

    if selection.tokenizer.startswith("anthropic_"):
        tokens = _fallback_count(serialized)
        approximate = True
    else:
        try:
            import tiktoken

            encoding = tiktoken.get_encoding(selection.tokenizer)
            tokens = len(encoding.encode(serialized))
        except Exception:
            tokens = _fallback_count(serialized)
            approximate = True

    return TokenCount(
        tokens=tokens,
        tokenizer=selection.tokenizer,
        tokenizer_is_approximate=approximate,
        payload_bytes=len(serialized.encode("utf-8")),
    )

