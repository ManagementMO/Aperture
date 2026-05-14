"""Composio meta tools — the surface this proxy understands.

The stable Tool Router session surface exposes six meta tools. Composio
Connect also documents `COMPOSIO_WAIT_FOR_CONNECTIONS`; Aperture treats it
as a known meta tool and forwards/tokenizes it without cache or overlay.
"""

from __future__ import annotations

from enum import Enum


class MetaTool(str, Enum):
    SEARCH_TOOLS = "COMPOSIO_SEARCH_TOOLS"
    GET_TOOL_SCHEMAS = "COMPOSIO_GET_TOOL_SCHEMAS"
    MULTI_EXECUTE_TOOL = "COMPOSIO_MULTI_EXECUTE_TOOL"
    MANAGE_CONNECTIONS = "COMPOSIO_MANAGE_CONNECTIONS"
    WAIT_FOR_CONNECTIONS = "COMPOSIO_WAIT_FOR_CONNECTIONS"
    REMOTE_WORKBENCH = "COMPOSIO_REMOTE_WORKBENCH"
    REMOTE_BASH_TOOL = "COMPOSIO_REMOTE_BASH_TOOL"


META_TOOL_SLUGS: frozenset[str] = frozenset(m.value for m in MetaTool)


# Per Plan-Agent 1 §3 decision matrix: which meta tools warrant which Aperture
# enrichment. The router consults these to decide whether to call cache /
# tokenize / overlay before forwarding.
#
#                       cache  tokenize  overlay
#   SEARCH_TOOLS          Y       Y        Y
#   GET_TOOL_SCHEMAS      N       Y        Y
#   MULTI_EXECUTE_TOOL    Y*      Y        N
#   MANAGE_CONNECTIONS    N       Y        N
#   WAIT_FOR_CONNECTIONS  N       Y        N
#   REMOTE_WORKBENCH      N       Y        N
#   REMOTE_BASH_TOOL      N       Y        N
#
# *MULTI_EXECUTE: cache check happens per-inner-tool (the wrapper accepts a
#  list of tools to execute). See aperture/proxy/intercept/multi_execute.py.

CACHEABLE_META_TOOLS: frozenset[str] = frozenset({
    MetaTool.SEARCH_TOOLS.value,
    MetaTool.MULTI_EXECUTE_TOOL.value,
})

OVERLAY_META_TOOLS: frozenset[str] = frozenset({
    MetaTool.SEARCH_TOOLS.value,
    MetaTool.GET_TOOL_SCHEMAS.value,
})


def is_meta_tool(name: str) -> bool:
    return name in META_TOOL_SLUGS


def is_cacheable_meta_tool(name: str) -> bool:
    return name in CACHEABLE_META_TOOLS


def is_overlay_target(name: str) -> bool:
    return name in OVERLAY_META_TOOLS
