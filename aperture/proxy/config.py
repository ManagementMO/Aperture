"""Proxy configuration from environment variables.

Kept separate from `aperture.config.ApertureConfig` because the proxy has
its own knobs (host, port, upstream URL template, log level) that don't
apply to the SDK runner. The two configs share env namespace; the proxy
reads cache + event-emitter settings via `ApertureConfig.from_env()`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class ProxyConfig:
    """Configuration for `aperture-proxy`.

    All fields are read from env vars at startup; mutating them after the
    proxy is running has no effect (lifespan reads once).
    """

    host: str
    port: int
    composio_mcp_url_template: str
    overlay_path: str | None
    log_level: str
    timeout_seconds: float
    fallback_tokenizer: str  # "auto" | "tiktoken" | "disabled"

    @classmethod
    def from_env(cls) -> "ProxyConfig":
        return cls(
            host=os.getenv("APERTURE_PROXY_HOST", "127.0.0.1"),
            port=int(os.getenv("APERTURE_PROXY_PORT", "8001")),
            # The upstream URL is a template; per-request the proxy substitutes
            # `{server_id}` and `{user_id}` from inbound query params or path.
            # When the inbound URL is the full Composio shape, the proxy can
            # forward verbatim — the template form is for hosted deployments
            # where the proxy is in front of a single Composio account.
            composio_mcp_url_template=os.getenv(
                "APERTURE_COMPOSIO_MCP_URL_TEMPLATE",
                "https://backend.composio.dev/v3/mcp/{server_id}?user_id={user_id}",
            ),
            overlay_path=os.getenv("APERTURE_OVERLAY_PATH"),
            log_level=os.getenv("APERTURE_PROXY_LOG_LEVEL", "INFO").upper(),
            timeout_seconds=float(os.getenv("APERTURE_PROXY_UPSTREAM_TIMEOUT", "30.0")),
            fallback_tokenizer=os.getenv("APERTURE_PROXY_FALLBACK_TOKENIZER", "auto").lower(),
        )

    @staticmethod
    def truthy_env(name: str, default: bool = False) -> bool:
        value = os.getenv(name, "").strip().lower()
        if not value:
            return default
        return value in _TRUTHY
