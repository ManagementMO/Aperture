"""Deterministic long-text compression."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aperture.compression.path_utils import get_path, set_path
from aperture.compression.profile_loader import CompressionProfile
from aperture.tokenization.token_counter import count_tokens_for_payload


def _extractive_summary(text: str, max_tokens: int) -> str:
    sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    if not sentences:
        return text[: max_tokens * 4]
    summary = ". ".join(sentences[:3])
    if len(summary) < len(text):
        summary += "."
    while count_tokens_for_payload(summary).tokens > max_tokens and len(summary) > 20:
        summary = summary[: max(20, int(len(summary) * 0.8))].rstrip()
    return summary


def _compress_one(payload: Any, profile: CompressionProfile) -> Any:
    if isinstance(payload, list):
        return [_compress_one(item, profile) for item in payload]
    if not isinstance(payload, dict):
        return payload
    output = deepcopy(payload)
    for path, config in profile.summarize_fields.items():
        value = get_path(output, path)
        if not isinstance(value, str):
            continue
        max_tokens = int(config.get("max_tokens", profile.max_string_tokens_without_summary))
        if count_tokens_for_payload(value).tokens <= max_tokens:
            continue
        strategy = config.get("strategy", "extractive")
        if strategy == "none":
            continue
        if strategy == "truncate":
            summary = value[: max_tokens * 4].rstrip()
        else:
            summary = _extractive_summary(value, max_tokens)
        set_path(output, path, summary)
        set_path(output, f"{path}_compressed", True)
    for key, value in list(output.items()):
        output[key] = _compress_one(value, profile)
    return output


def compress_long_text_fields(payload: object, profile: CompressionProfile) -> object:
    """Truncate or extractively summarize long text fields when allowed."""

    return _compress_one(payload, profile)

