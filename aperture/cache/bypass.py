"""Cache bypass parsing."""

from __future__ import annotations

from typing import Any


def cache_bypass_requested(headers: dict[str, str] | None = None, metadata: dict[str, Any] | None = None) -> bool:
    """Return whether a request explicitly bypasses Aperture cache."""

    if headers:
        for key, value in headers.items():
            if key.lower() == "x-aperture-cache-bypass" and str(value).lower() in {"1", "true", "yes"}:
                return True
    if metadata and metadata.get("aperture_cache_bypass") is True:
        return True
    return False

