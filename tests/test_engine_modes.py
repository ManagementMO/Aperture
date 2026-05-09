"""Tests for compression engine mode handling."""

from aperture.compression.engine import _VALID_MODES, compress_tool_output


SAMPLE = {
    "id": 999,
    "title": "Login fails after OAuth redirect",
    "body": "x" * 1500,
    "user": {"login": "nikos", "id": 1, "avatar_url": "https://example.com/a"},
    "url": "https://api.github.com/repos/foo/bar/issues/1",
    "node_id": "abc",
    "labels": [
        {"name": "bug", "url": "https://api.github.com/labels/bug"},
        {"name": "p0", "url": "https://api.github.com/labels/p0"},
    ],
}


class TestEngineModes:
    def test_all_documented_modes_are_valid(self):
        assert _VALID_MODES == frozenset({"off", "safe", "balanced", "low", "aggressive"})

    def test_off_returns_unchanged(self):
        result = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="off")
        assert result.compressed_payload == SAMPLE
        assert result.tokens_saved == 0

    def test_safe_drops_node_id_keeps_title(self):
        result = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="safe")
        assert "node_id" not in result.compressed_payload
        assert "title" in result.compressed_payload

    def test_balanced_flattens_user_to_login(self):
        result = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="balanced")
        assert result.compressed_payload["user"] == "nikos"

    def test_low_mode_truncates_body(self):
        result = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="low")
        body = result.compressed_payload["body"]
        assert len(body) <= 200
        assert body.endswith("...")

    def test_aggressive_caps_long_strings_more_than_low(self):
        low = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="low")
        agg = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="aggressive")
        assert agg.compressed_tokens <= low.compressed_tokens

    def test_unknown_mode_falls_back_to_safe(self):
        result = compress_tool_output(SAMPLE, "GITHUB_LIST_ISSUES", mode="bogus_mode")
        assert result.strategy in ("safe", "safe_task=None")
        assert result.tokens_saved >= 0

    def test_protected_fields_survive_aggressive(self):
        result = compress_tool_output(
            SAMPLE,
            "GITHUB_LIST_ISSUES",
            mode="aggressive",
            required_fields=["user.login", "user.avatar_url"],
        )
        user = result.compressed_payload.get("user")
        # Protected → must remain a dict, not flattened
        assert isinstance(user, dict)
        assert user["login"] == "nikos"
        assert "avatar_url" in user
