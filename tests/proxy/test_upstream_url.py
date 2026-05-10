"""url_for() must fail loud when a required template field is missing."""

from __future__ import annotations

import pytest

from aperture.proxy.upstream import UpstreamClient


def test_url_for_substitutes_session_id():
    client = UpstreamClient("https://example.test/tool_router/{session_id}/mcp")
    url = client.url_for(session_id="sess_abc")
    assert url == "https://example.test/tool_router/sess_abc/mcp"


def test_url_for_raises_when_required_field_missing():
    client = UpstreamClient("https://example.test/tool_router/{session_id}/mcp")
    with pytest.raises(ValueError, match="session_id"):
        client.url_for(session_id=None)


def test_url_for_passes_through_literal_url_with_no_placeholders():
    client = UpstreamClient("https://example.test/literal/mcp")
    assert client.url_for() == "https://example.test/literal/mcp"
    assert client.url_for(session_id=None, user_id=None) == "https://example.test/literal/mcp"


def test_url_for_handles_user_id_template():
    client = UpstreamClient("https://example.test/{session_id}/u/{user_id}/mcp")
    assert client.url_for(session_id="s", user_id="u") == "https://example.test/s/u/u/mcp"
    with pytest.raises(ValueError, match="user_id"):
        client.url_for(session_id="s", user_id=None)
