import pytest

from aperture.integration import live_check


class FakeExecutor:
    def __init__(self, config=None):
        self.calls = 0

    def get_tools(self, toolkits=None, slug=None):
        return [{"slug": slug or "GITHUB_LIST_ISSUES", "toolkits": toolkits, "description": "List issues."}]

    def execute(self, tool_slug, arguments, user_id=None, connected_account_id=None, version=None):
        self.calls += 1
        return [{"title": "Bug", "state": "open", "labels": [{"name": "bug"}], "url": "api"}]

    def get_toolkit_version(self, toolkit_slug):
        return "20260501_01"

    def find_active_connected_account_id(self, toolkit, user_id=None):
        return "acct_1"

    def session_tools(self, user_id=None, toolkits=None):
        return [{"function": {"name": "COMPOSIO_SEARCH_TOOLS", "description": "Search tools."}}]

    def session_search(self, query, user_id=None, toolkits=None):
        return {"results": [{"primary_tool_slugs": ["GITHUB_LIST_REPOSITORY_ISSUES"], "toolkits": ["github"]}]}

    def session_execute(self, tool_slug, arguments, user_id=None, toolkits=None, account=None):
        return self.execute(tool_slug, arguments, user_id=user_id, connected_account_id=account)


async def test_live_check_fetch_and_execute_with_fake_composio(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test")
    monkeypatch.setenv("COMPOSIO_USER_ID", "u1")
    monkeypatch.setattr(live_check, "ComposioToolExecutor", FakeExecutor)
    result = await live_check.run_live_check(
        toolkit="GITHUB",
        tool_slug="GITHUB_LIST_REPOSITORY_ISSUES",
        arguments={"owner": "acme", "repo": "app"},
        connected_account_id="acct_1",
        execute=True,
        out_path=tmp_path / "live.json",
    )
    assert result["schema_fetch_ok"] is True
    assert result["execution"] is not None
    assert any(event["cache_status"] == "hit" for event in result["cache_events"])


async def test_live_check_validates_tool_router(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test")
    monkeypatch.setenv("COMPOSIO_USER_ID", "u1")
    monkeypatch.setattr(live_check, "ComposioToolExecutor", FakeExecutor)
    result = await live_check.run_live_check(
        toolkit="GITHUB",
        tool_slug="GITHUB_LIST_REPOSITORY_ISSUES",
        arguments={},
        connected_account_id=None,
        execute=False,
        tool_router=True,
        search_query="list repository issues",
        out_path=tmp_path / "live.json",
    )
    assert result["tool_router"]["search_preview"]["results"][0]["primary_tool_slugs"] == ["GITHUB_LIST_REPOSITORY_ISSUES"]


async def test_live_check_refuses_non_read_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test")
    monkeypatch.setenv("COMPOSIO_USER_ID", "u1")
    monkeypatch.setattr(live_check, "ComposioToolExecutor", FakeExecutor)
    with pytest.raises(RuntimeError, match="Refusing live execution"):
        await live_check.run_live_check(
            toolkit="GMAIL",
            tool_slug="GMAIL_SEND_EMAIL",
            arguments={},
            connected_account_id="acct_1",
            execute=True,
            out_path=tmp_path / "live.json",
        )
