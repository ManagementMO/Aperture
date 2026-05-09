"""Model-facing compression envelope builder."""

from __future__ import annotations

from aperture.types import CompressionContext


def build_compression_envelope(
    compressed_payload: object,
    *,
    raw_tokens: int,
    compressed_tokens: int,
    tokens_saved: int,
    compression_ratio: float,
    raw_reference_id: str | None,
    omitted_fields: list[str],
    context: CompressionContext,
) -> object:
    """Wrap compressed result with metadata visible to the model."""

    return {
        "aperture_compressed": True,
        "tool_slug": context.tool_slug,
        "data": compressed_payload,
        "omitted_fields": sorted(set(omitted_fields)),
        "raw_reference_id": raw_reference_id,
        "raw_available": raw_reference_id is not None,
        "raw_retrieval_hint": "Use raw_reference_id if exact omitted fields are needed." if raw_reference_id else None,
        "compression": {
            "raw_tokens": raw_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": tokens_saved,
            "compression_ratio": compression_ratio,
        },
    }

