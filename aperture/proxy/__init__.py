"""Aperture MCP proxy.

Sits between an LLM client (Claude Desktop, custom agent, etc.) and
Composio's Tool Router MCP endpoint. The developer points their MCP URL
at this proxy instead of `https://backend.composio.dev/tool_router/.../mcp`.

This package forwards through Composio while routing meta-tool calls through
cache, token attribution, and schema-overlay enrichment layers.

Public API surface is intentionally narrow:
    create_app()   → ASGI app for `uvicorn` or any ASGI server
    main()         → `python -m aperture.proxy` CLI entrypoint
    ProxyConfig    → env-driven configuration
"""

from aperture.proxy.config import ProxyConfig
from aperture.proxy.server import create_app

__all__ = ["ProxyConfig", "create_app"]
