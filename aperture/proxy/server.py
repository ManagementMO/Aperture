"""MCP proxy server.

This is the Streamable-HTTP MCP entry point. It forwards auth/context
headers to Composio, substitutes the upstream tool-router session id, routes
`tools/call` through `router.dispatch`, applies schema overlays to schema
responses, emits token attribution in the background, and wires Redis or an
in-memory cache store during lifespan startup.

The server is built on `mcp.server.lowlevel.Server` (NOT FastMCP's decorator
API) because the tool list is upstream-defined dynamic — Composio publishes
the tools, we just relay them. FastMCP's `@mcp.tool` decorator forces static
declarations.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, AsyncIterator

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from aperture import __version__
from aperture.cache.bypass import cache_bypass_requested
from aperture.cache.redis_store import InMemoryCacheStore, RedisCacheStore
from aperture.config import ApertureConfig
from aperture.proxy.attribution import emit_meta_tool_event
from aperture.proxy.cache_bridge import set_default_store
from aperture.proxy.config import ProxyConfig
from aperture.proxy.overlay import SchemaOverlay, default_overlay_path
from aperture.proxy.router import dispatch
from aperture.proxy.session import SessionRegistry
from aperture.proxy.tokenize import TokenizerService
from aperture.proxy.upstream import UpstreamClient

logger = logging.getLogger(__name__)

_HOP_BY_HOP_HEADERS = {
    "accept",
    "accept-encoding",
    "connection",
    "content-length",
    "content-type",
    "host",
    "keep-alive",
    "transfer-encoding",
}


@asynccontextmanager
async def _lifespan(server: Server) -> AsyncIterator[dict[str, Any]]:
    """Construct shared resources once and tear down on shutdown.

    The lifespan owns the upstream client, session registry, schema overlay,
    tokenizer service, and cache store so each request can stay stateless at
    the HTTP transport layer while sharing local enrichment infrastructure.
    """
    cfg = ProxyConfig.from_env()
    app_cfg = ApertureConfig.from_env()
    upstream = UpstreamClient(
        mcp_url=cfg.composio_mcp_url_template,
        timeout_seconds=cfg.timeout_seconds,
    )
    sessions = SessionRegistry()
    tokenizer = TokenizerService()
    overlay = SchemaOverlay(cfg.overlay_path or default_overlay_path())
    cache_store = InMemoryCacheStore()
    if app_cfg.redis_url:
        try:
            cache_store = RedisCacheStore(app_cfg.redis_url)
            logger.info("aperture proxy cache store=redis")
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to initialize Redis cache store; using memory: %s", exc)
    set_default_store(cache_store)
    logger.info(
        "aperture proxy v%s starting; upstream=%s",
        __version__,
        cfg.composio_mcp_url_template,
    )
    try:
        yield {
            "upstream": upstream,
            "config": cfg,
            "app_config": app_cfg,
            "sessions": sessions,
            "tokenizer": tokenizer,
            "overlay": overlay,
            "cache_store": cache_store,
        }
    finally:
        await upstream.aclose()
        logger.info("aperture proxy stopped")


def _request_headers(request: Any) -> dict[str, str]:
    headers = getattr(request, "headers", None)
    if headers is None:
        return {}
    return {str(k).lower(): str(v) for k, v in headers.items()}


def _forward_headers(request: Any) -> dict[str, str]:
    """Forward inbound auth/context headers without leaking transport headers."""

    headers = _request_headers(request)
    return {
        key: value
        for key, value in headers.items()
        if key not in _HOP_BY_HOP_HEADERS
    }


def _query_value(request: Any, key: str) -> str | None:
    query = getattr(request, "query_params", None)
    if query is None:
        return None
    value = query.get(key)
    return str(value) if value else None


def _path_session_id(request: Any) -> str | None:
    scope = getattr(request, "scope", {}) or {}
    path = str(scope.get("path") or "")
    root_path = str(scope.get("root_path") or "")
    if root_path and path.startswith(root_path):
        path = path[len(root_path):]
    tail = path.strip("/").split("/")[-1] if path.strip("/") else ""
    if tail and tail != "mcp":
        return tail
    return None


def _session_id(request: Any, headers: dict[str, str]) -> str | None:
    return (
        _query_value(request, "session_id")
        or _query_value(request, "server_id")
        or headers.get("x-composio-session-id")
        or headers.get("mcp-session-id")
        or _path_session_id(request)
    )


def _user_id(request: Any, headers: dict[str, str], app_cfg: ApertureConfig) -> str | None:
    return (
        _query_value(request, "user_id")
        or headers.get("x-composio-user-id")
        or os.getenv("COMPOSIO_USER_ID")
        or app_cfg.composio_user_id
    )


def _connected_account_id(request: Any, headers: dict[str, str], arguments: dict[str, Any]) -> str | None:
    return (
        arguments.get("connected_account_id")
        or arguments.get("connectedAccountId")
        or _query_value(request, "connected_account_id")
        or headers.get("x-composio-connected-account-id")
        or os.getenv("COMPOSIO_CONNECTED_ACCOUNT_ID")
    )


def _connection_id(request: Any, session_id: str | None, request_id: object) -> str:
    headers = _request_headers(request)
    return (
        headers.get("mcp-session-id")
        or session_id
        or str(request_id)
        or "stateless"
    )


def _payload_from_call_result(result: mcp_types.CallToolResult) -> Any:
    if result.structuredContent is not None:
        return result.structuredContent
    if len(result.content) == 1 and isinstance(result.content[0], mcp_types.TextContent):
        text = result.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return [
        item.model_dump(by_alias=True) if hasattr(item, "model_dump") else item
        for item in result.content
    ]


def _content_blocks(value: Any) -> list[mcp_types.ContentBlock]:
    if isinstance(value, mcp_types.CallToolResult):
        return list(value.content)
    content_types = (
        mcp_types.TextContent,
        mcp_types.ImageContent,
        mcp_types.AudioContent,
        mcp_types.ResourceLink,
        mcp_types.EmbeddedResource,
    )
    if isinstance(value, list) and all(isinstance(item, content_types) for item in value):
        return value
    if isinstance(value, str):
        return [mcp_types.TextContent(type="text", text=value)]
    return [
        mcp_types.TextContent(
            type="text",
            text=json.dumps(value, sort_keys=True, separators=(",", ":")),
        )
    ]


def _inner_call_key(arguments: dict[str, Any]) -> str:
    for key in ("tool_calls", "calls", "executions", "tools"):
        if isinstance(arguments.get(key), list):
            return key
    return "tool_calls"


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
        overlay: SchemaOverlay = ctx["overlay"]
        app_cfg: ApertureConfig = ctx["app_config"]
        request = server.request_context.request
        headers = _forward_headers(request)
        session_id = _session_id(request, _request_headers(request))
        user_id = _user_id(request, _request_headers(request), app_cfg)
        tools = await upstream.list_tools(headers=headers, session_id=session_id, user_id=user_id)
        return overlay.apply_to_tools(tools)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.ContentBlock]:
        ctx = server.request_context.lifespan_context
        upstream: UpstreamClient = ctx["upstream"]
        sessions: SessionRegistry = ctx["sessions"]
        tokenizer: TokenizerService = ctx["tokenizer"]
        overlay: SchemaOverlay = ctx["overlay"]
        app_cfg: ApertureConfig = ctx["app_config"]
        request = server.request_context.request
        request_headers = _request_headers(request)
        headers = _forward_headers(request)
        upstream_session_id = _session_id(request, request_headers)
        user_id = _user_id(request, request_headers, app_cfg)
        connection_id = _connection_id(request, upstream_session_id, server.request_context.request_id)
        sessions.open(connection_id, user_id=user_id)
        turn = sessions.increment_turn(connection_id)
        context = sessions.context_for(
            connection_id,
            toolkit_slug=(arguments.get("toolkit") or arguments.get("toolkit_slug"))
            if isinstance(arguments, dict)
            else None,
            tool_slug=name,
            meta_tool_slug=name,
            model=(request_headers.get("x-aperture-model") or arguments.get("model"))
            if isinstance(arguments, dict)
            else request_headers.get("x-aperture-model"),
            connected_account_id=_connected_account_id(request, request_headers, arguments),
            project_id=os.getenv("COMPOSIO_PROJECT_ID"),
        )
        context = replace(
            context,
            cache_bypass=cache_bypass_requested(request_headers),
        )

        async def upstream_payload(call_arguments: dict[str, Any]) -> Any:
            result = await upstream.call_tool(
                name,
                call_arguments,
                headers=headers,
                session_id=upstream_session_id,
                user_id=user_id,
            )
            payload = _payload_from_call_result(result)
            return overlay.apply_to_payload(payload)

        async def upstream_call() -> Any:
            return await upstream_payload(arguments)

        async def upstream_call_subset(calls: list[dict[str, Any]]) -> Any:
            subset_arguments = dict(arguments)
            subset_arguments[_inner_call_key(arguments)] = calls
            return await upstream_payload(subset_arguments)

        response = await dispatch(
            name,
            arguments,
            context=context,
            upstream_call=upstream_call,
            upstream_call_subset=upstream_call_subset,
        )

        tokenizer.schedule_count(
            response,
            context.model,
            on_complete=lambda count: emit_meta_tool_event(
                context=context,
                raw_count=count,
                session_turn=turn,
            ),
        )
        return _content_blocks(response)

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
