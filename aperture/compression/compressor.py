"""Full schema-aware compression pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from aperture.compression.deduplication import deduplicate_repeated_objects
from aperture.compression.envelope import build_compression_envelope
from aperture.compression.field_pruning import prune_fields
from aperture.compression.flattening import flatten_fields
from aperture.compression.list_compaction import compact_lists
from aperture.compression.profile_loader import load_compression_profile
from aperture.compression.raw_store import store_raw_output
from aperture.compression.text_summarization import compress_long_text_fields
from aperture.observability.event_emitter import emit_token_event
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import CompressionContext, CompressionResult, TokenAttributionEvent


def _event(
    context: CompressionContext,
    raw_count,
    compressed_count,
    tokens_saved: int,
    compression_ratio: float,
) -> TokenAttributionEvent:
    return TokenAttributionEvent(
        event_type="tool_output_compression",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=context.project_id,
        user_id=context.user_id,
        session_id=context.session_id,
        connected_account_id=context.connected_account_id,
        toolkit_slug=context.toolkit_slug,
        tool_slug=context.tool_slug,
        meta_tool_slug=None,
        payload_kind="compressed",
        model=context.model,
        tokenizer=compressed_count.tokenizer,
        tokenizer_is_approximate=compressed_count.tokenizer_is_approximate or raw_count.tokenizer_is_approximate,
        raw_payload_bytes=raw_count.payload_bytes,
        compressed_payload_bytes=compressed_count.payload_bytes,
        raw_tokens=raw_count.tokens,
        compressed_tokens=compressed_count.tokens,
        input_tokens_contributed=compressed_count.tokens,
        tokens_saved=tokens_saved,
        compression_ratio=compression_ratio,
        cache_status=None,
        aperture_version="0.1.0",
    )


def compress_tool_output(raw_payload: object, context: CompressionContext) -> CompressionResult:
    """Run the full compression pipeline for a tool output."""

    profile = load_compression_profile(context.tool_slug)
    mode = "off" if context.mode == "off" else context.mode or profile.mode
    if mode not in {"off", "shadow", "safe", "balanced"}:
        mode = profile.mode if profile.mode in {"safe", "balanced"} else "safe"

    raw_count = count_tokens_for_payload(raw_payload, context.model)
    if mode == "off":
        return CompressionResult(
            compressed_payload=raw_payload,
            raw_tokens=raw_count.tokens,
            compressed_tokens=raw_count.tokens,
            tokens_saved=0,
            compression_ratio=1.0,
            raw_reference_id=None,
            strategy="off",
            omitted_fields=[],
            warnings=[],
        )

    raw_reference_id = store_raw_output(raw_payload, context) if profile.raw_reference else None
    working_payload, omitted_fields = prune_fields(raw_payload, profile)
    if mode in {"balanced", "shadow"}:
        working_payload = flatten_fields(working_payload, profile)
        working_payload = compact_lists(working_payload, profile)
        working_payload = deduplicate_repeated_objects(working_payload, profile)
        working_payload = compress_long_text_fields(working_payload, profile)

    provisional = {
        "aperture_compressed": True,
        "tool_slug": context.tool_slug,
        "data": working_payload,
        "omitted_fields": sorted(set(omitted_fields)),
        "raw_reference_id": raw_reference_id,
    }
    provisional_count = count_tokens_for_payload(provisional, context.model)
    tokens_saved = max(0, raw_count.tokens - provisional_count.tokens)
    ratio = provisional_count.tokens / raw_count.tokens if raw_count.tokens else 1.0
    envelope = build_compression_envelope(
        working_payload,
        raw_tokens=raw_count.tokens,
        compressed_tokens=provisional_count.tokens,
        tokens_saved=tokens_saved,
        compression_ratio=ratio,
        raw_reference_id=raw_reference_id,
        omitted_fields=omitted_fields,
        context=context,
    )
    final_count = count_tokens_for_payload(envelope, context.model)
    final_saved = max(0, raw_count.tokens - final_count.tokens)
    final_ratio = final_count.tokens / raw_count.tokens if raw_count.tokens else 1.0

    emit_token_event(_event(context, raw_count, final_count, final_saved, final_ratio))

    return CompressionResult(
        compressed_payload=raw_payload if mode == "shadow" else envelope,
        raw_tokens=raw_count.tokens,
        compressed_tokens=final_count.tokens,
        tokens_saved=final_saved,
        compression_ratio=final_ratio,
        raw_reference_id=raw_reference_id,
        strategy=mode,
        omitted_fields=sorted(set(omitted_fields)),
        warnings=[],
    )

