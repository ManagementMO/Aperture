"""Async client for Composio's MCP URL.

The proxy forwards every meta-tool request through this client. The public
API is intentionally minimal: ``list_tools()`` and ``call_tool(name, arguments)``.

Auth: ``x-api-key`` is forwarded per-request from the inbound MCP request's
HTTP headers. The proxy NEVER persists or logs the API key (handoff
decision §4).
"""

from __future__ import annotations

import contextlib
import string
from collections import defaultdict
from typing import Any, AsyncIterator

import mcp.types as mcp_types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class UpstreamClient:
    """Forwards MCP requests to a configured Composio MCP URL.

    Creates a fresh session per request because Composio's MCP sessions
    are typically tied to short-lived state (auth, connected accounts) and
    the proxy is stateless w.r.t. credentials. Connection pooling for
    hosted deployments is a future optimization.
    """

    def __init__(self, mcp_url: str, timeout_seconds: float = 30.0) -> None:
        self._mcp_url_template = mcp_url
        self._template_fields = {
            field
            for _, field, _, _ in string.Formatter().parse(mcp_url)
            if field
        }
        self._timeout_seconds = timeout_seconds
        # Prime _mcp_url only when the template has no placeholders so a
        # literal URL is reused without forcing callers to pass session_id.
        self._mcp_url = mcp_url if not self._template_fields else None

    def url_for(self, *, session_id: str | None = None, user_id: str | None = None) -> str:
        """Return the upstream MCP URL for one inbound request.

        Composio's tool-router URL is usually
        ``https://backend.composio.dev/tool_router/{session_id}/mcp``. Tests and
        local deployments may provide a literal URL with no placeholders; in
        that case it is returned unchanged.

        Raises ``ValueError`` if the template needs a placeholder the caller
        did not supply — better to fail loud than to issue
        ``/tool_router//mcp`` and let Composio 404.
        """

        if not self._template_fields:
            return self._mcp_url_template
        provided = {
            "session_id": session_id or "",
            "server_id": session_id or "",
            "user_id": user_id or "",
        }
        missing = sorted(
            field
            for field in self._template_fields
            if field in provided and not provided[field]
        )
        if missing:
            raise ValueError(
                f"upstream URL template requires {missing!r} but caller did not supply"
            )
        values = defaultdict(str, provided)
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
        """Forward ``tools/call`` to Composio and return the raw
        ``CallToolResult``. The cache, attribution, and overlay layers wrap
        this from above (see ``aperture/proxy/server.py:_call_tool``).
        """
        async with self._session(headers, session_id=session_id, user_id=user_id) as session:
            return await session.call_tool(name, arguments=arguments)

    async def aclose(self) -> None:
        """No persistent resources today; method exists so a future
        connection pool can plug in without changing the proxy's lifespan
        code."""
        return None
