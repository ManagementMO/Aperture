"""Upstream field selection profiles.

Instead of fetching everything from an API and then compressing it, we can
often request only the fields we need UPSTREAM — at the API level.

This is lossless compression at the source:
- GitHub REST API: ?per_page=10 (pagination)
- GitHub GraphQL: specify exact fields in the query
- Notion API: filter properties
- Linear API: filter fields
- Supabase: SELECT specific columns

When the upstream API supports field selection, Aperture can push the profile
downstream so only relevant data ever enters the context window.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any


@dataclass(frozen=True)
class FieldProfile:
    """Defines which fields to request from an upstream API."""

    tool_slug: str
    profile_name: str
    fields: list[str]
    page_size: int | None = None
    filters: dict[str, Any] = dc_field(default_factory=dict)
    description: str = ""


# ---------------------------------------------------------------------------
# Pre-defined field profiles
# ---------------------------------------------------------------------------

_GITHUB_FIELD_PROFILES: list[FieldProfile] = [
    FieldProfile(
        tool_slug="GITHUB_LIST_ISSUES",
        profile_name="minimal",
        fields=["number", "title", "state", "created_at", "user.login"],
        page_size=10,
        description="Minimal issue list — titles and states only",
    ),
    FieldProfile(
        tool_slug="GITHUB_LIST_ISSUES",
        profile_name="triage",
        fields=[
            "number", "title", "state", "created_at", "updated_at",
            "body", "comments", "labels.name", "labels.color",
            "assignee.login", "user.login", "html_url",
        ],
        page_size=20,
        description="Triage view — need body, labels, assignee to assess severity",
    ),
    FieldProfile(
        tool_slug="GITHUB_LIST_ISSUES",
        profile_name="assignment",
        fields=[
            "number", "title", "state", "assignee.login", "assignee.email",
            "assignee.avatar_url", "user.login", "created_at", "html_url",
        ],
        page_size=20,
        description="Assignment view — focus on who's assigned to what",
    ),
    FieldProfile(
        tool_slug="GITHUB_GET_A_REPOSITORY",
        profile_name="overview",
        fields=[
            "name", "full_name", "description", "stargazers_count",
            "forks_count", "open_issues_count", "language", "created_at",
            "updated_at", "owner.login", "owner.avatar_url", "html_url",
            "topics", "license.name", "license.spdx_id",
        ],
        description="Repo overview — stats and metadata",
    ),
    FieldProfile(
        tool_slug="GITHUB_LIST_PULL_REQUESTS",
        profile_name="review",
        fields=[
            "number", "title", "state", "created_at", "updated_at",
            "body", "user.login", "head.ref", "base.ref", "html_url",
            "draft", "merged", "mergeable_state",
        ],
        page_size=10,
        description="PR review — need branch info, merge status, body",
    ),
]

_NOTION_FIELD_PROFILES: list[FieldProfile] = [
    FieldProfile(
        tool_slug="NOTION_SEARCH_NOTION_PAGE",
        profile_name="minimal",
        fields=["id", "title", "url", "created_time", "last_edited_time"],
        page_size=10,
        description="Page search — just titles and URLs",
    ),
    FieldProfile(
        tool_slug="NOTION_SEARCH_NOTION_PAGE",
        profile_name="content_preview",
        fields=[
            "id", "title", "url", "created_time", "last_edited_time",
            "parent.type", "parent.database_id", "properties",
        ],
        page_size=10,
        description="Content preview — include parent and properties",
    ),
]

_LINEAR_FIELD_PROFILES: list[FieldProfile] = [
    FieldProfile(
        tool_slug="LINEAR_GET_LINEAR_USER_ISSUES",
        profile_name="minimal",
        fields=["id", "identifier", "title", "state.name", "priority", "url"],
        page_size=20,
        description="Minimal issue list",
    ),
    FieldProfile(
        tool_slug="LINEAR_GET_LINEAR_USER_ISSUES",
        profile_name="full",
        fields=[
            "id", "identifier", "title", "state.name", "state.color",
            "priority", "createdAt", "updatedAt", "assignee.name",
            "assignee.email", "team.name", "team.key", "url", "description",
        ],
        page_size=20,
        description="Full issue view with team and assignee details",
    ),
]

_SUPABASE_FIELD_PROFILES: list[FieldProfile] = [
    FieldProfile(
        tool_slug="SUPABASE_FETCH_TABLE_ROWS",
        profile_name="minimal",
        fields=["id", "email", "created_at", "role", "status"],
        page_size=50,
        description="Minimal user records",
    ),
    FieldProfile(
        tool_slug="SUPABASE_FETCH_TABLE_ROWS",
        profile_name="full",
        fields=[
            "id", "email", "created_at", "updated_at", "role",
            "status", "full_name", "avatar_url", "last_sign_in_at",
        ],
        page_size=50,
        description="Full user records with profile data",
    ),
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ALL_FIELD_PROFILES: list[FieldProfile] = (
    _GITHUB_FIELD_PROFILES
    + _NOTION_FIELD_PROFILES
    + _LINEAR_FIELD_PROFILES
    + _SUPABASE_FIELD_PROFILES
)

_FIELD_PROFILE_REGISTRY: dict[tuple[str, str], FieldProfile] = {
    (p.tool_slug, p.profile_name): p for p in _ALL_FIELD_PROFILES
}

_TOOL_FIELD_PROFILES: dict[str, list[FieldProfile]] = {}
for p in _ALL_FIELD_PROFILES:
    _TOOL_FIELD_PROFILES.setdefault(p.tool_slug, []).append(p)


def get_field_profile(tool_slug: str, profile_name: str) -> FieldProfile | None:
    """Look up a field profile by tool + profile name."""
    return _FIELD_PROFILE_REGISTRY.get((tool_slug, profile_name))


def list_field_profiles_for_tool(tool_slug: str) -> list[FieldProfile]:
    """List all available field profiles for a given tool."""
    return _TOOL_FIELD_PROFILES.get(tool_slug, [])


def apply_field_selection(payload: object, fields: list[str]) -> object:
    """Apply field selection to a payload (simulate upstream filtering).

    This is used when the upstream API doesn't support field selection
    but we still want to show what WOULD be returned with proper filtering.

    Args:
        payload: The full API response.
        fields: Dot-paths of fields to keep.

    Returns:
        Filtered payload with only the requested fields.
    """
    if not fields:
        return payload

    if isinstance(payload, list):
        return [_filter_object(item, fields) for item in payload]

    if isinstance(payload, dict):
        return _filter_object(payload, fields)

    return payload


def _filter_object(obj: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Filter a dict to only keep specified dot-path fields."""
    if not isinstance(obj, dict):
        return obj

    result: dict[str, Any] = {}
    groups: dict[str, list[str | None]] = {}
    for path in fields:
        parts = path.split(".", 1)
        top = parts[0]
        rest = parts[1] if len(parts) > 1 else None
        groups.setdefault(top, []).append(rest)

    for top_key, rest_fields in groups.items():
        if top_key not in obj:
            continue

        val = obj[top_key]
        sub_fields = [r for r in rest_fields if r is not None]

        if not sub_fields:
            result[top_key] = val
        elif isinstance(val, dict):
            result[top_key] = _filter_object(val, sub_fields)
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            result[top_key] = [_filter_object(item, sub_fields) for item in val]
        else:
            result[top_key] = val

    return result
