"""Tests for compression engine."""

import pytest

from aperture.compression.engine import compress_tool_output


class TestCompression:
    def test_off_mode_returns_unchanged(self):
        payload = {"a": 1, "b": 2}
        result = compress_tool_output(payload, "TEST_TOOL", mode="off")
        assert result.compressed_payload == payload
        assert result.tokens_saved == 0
        assert result.compression_ratio == 1.0

    def test_safe_drops_nulls(self):
        payload = {"a": 1, "b": None, "c": "hello"}
        result = compress_tool_output(payload, "TEST_TOOL", mode="safe")
        assert "b" not in result.compressed_payload
        assert result.tokens_saved > 0

    def test_safe_drops_api_url_keeps_html_url(self):
        payload = {
            "title": "Issue",
            "url": "https://api.github.com/repos/foo/bar/issues/1",
            "html_url": "https://github.com/foo/bar/issues/1",
        }
        result = compress_tool_output(payload, "TEST_TOOL", mode="safe")
        # The raw API URL is bookkeeping noise — drop it.
        assert "url" not in result.compressed_payload
        # html_url is the canonical user-facing link — keep it.
        assert "html_url" in result.compressed_payload
        assert "title" in result.compressed_payload

    def test_balanced_flattens_user(self):
        payload = {
            "title": "Issue",
            "user": {"login": "nikos", "id": 123, "avatar_url": "..."},
        }
        result = compress_tool_output(payload, "TEST_TOOL", mode="balanced")
        compressed = result.compressed_payload
        # In aggressive mode, user dict should be flattened to just the login
        assert "user" in compressed
        assert compressed["user"] == "nikos"

    def test_omitted_fields_tracked(self):
        payload = {
            "title": "Issue",
            "url": "https://api.github.com/repos/foo/bar/issues/1",
            "node_id": "abc123",
        }
        result = compress_tool_output(payload, "TEST_TOOL", mode="safe")
        assert "url" in result.omitted_fields
        assert "node_id" in result.omitted_fields
        assert "title" not in result.omitted_fields

    def test_compression_ratio_sane(self):
        payload = {
            "title": "Login fails after OAuth redirect",
            "url": "https://api.github.com/repos/foo/bar/issues/1",
            "node_id": "abc",
            "user": {"login": "test", "id": 1},
        }
        result = compress_tool_output(payload, "TEST_TOOL", mode="balanced")
        assert 0 < result.compression_ratio <= 1.0
        assert result.tokens_saved >= 0
