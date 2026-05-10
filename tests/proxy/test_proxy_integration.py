"""ASGI-level proxy integration tests."""

from __future__ import annotations

import json

import mcp.types as mcp_types
from starlette.testclient import TestClient


def test_tools_list_forwards_auth_headers_and_session(monkeypatch, tmp_path):
    """A real MCP tools/list request must forward auth and substitute session ids."""

    import aperture.proxy.server as server_module

    captured = {}

    class FakeUpstream:
        def __init__(self, mcp_url: str, timeout_seconds: float) -> None:
            captured["template"] = mcp_url

        async def list_tools(
            self,
            headers: dict[str, str],
            *,
            session_id: str | None = None,
            user_id: str | None = None,
        ) -> list[mcp_types.Tool]:
            captured["list_tools"] = {
                "headers": headers,
                "session_id": session_id,
                "user_id": user_id,
            }
            return [
                mcp_types.Tool(
                    name="COMPOSIO_SEARCH_TOOLS",
                    description="Search tools",
                    inputSchema={"type": "object"},
                )
            ]

        async def call_tool(
            self,
            name: str,
            arguments: dict,
            headers: dict[str, str],
            *,
            session_id: str | None = None,
            user_id: str | None = None,
        ) -> mcp_types.CallToolResult:
            raise AssertionError("tools/list test must not call tools/call")

        async def aclose(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(server_module, "UpstreamClient", FakeUpstream)
    monkeypatch.setenv(
        "APERTURE_COMPOSIO_MCP_URL_TEMPLATE",
        "https://backend.composio.dev/tool_router/{session_id}/mcp",
    )
    monkeypatch.setenv("APERTURE_OVERLAY_PATH", str(tmp_path / "missing_overlay.json"))

    app = server_module.create_app()
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "x-api-key": "test-api-key",
        "authorization": "Bearer test-token",
    }

    with TestClient(app) as client:
        init_response = client.post(
            "/mcp/?session_id=sess_list&user_id=user_list",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            },
        )
        assert init_response.status_code == 200

        list_response = client.post(
            "/mcp/?session_id=sess_list&user_id=user_list",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )

    assert list_response.status_code == 200
    assert "COMPOSIO_SEARCH_TOOLS" in list_response.text
    assert captured["list_tools"]["headers"]["x-api-key"] == "test-api-key"
    assert captured["list_tools"]["headers"]["authorization"] == "Bearer test-token"
    assert captured["list_tools"]["session_id"] == "sess_list"
    assert captured["list_tools"]["user_id"] == "user_list"


def test_tools_call_enters_dispatch_and_forwards_auth_headers(monkeypatch):
    """A real MCP tools/call request must not bypass router.dispatch."""

    import aperture.proxy.server as server_module

    captured = {}

    class FakeUpstream:
        def __init__(self, mcp_url: str, timeout_seconds: float) -> None:
            captured["template"] = mcp_url
            captured["timeout_seconds"] = timeout_seconds

        async def list_tools(
            self,
            headers: dict[str, str],
            *,
            session_id: str | None = None,
            user_id: str | None = None,
        ) -> list[mcp_types.Tool]:
            captured["list_tools"] = {
                "headers": headers,
                "session_id": session_id,
                "user_id": user_id,
            }
            return []

        async def call_tool(
            self,
            name: str,
            arguments: dict,
            headers: dict[str, str],
            *,
            session_id: str | None = None,
            user_id: str | None = None,
        ) -> mcp_types.CallToolResult:
            captured["call_tool"] = {
                "name": name,
                "arguments": arguments,
                "headers": headers,
                "session_id": session_id,
                "user_id": user_id,
            }
            return mcp_types.CallToolResult(
                content=[
                    mcp_types.TextContent(
                        type="text",
                        text=json.dumps({"ok": True}),
                    )
                ]
            )

        async def aclose(self) -> None:
            captured["closed"] = True

    async def fake_dispatch(
        name,
        arguments,
        *,
        context,
        upstream_call,
        upstream_call_subset=None,
        fetch_connection_status=None,
    ):
        captured["dispatch"] = {
            "name": name,
            "arguments": arguments,
            "context": context,
            "has_subset": upstream_call_subset is not None,
        }
        return await upstream_call()

    monkeypatch.setattr(server_module, "UpstreamClient", FakeUpstream)
    monkeypatch.setattr(server_module, "dispatch", fake_dispatch)
    monkeypatch.setenv(
        "APERTURE_COMPOSIO_MCP_URL_TEMPLATE",
        "https://backend.composio.dev/tool_router/{session_id}/mcp",
    )

    app = server_module.create_app()
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "x-api-key": "test-api-key",
        "authorization": "Bearer test-token",
    }

    with TestClient(app) as client:
        init_response = client.post(
            "/mcp/?session_id=sess_test&user_id=user_test",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            },
        )
        assert init_response.status_code == 200

        call_response = client.post(
            "/mcp/?session_id=sess_test&user_id=user_test",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "COMPOSIO_SEARCH_TOOLS",
                    "arguments": {"query": "repo"},
                },
            },
        )

    assert call_response.status_code == 200
    assert captured["dispatch"]["name"] == "COMPOSIO_SEARCH_TOOLS"
    assert captured["dispatch"]["arguments"] == {"query": "repo"}
    assert captured["dispatch"]["context"].user_id == "user_test"
    assert captured["dispatch"]["context"].session_id is not None
    assert captured["dispatch"]["has_subset"] is True
    assert captured["call_tool"]["headers"]["x-api-key"] == "test-api-key"
    assert captured["call_tool"]["headers"]["authorization"] == "Bearer test-token"
    assert captured["call_tool"]["session_id"] == "sess_test"
    assert captured["call_tool"]["user_id"] == "user_test"
