"""Async client for Composio's MCP URL.

The proxy forwards every meta-tool request through this client. PR 1 keeps
the API minimal: `list_tools()` and `call_tool(name, arguments)`. PR 2 adds
streaming support for tools that emit progressive responses.

Auth: `x-api-key` is forwarded per-request from the inbound MCP request's
HTTP headers. The proxy NEVER persists or logs the API key (handoff
decision §4).
"""

from __future__ import annotations

import contextlib
from collections import defaultdict
from typing import Any, AsyncIterator

import mcp.types as mcp_types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class UpstreamClient:
    """Forwards MCP requests to a configured Composio MCP URL.

    Creates a fresh session per request because Composio's MCP sessions
    are typically tied to short-lived state (auth, connected accounts) and
    the proxy is stateless w.r.t. credentials. PR 5 considers connection
    pooling for hosted deployments.
    """

    def __init__(self, mcp_url: str, timeout_seconds: float = 30.0) -> None:
        self._mcp_url_template = mcp_url
        self._mcp_url = self.url_for()
        self._timeout_seconds = timeout_seconds

    def url_for(self, *, session_id: str | None = None, user_id: str | None = None) -> str:
        """Return the upstream MCP URL for one inbound request.

        Composio's tool-router URL is usually
        ``https://backend.composio.dev/tool_router/{session_id}/mcp``. Tests and
        local deployments may provide a literal URL with no placeholders; in
        that case it is returned unchanged.
        """

        values = defaultdict(
            str,
            {
                "session_id": session_id or "",
                "server_id": session_id or "",
                "user_id": user_id or "",
            },
        )
        return self._mcp_url_template.format_map(values)

    @contextlib.asynccontextmanager
    async def _session(
        self,
        headers: dict[str, str],
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[ClientSession]:
        """Yield an initialized MCP `ClientSession` for one request.

        `headers` carry the inbound `x-api-key` (and any other auth headers
        the developer's MCP client supplied) so the upstream Composio call
        is authenticated as the developer, not as the proxy.
        """
        async with streamablehttp_client(
            self.url_for(session_id=session_id, user_id=user_id),
            headers=headers,
            timeout=self._timeout_seconds,
        ) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def list_tools(
        self,
        headers: dict[str, str],
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[mcp_types.Tool]:
        """Forward `tools/list` to Composio and return the tool array verbatim."""
        async with self._session(headers, session_id=session_id, user_id=user_id) as session:
            result = await session.list_tools()
            return list(result.tools)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        headers: dict[str, str],
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> mcp_types.CallToolResult:
        """Forward `tools/call` to Composio. PR 1 returns the result unchanged.

        PR 2 will wrap this with cache lookup; PR 3 with token attribution;
        PR 4 with schema overlay application.
        """
        async with self._session(headers, session_id=session_id, user_id=user_id) as session:
            return await session.call_tool(name, arguments=arguments)

    async def aclose(self) -> None:
        """No persistent resources today; method exists so PR 5's connection
        pool can plug in without changing the proxy's lifespan code."""
        return None
