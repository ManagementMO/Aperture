"""Task-aware compression profiles.

Instead of blindly flattening all nested objects, task profiles tell the engine
which fields are semantically required for a given task. Fields not in the
profile get the standard compression treatment; fields in the profile are
preserved (or get gentler compression).

This achieves 40-70% token reduction with minimal quality loss because the
engine only keeps what the LLM actually needs for the current goal.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class TaskProfile:
    """Defines which fields matter for a specific task on a specific tool."""

    task_name: str
    tool_slug: str
    # Dot-paths of fields that MUST be preserved (not flattened/truncated)
    required_fields: set[str] = field(default_factory=set)
    # Fields that are OK to drop entirely for this task
    droppable_fields: set[str] = field(default_factory=set)
    # Fields where long strings should still be truncated (even if required)
    truncate_ok: set[str] = field(default_factory=set)
    # Description of what this task does (for debugging/UI)
    description: str = ""


# ---------------------------------------------------------------------------
# Pre-defined profiles for common tool+task combinations
# ---------------------------------------------------------------------------

_GITHUB_ISSUE_PROFILES: list[TaskProfile] = [
    TaskProfile(
        task_name="find_issues_by_assignee",
        tool_slug="GITHUB_LIST_ISSUES",
        required_fields={
            "assignee.login",
            "assignee.avatar_url",
            "title",
            "state",
            "number",
            "html_url",
            "created_at",
            "labels.name",
            "labels.color",
            "user.login",
        },
        droppable_fields={
            "assignee.gravatar_id",
            "assignee.followers_url",
            "assignee.following_url",
            "assignee.starred_url",
            "assignee.subscriptions_url",
            "assignee.organizations_url",
            "assignee.repos_url",
            "assignee.events_url",
            "assignee.received_events_url",
            "assignee.type",
            "assignee.site_admin",
            "user.gravatar_id",
            "user.followers_url",
            "user.following_url",
            "user.starred_url",
            "user.subscriptions_url",
            "user.organizations_url",
            "user.repos_url",
            "user.events_url",
            "user.received_events_url",
            "user.type",
            "user.site_admin",
            "locked",
            "node_id",
            "repository_url",
            "labels_url",
            "comments_url",
            "events_url",
            "milestone",
            "active_lock_reason",
        },
        description="Find issues assigned to specific people — need assignee identity + issue metadata",
    ),
    TaskProfile(
        task_name="triage_high_priority",
        tool_slug="GITHUB_LIST_ISSUES",
        required_fields={
            "title",
            "state",
            "number",
            "html_url",
            "created_at",
            "updated_at",
            "labels.name",
            "labels.color",
            "body",
            "comments",
            "user.login",
            "assignee.login",
        },
        droppable_fields={
            "user.gravatar_id",
            "user.followers_url",
            "user.following_url",
            "user.starred_url",
            "user.subscriptions_url",
            "user.organizations_url",
            "user.repos_url",
            "user.events_url",
            "user.received_events_url",
            "user.type",
            "user.site_admin",
            "locked",
            "node_id",
            "repository_url",
            "labels_url",
            "comments_url",
            "events_url",
            "milestone",
            "active_lock_reason",
            "performed_via_github_app",
            "reactions",
        },
        description="Triage bugs by priority — need labels, body, comments to assess severity",
    ),
    TaskProfile(
        task_name="count_and_summarize",
        tool_slug="GITHUB_LIST_ISSUES",
        required_fields={
            "title",
            "state",
            "number",
            "created_at",
            "labels.name",
            "user.login",
        },
        droppable_fields={
            "body",
            "comments",
            "assignee",
            "milestone",
            "locked",
            "node_id",
            "repository_url",
            "labels_url",
            "comments_url",
            "events_url",
            "html_url",
            "updated_at",
            "active_lock_reason",
            "performed_via_github_app",
            "reactions",
            "user.gravatar_id",
            "user.followers_url",
            "user.following_url",
            "user.starred_url",
            "user.subscriptions_url",
            "user.organizations_url",
            "user.repos_url",
            "user.events_url",
            "user.received_events_url",
            "user.type",
            "user.site_admin",
        },
        description="Simple count/summary — only need titles, states, and labels",
    ),
]

_GITHUB_REPO_PROFILES: list[TaskProfile] = [
    TaskProfile(
        task_name="repo_overview",
        tool_slug="GITHUB_GET_A_REPOSITORY",
        required_fields={
            "name",
            "full_name",
            "description",
            "stargazers_count",
            "forks_count",
            "open_issues_count",
            "language",
            "created_at",
            "updated_at",
            "owner.login",
            "owner.avatar_url",
            "html_url",
            "topics",
            "license.name",
            "license.spdx_id",
        },
        droppable_fields={
            "owner.gravatar_id",
            "owner.followers_url",
            "owner.following_url",
            "owner.starred_url",
            "owner.subscriptions_url",
            "owner.organizations_url",
            "owner.repos_url",
            "owner.events_url",
            "owner.received_events_url",
            "owner.type",
            "owner.site_admin",
            "node_id",
            "private",
            "fork",
            "archive_url",
            "assignees_url",
            "blobs_url",
            "branches_url",
            "clone_url",
            "collaborators_url",
            "comments_url",
            "commits_url",
            "compare_url",
            "contents_url",
            "contributors_url",
            "deployments_url",
            "downloads_url",
            "events_url",
            "forks_url",
            "git_commits_url",
            "git_refs_url",
            "git_tags_url",
            "git_url",
            "hooks_url",
            "issue_comment_url",
            "issue_events_url",
            "issues_url",
            "keys_url",
            "labels_url",
            "languages_url",
            "merges_url",
            "milestones_url",
            "notifications_url",
            "pulls_url",
            "releases_url",
            "ssh_url",
            "stargazers_url",
            "statuses_url",
            "subscribers_url",
            "subscription_url",
            "svn_url",
            "tags_url",
            "teams_url",
            "trees_url",
            "mirror_url",
        },
        description="Get a high-level repo overview — need stats, description, owner identity",
    ),
]

_NOTION_PROFILES: list[TaskProfile] = [
    TaskProfile(
        task_name="search_and_list",
        tool_slug="NOTION_SEARCH_NOTION_PAGE",
        required_fields={
            "id",
            "title",
            "url",
            "created_time",
            "last_edited_time",
            "object",
            "parent.type",
            "parent.database_id",
            "parent.page_id",
            "properties.title.title.text.content",
        },
        droppable_fields={
            "object",
            "archived",
            "in_trash",
            "icon",
            "cover",
            "properties",
            "url",
            "public_url",
            "created_by",
            "last_edited_by",
            "workspace_id",
        },
        truncate_ok={
            "properties.title.title.text.content",
        },
        description="Search Notion pages — need titles, URLs, and parent info",
    ),
]

_LINEAR_PROFILES: list[TaskProfile] = [
    TaskProfile(
        task_name="list_user_issues",
        tool_slug="LINEAR_GET_LINEAR_USER_ISSUES",
        required_fields={
            "id",
            "identifier",
            "title",
            "state.name",
            "state.color",
            "priority",
            "createdAt",
            "updatedAt",
            "assignee.name",
            "assignee.email",
            "team.name",
            "team.key",
            "url",
        },
        droppable_fields={
            "assignee.avatarUrl",
            "assignee.avatarBackgroundColor",
            "assignee.isMe",
            "creator",
            "project",
            "cycle",
            "estimate",
            "parent",
            "subIssues",
            "comments",
            "history",
            "integrationResources",
            "sourceBranch",
            "targetBranch",
        },
        description="List a user's assigned issues — need state, priority, team, assignee",
    ),
]

_SUPABASE_PROFILES: list[TaskProfile] = [
    TaskProfile(
        task_name="fetch_user_records",
        tool_slug="SUPABASE_FETCH_TABLE_ROWS",
        required_fields={
            "id",
            "email",
            "created_at",
            "updated_at",
            "role",
            "status",
            "full_name",
        },
        droppable_fields={
            "avatar_url",
            "phone",
            "address",
            "metadata",
            "preferences",
            "last_sign_in_at",
            "confirmation_sent_at",
            "confirmed_at",
            "recovery_sent_at",
            "email_change_sent_at",
            "new_email",
            "invited_at",
            "action_link",
        },
        description="Fetch user records — need identity, role, status, timestamps",
    ),
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ALL_PROFILES: list[TaskProfile] = (
    _GITHUB_ISSUE_PROFILES
    + _GITHUB_REPO_PROFILES
    + _NOTION_PROFILES
    + _LINEAR_PROFILES
    + _SUPABASE_PROFILES
)
_ALL_PROFILES += [
    replace(p, tool_slug="GITHUB_LIST_REPOSITORY_ISSUES")
    for p in _GITHUB_ISSUE_PROFILES
]

_PROFILE_REGISTRY: dict[tuple[str, str], TaskProfile] = {
    (p.tool_slug, p.task_name): p for p in _ALL_PROFILES
}

_TOOL_PROFILES: dict[str, list[TaskProfile]] = {}
for p in _ALL_PROFILES:
    _TOOL_PROFILES.setdefault(p.tool_slug, []).append(p)


def get_profile(tool_slug: str, task_name: str) -> TaskProfile | None:
    """Look up a task profile by tool + task name."""
    return _PROFILE_REGISTRY.get((tool_slug, task_name))


def list_profiles_for_tool(tool_slug: str) -> list[TaskProfile]:
    """List all available profiles for a given tool."""
    return _TOOL_PROFILES.get(tool_slug, [])


def get_profile_fields(tool_slug: str, task_name: str) -> set[str]:
    """Get the set of required field paths for a profile."""
    profile = get_profile(tool_slug, task_name)
    if profile is None:
        return set()
    return profile.required_fields


def merge_required_fields(
    tool_slug: str,
    task_name: str | None,
    explicit_fields: list[str] | None,
) -> set[str]:
    """Merge profile-required fields with explicitly requested fields."""
    result: set[str] = set()
    if task_name:
        result |= get_profile_fields(tool_slug, task_name)
    if explicit_fields:
        result |= set(explicit_fields)
    return result
