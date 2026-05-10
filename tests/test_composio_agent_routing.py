from types import SimpleNamespace

import anthropic

from aperture.agent import composio_agent


def test_google_sheet_read_is_routed_to_googlesheets():
    assert composio_agent._normalize_toolkit_slug("google_sheets") == "googlesheets"
    assert composio_agent._toolkits_for_ask(
        "Read the first 50 rows of my Google Sheet",
        ["github", "googlesheets", "gmail"],
    ) == ["googlesheets"]
    assert composio_agent._ask_requires_connected_tool(
        "Read the first 50 rows of my Google Sheet"
    )


def test_github_commit_main_404_retries_master_args():
    retry = composio_agent._github_list_commits_retry_args(
        "GITHUB_LIST_COMMITS",
        {"owner": "composiohq", "repo": "composio", "sha": "main", "per_page": 3},
        {
            "successful": False,
            "data": {
                "message": "Not Found",
                "documentation_url": "https://docs.github.com/rest/commits/commits#list-commits",
                "status": "404",
            },
        },
    )

    assert retry == {
        "owner": "composiohq",
        "repo": "composio",
        "sha": "master",
        "per_page": 3,
    }


def test_github_commit_main_branch_string_retries_master_args():
    retry = composio_agent._github_list_commits_retry_args(
        "GITHUB_LIST_COMMITS",
        {"owner": "composiohq", "repo": "composio", "sha": "main branch"},
        '{"message":"Not Found","status":"404"}',
    )

    assert retry == {
        "owner": "composiohq",
        "repo": "composio",
        "sha": "master",
    }


def test_github_commit_main_branch_ask_adds_master_sha():
    retry = composio_agent._github_list_commits_retry_args(
        "GITHUB_LIST_COMMITS",
        {"owner": "composiohq", "repo": "composio", "per_page": 3},
        '{"message":"Not Found","status":"404"}',
        "List the last 3 commits on the composiohq/composio main branch",
    )

    assert retry == {
        "owner": "composiohq",
        "repo": "composio",
        "per_page": 3,
        "sha": "master",
    }


def test_github_commit_retry_ignores_non_404():
    retry = composio_agent._github_list_commits_retry_args(
        "GITHUB_LIST_COMMITS",
        {"owner": "composiohq", "repo": "composio", "sha": "main"},
        {"successful": False, "data": {"message": "Bad credentials", "status": "401"}},
    )

    assert retry is None


def test_tool_required_ask_retries_no_tool_answer_and_executes_sheet(monkeypatch):
    composio_agent.clear_result_cache()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("COMPOSIO_API_KEY", "test")
    monkeypatch.setattr(composio_agent, "_resolved_user_id", lambda: "user_1")
    monkeypatch.setattr(composio_agent, "_resolved_toolkits", lambda user_id: ["googlesheets"])
    monkeypatch.setattr(
        composio_agent,
        "_resolved_tool_list",
        lambda user_id, toolkits: [
            {
                "name": "GOOGLESHEETS_BATCH_GET",
                "description": "Read values from a Google Sheet.",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
    )
    monkeypatch.setattr(
        composio_agent,
        "_connected_account_id_for_tool",
        lambda user_id, tool_slug: "acct_sheets",
    )

    class FakeTextBlock:
        type = "text"

        def __init__(self, text: str):
            self.text = text

        def model_dump(self):
            return {"type": "text", "text": self.text}

    class FakeToolUseBlock:
        type = "tool_use"
        id = "toolu_1"
        name = "GOOGLESHEETS_BATCH_GET"
        input = {"spreadsheet": "users", "rows": 50}

        def model_dump(self):
            return {
                "type": "tool_use",
                "id": self.id,
                "name": self.name,
                "input": self.input,
            }

    class FakeMessages:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            usage = SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            )
            if len(self.requests) == 1:
                return SimpleNamespace(
                    stop_reason="end_turn",
                    content=[FakeTextBlock("I cannot access your sheet.")],
                    usage=usage,
                )
            if len(self.requests) == 2:
                return SimpleNamespace(
                    stop_reason="tool_use",
                    content=[FakeToolUseBlock()],
                    usage=usage,
                )
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[FakeTextBlock("Read 2 rows from the sheet.")],
                usage=usage,
            )

    fake_messages = FakeMessages()

    class FakeAnthropic:
        def __init__(self):
            self.messages = fake_messages

    class FakeTools:
        def execute(self, slug, args, user_id, dangerously_skip_version_check=True):
            assert slug == "GOOGLESHEETS_BATCH_GET"
            return {
                "successful": True,
                "data": [
                    {"name": "Ada", "email": "ada@example.com"},
                    {"name": "Grace", "email": "grace@example.com"},
                ],
            }

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(
        composio_agent,
        "_composio_client",
        lambda: SimpleNamespace(tools=FakeTools()),
    )

    result = composio_agent.run_agent(
        "Read the first 50 rows of my Google Sheet",
        bypass_cache=True,
    )

    assert result.error is None
    assert result.answer == "Read 2 rows from the sheet."
    assert [step.tool for step in result.steps] == ["GOOGLESHEETS_BATCH_GET"]
    assert fake_messages.requests[0]["tool_choice"] == {"type": "any"}
    assert fake_messages.requests[1]["tool_choice"] == {"type": "any"}
    assert "tool_choice" not in fake_messages.requests[2]
