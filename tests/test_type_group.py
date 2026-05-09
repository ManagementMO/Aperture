"""Tests for type-grouped schema compaction."""

from aperture.schema_optimizer.type_group import compact_schema, measure_compaction
from aperture.tokenization import count_tokens


GITHUB_LIST_ISSUES = {
    "name": "GITHUB_LIST_ISSUES",
    "description": "List issues in a repository.",
    "parameters": {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"]},
            "labels": {"type": "string"},
            "assignee": {"type": "string"},
            "per_page": {"type": "integer"},
            "page": {"type": "integer"},
            "archived": {"type": "boolean"},
        },
        "required": ["owner", "repo"],
    },
}


class TestCompactSchema:
    def test_groups_by_type(self):
        out = compact_schema(GITHUB_LIST_ISSUES)
        assert out.startswith("GITHUB_LIST_ISSUES(")
        # required fields don't have ?, optional ones do
        assert "owner," in out
        assert "repo" in out
        assert "per_page?" in out
        assert "archived?" in out

    def test_includes_enum_values(self):
        out = compact_schema(GITHUB_LIST_ISSUES)
        assert "open" in out and "closed" in out

    def test_compact_smaller_than_json(self):
        m = measure_compaction(GITHUB_LIST_ISSUES, count_tokens, model="gpt-4o")
        assert m.compact_tokens < m.json_tokens
        assert m.ratio < 1.0

    def test_no_properties_returns_empty_call(self):
        schema = {"name": "noop", "parameters": {"type": "object", "properties": {}}}
        assert compact_schema(schema) == "noop()"

    def test_handles_bare_schema(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }
        out = compact_schema(schema, name="profile")
        assert out.startswith("profile(")
        assert "name" in out and "age?" in out

    def test_description_appended(self):
        out = compact_schema(GITHUB_LIST_ISSUES)
        assert "// List issues in a repository." in out
