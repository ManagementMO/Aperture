"""PR 1 sanity tests for the MCP proxy skeleton.

Goal: prove the wiring imports + the ASGI app can be constructed without
network. End-to-end MCP round-trips against Composio require live creds and
a recorded fixture, which lands in PR 2's `test_transparent.py`.
"""

from __future__ import annotations

import pytest

from aperture import __version__
from aperture.proxy import ProxyConfig, create_app
from aperture.proxy.upstream import UpstreamClient


def test_version_is_v1_fixes_baseline():
    """Sanity: aperture is at v0.3.0+ on the v1 fixes branch."""

    major, minor, *_ = __version__.split(".")
    assert int(major) >= 0 and int(minor) >= 3


def test_proxy_config_defaults_are_sane(monkeypatch: pytest.MonkeyPatch):
    """ProxyConfig.from_env() must return usable defaults with NO env vars set."""

    for key in (
        "APERTURE_PROXY_HOST",
        "APERTURE_PROXY_PORT",
        "APERTURE_COMPOSIO_MCP_URL_TEMPLATE",
        "APERTURE_OVERLAY_PATH",
        "APERTURE_PROXY_LOG_LEVEL",
        "APERTURE_PROXY_UPSTREAM_TIMEOUT",
        "APERTURE_PROXY_FALLBACK_TOKENIZER",
    ):
        monkeypatch.delenv(key, raising=False)

    cfg = ProxyConfig.from_env()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8001
    assert "backend.composio.dev" in cfg.composio_mcp_url_template
    assert cfg.overlay_path is None
    assert cfg.log_level == "INFO"
    assert cfg.timeout_seconds == 30.0
    assert cfg.fallback_tokenizer == "auto"


def test_proxy_config_reads_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APERTURE_PROXY_HOST", "0.0.0.0")
    monkeypatch.setenv("APERTURE_PROXY_PORT", "9090")
    monkeypatch.setenv("APERTURE_PROXY_LOG_LEVEL", "debug")
    cfg = ProxyConfig.from_env()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9090
    assert cfg.log_level == "DEBUG"


def test_truthy_env_helper(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APERTURE_TEST_FLAG", "yes")
    assert ProxyConfig.truthy_env("APERTURE_TEST_FLAG") is True
    monkeypatch.setenv("APERTURE_TEST_FLAG", "no")
    assert ProxyConfig.truthy_env("APERTURE_TEST_FLAG") is False
    monkeypatch.delenv("APERTURE_TEST_FLAG")
    assert ProxyConfig.truthy_env("APERTURE_TEST_FLAG", default=True) is True
    assert ProxyConfig.truthy_env("APERTURE_TEST_FLAG", default=False) is False


def test_upstream_client_constructs():
    """The UpstreamClient must construct without making a network call."""

    client = UpstreamClient(
        mcp_url="https://example.test/mcp",
        timeout_seconds=5.0,
    )
    assert client._mcp_url == "https://example.test/mcp"
    assert client._timeout_seconds == 5.0


def test_create_app_returns_asgi_app():
    """create_app() returns a Starlette app with the /mcp route mounted."""

    app = create_app()
    # Starlette stores routes on .routes; we check that something is mounted at /mcp.
    paths = []
    for route in getattr(app, "routes", []):
        path = getattr(route, "path", None)
        if path is None:
            path = getattr(route, "path_format", None)
        if path:
            paths.append(path)
    assert any("/mcp" in p for p in paths), f"expected /mcp mount, got {paths}"
