"""Tests for upstream field selection."""

from aperture.compression.field_profiles import (
    apply_field_selection,
    get_field_profile,
    list_field_profiles_for_tool,
)


class TestFieldProfileRegistry:
    def test_get_known_profile(self):
        p = get_field_profile("GITHUB_LIST_ISSUES", "minimal")
        assert p is not None
        assert "title" in p.fields

    def test_unknown_profile(self):
        assert get_field_profile("BOGUS", "minimal") is None

    def test_list_for_tool(self):
        profiles = list_field_profiles_for_tool("GITHUB_LIST_ISSUES")
        names = {p.profile_name for p in profiles}
        assert "minimal" in names

    def test_default_filters_is_dict(self):
        p = get_field_profile("GITHUB_LIST_ISSUES", "minimal")
        assert isinstance(p.filters, dict)


class TestApplyFieldSelection:
    def test_top_level_fields(self):
        payload = {"id": 1, "title": "x", "body": "long...", "node_id": "abc"}
        out = apply_field_selection(payload, ["id", "title"])
        assert out == {"id": 1, "title": "x"}

    def test_nested_field_path(self):
        payload = {"user": {"login": "nikos", "id": 1, "avatar_url": "..."}, "title": "x"}
        out = apply_field_selection(payload, ["title", "user.login"])
        assert out == {"title": "x", "user": {"login": "nikos"}}

    def test_list_of_objects(self):
        payload = [
            {"id": 1, "title": "a", "extra": "drop"},
            {"id": 2, "title": "b", "extra": "drop"},
        ]
        out = apply_field_selection(payload, ["id", "title"])
        assert out == [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]

    def test_missing_field_skipped(self):
        out = apply_field_selection({"id": 1}, ["id", "missing"])
        assert out == {"id": 1}

    def test_empty_field_list_returns_payload(self):
        payload = {"id": 1}
        assert apply_field_selection(payload, []) == payload
