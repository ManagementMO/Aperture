"""Meta-tool registry safety checks."""

from aperture.proxy.meta_tools import (
    MetaTool,
    is_cacheable_meta_tool,
    is_meta_tool,
    is_overlay_target,
)


def test_wait_for_connections_is_known_but_never_optimized():
    """Composio Connect exposes this as a seventh meta tool.

    Aperture should recognize it for metrics/routing clarity, but it is an
    auth-flow wait primitive and must not be cached or schema-overlaid.
    """

    slug = MetaTool.WAIT_FOR_CONNECTIONS.value
    assert is_meta_tool(slug)
    assert not is_cacheable_meta_tool(slug)
    assert not is_overlay_target(slug)
