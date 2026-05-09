"""Compression report helpers."""

from __future__ import annotations

from aperture.observability.reports import compression_savings_report
from aperture.types import TokenAttributionEvent


def build_compression_report(events: list[TokenAttributionEvent]) -> str:
    """Return a Markdown compression report from token events."""

    return compression_savings_report(events)

