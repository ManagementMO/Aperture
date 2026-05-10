"""Tests for cache modules."""

from aperture.cache.interceptor import CachedExecutor
from aperture.cache.key_builder import build_cache_key
from aperture.cache.policy import is_cacheable
from aperture.cache.store import CacheStore
from aperture.contracts import ApertureRunConfig
from aperture.integration import ApertureRunner


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
            "GITHUB_GET_REPO",
            {"owner": "foo", "repo": "bar"},
            user_id="user_1",
            cache_scope="user",
        )
        key2 = build_cache_key(
            "GITHUB_GET_REPO",
            {"owner": "foo", "repo": "bar"},
            user_id="user_2",
            cache_scope="user",
        )
        assert key1 != key2

    def test_key_format(self):
        key = build_cache_key("GITHUB_GET_REPO", {"a": 1})
        assert key.startswith("aperture:cache:")
        assert "GITHUB_GET_REPO" in key

    def test_account_scope_requires_connected_account(self):
        assert (
            build_cache_key(
                "GMAIL_SEARCH_EMAILS",
                {"query": "oauth"},
                user_id="user_1",
                cache_scope="account",
            )
            is None
        )

    def test_public_scope_rejects_connected_account_context(self):
        assert (
            build_cache_key(
                "GITHUB_GET_REPO",
                {"owner": "foo", "repo": "bar"},
                connected_account_id="acct_1",
                cache_scope="public",
            )
            is None
        )


class TestCachedExecutor:
    def test_missing_private_scope_executes_but_does_not_cache(self):
        calls = {"count": 0}
        executor = CachedExecutor()
        config = ApertureRunConfig(run_id="missing-scope", user_id="user_1")

        def execute():
            calls["count"] += 1
            return {"messages": [{"subject": "OAuth failure"}]}

        first, first_event = executor.execute(
            "GMAIL_SEARCH_EMAILS", {"query": "oauth"}, execute, config
        )
        second, second_event = executor.execute(
            "GMAIL_SEARCH_EMAILS", {"query": "oauth"}, execute, config
        )

        assert first == second
        assert calls["count"] == 2
        assert first_event.cache_status == "not_cacheable"
        assert first_event.reason == "missing_required_cache_scope"
        assert second_event.cache_status == "not_cacheable"

    def test_failed_response_is_not_cached(self):
        calls = {"count": 0}
        executor = CachedExecutor()
        config = ApertureRunConfig(
            run_id="failed-response",
            connected_account_id="acct_failure_test",
        )

        def execute():
            calls["count"] += 1
            return {"success": False, "error": "temporary failure"}

        _, first_event = executor.execute(
            "GMAIL_SEARCH_EMAILS", {"query": "failure"}, execute, config
        )
        _, second_event = executor.execute(
            "GMAIL_SEARCH_EMAILS", {"query": "failure"}, execute, config
        )

        assert calls["count"] == 2
        assert first_event.cache_status == "miss"
        assert first_event.reason == "failed_response_not_cached"
        assert second_event.cache_status == "miss"

    def test_cache_hit_retracks_entry_for_demo_visibility(self):
        calls = {"count": 0}
        store = CacheStore()
        store.clear_tracked()
        executor = CachedExecutor()
        config = ApertureRunConfig(
            run_id="retrack-hit",
            model="gpt-4o",
            connected_account_id="acct_retrack_test",
        )

        def execute():
            calls["count"] += 1
            return [{"title": "OAuth failure", "state": "open"}]

        _, first_event = executor.execute(
            "GITHUB_LIST_ISSUES", {"case": "retrack"}, execute, config
        )
        store._metadata.clear()
        _, second_event = executor.execute(
            "GITHUB_LIST_ISSUES", {"case": "retrack"}, execute, config
        )

        entries = store.tracked_entries()
        assert calls["count"] == 1
        assert first_event.cache_status == "miss"
        assert second_event.cache_status == "hit"
        assert len(entries) == 1
        assert entries[0]["tool"] == "GITHUB_LIST_ISSUES"
        assert entries[0]["arguments"] == {"case": "retrack"}

    def test_runner_compresses_cached_raw_result_on_hit(self):
        config = ApertureRunConfig(
            run_id="cache-hit-compresses",
            model="gpt-4o",
            connected_account_id="acct_runner_test",
        )
        runner = ApertureRunner(config)
        payload = [
            {
                "title": "OAuth failure",
                "state": "open",
                "body": "Safari users cannot complete OAuth.",
                "url": "https://api.github.test/noisy",
                "user": {"login": "nikos", "avatar_url": "https://avatar.test/noisy"},
            }
        ]

        def execute():
            return payload

        first = runner.run_tool("GITHUB_LIST_ISSUES", {"case": "runner-compression"}, execute)
        second = runner.run_tool("GITHUB_LIST_ISSUES", {"case": "runner-compression"}, execute)

        assert first["cache_event"].cache_status == "miss"
        assert second["cache_event"].cache_status == "hit"
        assert second["compression"].compressed_tokens > 0
        assert second["compression"].tokens_saved > 0
        assert "url" not in second["result"][0]

    def test_runner_summary_counts_only_cache_lookup_events(self):
        config = ApertureRunConfig(
            run_id="cache-summary-events",
            model="gpt-4o",
            connected_account_id="acct_summary_test",
        )
        runner = ApertureRunner(config)
        payload = [{"title": "OAuth failure", "state": "open"}]

        def execute():
            return payload

        runner.run_tool("GITHUB_LIST_ISSUES", {"case": "summary-events"}, execute)
        runner.run_tool("GITHUB_LIST_ISSUES", {"case": "summary-events"}, execute)
        summary = runner.finish()

        assert summary["cache_hits"] == 1
        assert summary["api_calls_avoided"] == 1
