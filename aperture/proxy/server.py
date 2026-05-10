"""MCP proxy server.

PR 1 (this file): transparent forwarder. Every `tools/list` and `tools/call`
is forwarded byte-for-byte to Composio's MCP URL. No interception, no cache,
no tokenization, no overlay.

PR 2 will add `aperture/proxy/router.py` and `aperture/proxy/intercept/*.py`
to fan out by meta-tool slug. PR 3 wires `aperture/proxy/tokenize.py` and
`aperture/proxy/attribution.py`. PR 4 adds `aperture/proxy/overlay.py`.

The server is built on `mcp.server.lowlevel.Server` (NOT FastMCP's decorator
API) because the tool list is upstream-defined dynamic — Composio publishes
the tools, we just relay them. FastMCP's `@mcp.tool` decorator forces static
declarations.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from aperture import __version__
from aperture.proxy.config import ProxyConfig
from aperture.proxy.upstream import UpstreamClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(server: Server) -> AsyncIterator[dict[str, Any]]:
    """Construct shared resources once and tear down on shutdown.

    Per Plan-Agent 1 §2: the lifespan owns the `UpstreamClient` and (later)
    the `SessionRegistry`, the schema overlay, and the tokenizer service.
    PR 1 only owns the upstream client.
    """
    cfg = ProxyConfig.from_env()
    upstream = UpstreamClient(
        mcp_url=cfg.composio_mcp_url_template,
        timeout_seconds=cfg.timeout_seconds,
    )
    logger.info(
        "aperture proxy v%s starting; upstream=%s",
        __version__,
        cfg.composio_mcp_url_template,
    )
    try:
        yield {"upstream": upstream, "config": cfg}
    finally:
        await upstream.aclose()
        logger.info("aperture proxy stopped")


def _build_mcp_server() -> Server:
    """Construct the low-level MCP server with `tools/list` and `tools/call` handlers."""

    server: Server = Server(
        name="aperture-proxy",
        version=__version__,
        instructions=(
            "Aperture: token-efficiency layer over Composio. Forwards meta-tool "
            "requests to Composio's MCP endpoint while measuring + caching them."
        ),
        lifespan=_lifespan,
    )

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        ctx = server.request_context.lifespan_context
        upstream: UpstreamClient = ctx["upstream"]
        # PR 1: forward verbatim. PR 4 will apply the schema overlay here so the
        # LLM sees rewritten descriptions for tools that have an accepted overlay
        # entry.
        # Headers come from the inbound MCP request; the lowlevel Server exposes
        # them via request_context.request when the transport sets it. For PR 1
        # we pass an empty header dict — Composio will reject without auth, but
        # that's the next concern (PR 2 wires header pass-through end-to-end).
        return await upstream.list_tools(headers={})

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.ContentBlock]:
        ctx = server.request_context.lifespan_context
        upstream: UpstreamClient = ctx["upstream"]
        # PR 1: forward verbatim, return whatever Composio returned.
        # PR 2 dispatches by meta-tool slug into intercept handlers; PR 3 emits
        # TokenAttributionEvent here; PR 4 applies the overlay.
        result = await upstream.call_tool(name, arguments, headers={})
        return list(result.content)

    return server


def create_app() -> Any:
    """Return a Starlette ASGI app wrapping the MCP server.

    Use with `uvicorn aperture.proxy:create_app --factory`.

    Plan-Agent 1's design uses `StreamableHTTPSessionManager` with `stateless=True`
    so the proxy can be horizontally scaled. The session manager handles MCP's
    SSE/Streamable-HTTP transport details; we only deal with the high-level
    `Server` decorators above.
    """

    from starlette.applications import Starlette
    from starlette.routing import Mount

    server = _build_mcp_server()
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=True,
        json_response=False,  # default SSE; flip to JSON-only for testing
    )

    @asynccontextmanager
    async def _starlette_lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(
        debug=False,
        routes=[Mount("/mcp", app=session_manager.handle_request)],
        lifespan=_starlette_lifespan,
    )
    return app
