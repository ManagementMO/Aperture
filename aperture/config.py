"""Configuration loading for Aperture."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ApertureConfig:
    """Runtime configuration for local and live Aperture usage."""

    mode: str = "balanced"
    raw_store_path: Path = Path(".aperture/raw_store")
    event_sink_path: Path = Path("reports/events.jsonl")
    redis_url: str | None = None
    composio_api_key: str | None = None
    composio_user_id: str = "default"
    enable_live_tests: bool = False

    @classmethod
    def from_env(cls) -> "ApertureConfig":
        """Load Aperture configuration from environment variables."""

        return cls(
            mode=os.getenv("APERTURE_MODE", "balanced"),
            raw_store_path=Path(os.getenv("APERTURE_RAW_STORE_PATH", ".aperture/raw_store")),
            event_sink_path=Path(os.getenv("APERTURE_EVENT_SINK_PATH", "reports/events.jsonl")),
            redis_url=os.getenv("APERTURE_REDIS_URL") or None,
            composio_api_key=os.getenv("COMPOSIO_API_KEY") or None,
            composio_user_id=os.getenv("COMPOSIO_USER_ID", "default"),
            enable_live_tests=_bool_env("APERTURE_ENABLE_LIVE_TESTS", False),
        )

