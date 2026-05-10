"""Inbound `tools/call` dispatcher.

Pattern-matches on the meta-tool slug and routes to the corresponding
`intercept/*` handler. Anything outside the six meta tools (custom tools,
SDK tool slugs that occasionally arrive over MCP) is forwarded transparently.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aperture.proxy.intercept.multi_execute import handle_multi_execute
from aperture.proxy.intercept.search_tools import handle_search_tools
from aperture.proxy.meta_tools import MetaTool, is_meta_tool
from aperture.types import ExecutionContext


async def dispatch(
    name: str,
    arguments: dict[str, Any],
    *,
    context: ExecutionContext,
    upstream_call: Callable[[], Awaitable[Any]],
    upstream_call_subset: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = None,
    fetch_connection_status: Callable[[], Awaitable[Any]] | None = None,
) -> Any:
    """Route a `tools/call` to the right handler.

    Args:
        name: tool slug from the inbound MCP request (the meta-tool name).
        arguments: tool call arguments.
        context: ExecutionContext for cache scoping + attribution.
        upstream_call: async forward of the original request to Composio MCP.
        upstream_call_subset: for MULTI_EXECUTE, a forward that only includes
            a subset of inner tools. Optional; partial-batch caching needs it.
        fetch_connection_status: for SEARCH_TOOLS, a fresh per-user
            connection-status fetch. Optional.

    Returns the (possibly cache-served, possibly enriched) response payload.
    """
    if not is_meta_tool(name):
        # Not a meta tool — forward verbatim without interception.
        return await upstream_call()

    if name == MetaTool.SEARCH_TOOLS.value:
        return await handle_search_tools(
            arguments,
            context=context,
            upstream_call=upstream_call,
            fetch_connection_status=fetch_connection_status,
        )

    if name == MetaTool.MULTI_EXECUTE_TOOL.value:
        return await handle_multi_execute(
            arguments,
            context=context,
            upstream_call=upstream_call,
            upstream_call_subset=upstream_call_subset,
        )

    # GET_TOOL_SCHEMAS / MANAGE_CONNECTIONS / REMOTE_WORKBENCH / REMOTE_BASH_TOOL:
    # forward verbatim. Tokenization + overlay happen in server.py above this
    # layer (the overlay is applied via upstream_payload before the response
    # reaches the cache).
    return await upstream_call()
