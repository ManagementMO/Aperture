"""Tests for cache modules."""

import pytest

from aperture.cache.key_builder import build_cache_key
from aperture.cache.policy import is_cacheable


class TestCachePolicy:
    def test_github_get_repo_is_cacheable(self):
        assert is_cacheable("GITHUB_GET_REPO") is True

    def test_github_create_issue_not_cacheable(self):
        assert is_cacheable("GITHUB_CREATE_ISSUE") is False

    def test_gmail_send_not_cacheable(self):
        assert is_cacheable("GMAIL_SEND_EMAIL") is False

    def test_unknown_tool_not_cacheable(self):
        assert is_cacheable("SOME_RANDOM_TOOL") is False


class TestCacheKeyBuilder:
    def test_same_args_same_key(self):
        key1 = build_cache_key("GITHUB_GET_REPO", {"owner": "foo", "repo": "bar"})
        key2 = build_cache_key("GITHUB_GET_REPO", {"owner": "foo", "repo": "bar"})
        assert key1 == key2

    def test_different_args_different_key(self):
        key1 = build_cache_key("GITHUB_GET_REPO", {"owner": "foo", "repo": "bar"})
        key2 = build_cache_key("GITHUB_GET_REPO", {"owner": "foo", "repo": "baz"})
        assert key1 != key2

    def test_user_scoping(self):
        key1 = build_cache_key(
            "GITHUB_GET_REPO", {"owner": "foo", "repo": "bar"}, user_id="user_1"
        )
        key2 = build_cache_key(
            "GITHUB_GET_REPO", {"owner": "foo", "repo": "bar"}, user_id="user_2"
        )
        assert key1 != key2

    def test_key_format(self):
        key = build_cache_key("GITHUB_GET_REPO", {"a": 1})
        assert key.startswith("aperture:cache:")
        assert "GITHUB_GET_REPO" in key
