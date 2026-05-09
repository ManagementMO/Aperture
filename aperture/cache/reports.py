"""Cache report helpers."""

from __future__ import annotations

from aperture.observability.reports import cache_savings_report
from aperture.types import CacheEvent


def build_cache_report(events: list[CacheEvent]) -> str:
    """Return a Markdown cache savings report."""

    return cache_savings_report(events)

