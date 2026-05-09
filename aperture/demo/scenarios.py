"""Pre-defined multi-step agent scenarios.

Each scenario is a sequence of ToolCall objects that mirror what a real agent
would do when given a high-level task. The payloads are large and realistic
so that Aperture's value is visible across the entire workflow."""

from __future__ import annotations

from dataclasses import dataclass

from aperture.contracts import ToolCall
from aperture.demo.mock_data import (
    github_commits,
    github_issues,
    github_pull_requests,
    github_repo,
    gmail_search,
    slack_messages,
)


@dataclass
class Scenario:
    name: str
    description: str
    user_query: str  # What the user actually asked the agent
    steps: list[ToolCall]
    expected_effort_mode: str = "medium"


def _make(tool_slug: str, arguments: dict, toolkit_slug: str = "") -> ToolCall:
    return ToolCall(
        toolkit_slug=toolkit_slug,
        tool_slug=tool_slug,
        arguments=arguments,
    )


def scenario_research_project() -> Scenario:
    """Agent researches the composio repo: repo → issues → PRs → commits."""
    return Scenario(
        name="research_project",
        description="Research a GitHub project: get repo details, list open issues, review active PRs, check recent commits",
        user_query="Tell me about the composio repo — how many stars, what issues are open, and what's being worked on?",
        steps=[
            _make("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}, "GITHUB"),
            _make("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "state": "open", "per_page": 5}, "GITHUB"),
            _make("GITHUB_LIST_PULL_REQUESTS", {"owner": "composioHQ", "repo": "composio", "state": "open", "per_page": 3}, "GITHUB"),
            _make("GITHUB_LIST_COMMITS", {"owner": "composioHQ", "repo": "composio", "per_page": 5}, "GITHUB"),
        ],
    )


def scenario_triage_bugs() -> Scenario:
    """Agent triages bugs: find issues → search Gmail for related discussions → check Slack for mentions."""
    return Scenario(
        name="triage_bugs",
        description="Triage open bugs: list GitHub issues, search Gmail for customer reports, check Slack for team discussions",
        user_query="Find all open bugs in composio and check if customers have emailed or slack'd about them",
        steps=[
            _make("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "state": "open", "labels": "bug", "per_page": 5}, "GITHUB"),
            _make("GMAIL_SEARCH_EMAILS", {"query": "composio bug OR error OR crash", "max_results": 3}, "GMAIL"),
            _make("SLACK_SEARCH_MESSAGES", {"query": "bug OR crash OR error", "count": 4}, "SLACK"),
        ],
    )


def scenario_onboard_user() -> Scenario:
    """Agent onboards a new team member: repo overview → recent commits → team Slack activity."""
    return Scenario(
        name="onboard_user",
        description="Onboard a new engineer: show repo overview, recent commits, and active Slack channels",
        user_query="Show me the composio repo and recent commits",
        steps=[
            _make("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}, "GITHUB"),
            _make("GITHUB_LIST_COMMITS", {"owner": "composioHQ", "repo": "composio", "per_page": 5}, "GITHUB"),
            _make("SLACK_SEARCH_MESSAGES", {"query": "onboarding OR new hire OR welcome", "count": 4}, "SLACK"),
        ],
        expected_effort_mode="low",
    )


SCENARIOS: dict[str, Scenario] = {
    "research_project": scenario_research_project(),
    "triage_bugs": scenario_triage_bugs(),
    "onboard_user": scenario_onboard_user(),
}


def get_scenario(name: str) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Choose from: {list(SCENARIOS.keys())}")
    return SCENARIOS[name]


def get_mock_result(tool_slug: str, arguments: dict) -> object:
    """Return a realistic mock payload for a given tool call."""
    owner = arguments.get("owner", "composioHQ")
    repo = arguments.get("repo", "composio")

    if "GET_A_REPOSITORY" in tool_slug or "GET_REPO" in tool_slug:
        return github_repo(owner, repo)

    if "LIST_ISSUES" in tool_slug:
        return github_issues(owner, repo, count=arguments.get("per_page", 5))

    if "LIST_PULL_REQUESTS" in tool_slug or "LIST_PRS" in tool_slug:
        return github_pull_requests(owner, repo, count=arguments.get("per_page", 3))

    if "LIST_COMMITS" in tool_slug:
        return github_commits(owner, repo, count=arguments.get("per_page", 5))

    if "SEARCH_EMAILS" in tool_slug or "FETCH_EMAILS" in tool_slug:
        return gmail_search(arguments.get("query", ""), max_results=arguments.get("max_results", 3))

    if "SEARCH_MESSAGES" in tool_slug or "LIST_MESSAGES" in tool_slug:
        return slack_messages(arguments.get("query", ""), count=arguments.get("count", 4))

    # Fallback
    return {"message": f"Mock result for {tool_slug}", "arguments": arguments}
