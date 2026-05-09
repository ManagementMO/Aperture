"""Tests for task-aware compression profiles."""

from aperture.compression.task_profiles import (
    get_profile,
    list_profiles_for_tool,
    merge_required_fields,
)


class TestTaskProfileLookup:
    def test_existing_profile(self):
        profile = get_profile("GITHUB_LIST_ISSUES", "find_issues_by_assignee")
        assert profile is not None
        assert "assignee.login" in profile.required_fields

    def test_unknown_profile_returns_none(self):
        assert get_profile("UNKNOWN_TOOL", "anything") is None

    def test_list_for_tool(self):
        profiles = list_profiles_for_tool("GITHUB_LIST_ISSUES")
        assert len(profiles) >= 1
        assert all(p.tool_slug == "GITHUB_LIST_ISSUES" for p in profiles)

    def test_list_for_unknown_returns_empty(self):
        assert list_profiles_for_tool("UNKNOWN_TOOL") == []


class TestMergeRequiredFields:
    def test_merges_explicit_with_profile(self):
        merged = merge_required_fields(
            "GITHUB_LIST_ISSUES",
            "find_issues_by_assignee",
            ["custom_field"],
        )
        assert "custom_field" in merged
        assert "assignee.login" in merged

    def test_explicit_only_when_no_task(self):
        merged = merge_required_fields("GITHUB_LIST_ISSUES", None, ["foo", "bar"])
        assert merged == {"foo", "bar"}

    def test_none_returns_empty(self):
        assert merge_required_fields("ANY_TOOL", None, None) == set()
