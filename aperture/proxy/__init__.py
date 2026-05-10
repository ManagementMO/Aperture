"""Aperture MCP proxy.

Sits between an LLM client (Claude Desktop, custom agent, etc.) and
Composio's Tool Router MCP endpoint. The developer points their MCP URL
at this proxy instead of `https://backend.composio.dev/v3/mcp/...`.

This package implements Plan-Agent 1's PR-1 design (transparent forwarder).
Subsequent phases layer in cache (PR 2), token attribution (PR 3), and
schema overlay (PR 4) without changing the proxy's outer shape.

Public API surface is intentionally narrow:
    create_app()   → ASGI app for `uvicorn` or any ASGI server
    main()         → `python -m aperture.proxy` CLI entrypoint
    ProxyConfig    → env-driven configuration
"""

from aperture.proxy.config import ProxyConfig
from aperture.proxy.server import create_app

__all__ = ["ProxyConfig", "create_app"]
