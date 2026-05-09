"""Compression profile loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CompressionProfile:
    tool_slug: str
    mode: str = "safe"
    drop_nulls: bool = True
    drop_empty_strings: bool = True
    drop_empty_arrays: bool = True
    drop_obvious_api_urls: bool = True
    raw_reference: bool = True
    max_string_tokens_without_summary: int = 300
    preserve_fields: list[str] = field(default_factory=list)
    drop_fields: list[str] = field(default_factory=list)
    flatten: dict[str, str] = field(default_factory=dict)
    compact_lists: dict[str, str] = field(default_factory=dict)
    summarize_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    deduplicate: list[str] = field(default_factory=list)


def _profile_path() -> Path:
    return Path(__file__).with_name("profiles.yaml")


def _load_yaml(path: Path | None = None) -> dict[str, Any]:
    selected = path or _profile_path()
    with selected.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if data.get("version") != 1:
        raise ValueError("Compression profile file must have version: 1")
    return data


def _build_profile(tool_slug: str, raw: dict[str, Any]) -> CompressionProfile:
    return CompressionProfile(
        tool_slug=tool_slug,
        mode=raw.get("mode", "safe"),
        drop_nulls=bool(raw.get("drop_nulls", True)),
        drop_empty_strings=bool(raw.get("drop_empty_strings", True)),
        drop_empty_arrays=bool(raw.get("drop_empty_arrays", True)),
        drop_obvious_api_urls=bool(raw.get("drop_obvious_api_urls", True)),
        raw_reference=bool(raw.get("raw_reference", True)),
        max_string_tokens_without_summary=int(raw.get("max_string_tokens_without_summary", 300)),
        preserve_fields=list(raw.get("preserve_fields") or []),
        drop_fields=list(raw.get("drop_fields") or []),
        flatten=dict(raw.get("flatten") or {}),
        compact_lists=dict(raw.get("compact_lists") or {}),
        summarize_fields=dict(raw.get("summarize_fields") or {}),
        deduplicate=list(raw.get("deduplicate") or []),
    )


def load_compression_profile(tool_slug: str, path: Path | None = None) -> CompressionProfile:
    """Return tool-specific profile or default safe profile."""

    data = _load_yaml(path)
    default = dict(data.get("default") or {})
    tool_overrides = dict((data.get("tools") or {}).get(tool_slug) or {})
    merged = {**default, **tool_overrides}
    return _build_profile(tool_slug, merged)

