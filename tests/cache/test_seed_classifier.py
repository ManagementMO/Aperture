"""Tests for the auto-classifier in scripts/seed_cache_policy.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load the script as a module — it lives outside aperture/.
_SEED_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_cache_policy.py"
_spec = importlib.util.spec_from_file_location("seed_cache_policy", _SEED_SCRIPT)
seed = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(seed)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "slug,expected_op,expected_scope",
    [
        # Auth — even when slug contains CREATE
        ("OAUTH_REFRESH_TOKEN", "auth", "account"),
        ("COMPOSIO_INITIATE_CONNECTION", "auth", "account"),
        ("COMPOSIO_MANAGE_CONNECTIONS", "auth", "account"),
        # Write — multiple verb patterns
        ("GITHUB_CREATE_ISSUE", "write", "account"),
        ("GMAIL_SEND_EMAIL", "write", "account"),
        ("SLACK_DELETE_MESSAGE", "write", "account"),
        ("GITHUB_MERGE_PULL_REQUEST", "write", "account"),
        ("GMAIL_BATCH_MODIFY_MESSAGES", "unknown", "none"),  # default-deny
        ("GOOGLESHEETS_APPEND_VALUES", "write", "account"),
        # Public GitHub reads
        ("GITHUB_GET_REPO", "read", "public"),
        ("GITHUB_GET_A_REPOSITORY", "read", "public"),
        ("GITHUB_SEARCH_REPOS", "read", "public"),
        # GitHub LIST + GET
        ("GITHUB_LIST_ISSUES", "read", "account"),
        ("GITHUB_GET_ISSUE", "read", "account"),
        # Private toolkit reads
        ("GMAIL_SEARCH_EMAILS", "read", "account"),
        ("GMAIL_FETCH_EMAILS", "read", "account"),
        ("SLACK_LIST_CHANNELS", "read", "account"),
        ("NOTION_QUERY_DATABASE", "read", "account"),
        ("LINEAR_GET_LINEAR_USER_ISSUES", "read", "account"),
        # Tabular reads
        ("GOOGLESHEETS_BATCH_GET", "read", "account"),
        ("SUPABASE_FETCH_TABLE_ROWS", "read", "account"),
        # YouTube public reads
        ("YOUTUBE_GET_VIDEO", "read", "public"),
        ("YOUTUBE_LIST_VIDEOS", "read", "public"),
        # Default deny for unknown shapes
        ("RANDOM_UNKNOWN_TOOL", "unknown", "none"),
    ],
)
def test_classify_assigns_correct_category(slug, expected_op, expected_scope):
    entry = seed.classify(slug)
    assert entry["operation_type"] == expected_op, slug
    assert entry["privacy_scope"] == expected_scope, slug


def test_classify_writes_have_no_ttl():
    entry = seed.classify("GITHUB_CREATE_ISSUE")
    assert entry["cacheable"] is False
    assert entry["ttl_seconds"] is None
    assert entry["matching"] == "none"


def test_classify_reads_have_ttl_and_exact_matching():
    entry = seed.classify("GITHUB_GET_REPO")
    assert entry["cacheable"] is True
    assert entry["ttl_seconds"] is not None
    assert entry["matching"] == "exact"


def test_render_yaml_produces_loadable_document():
    import yaml

    rendered = seed.render_yaml(["GITHUB_GET_REPO", "GITHUB_CREATE_ISSUE"])
    parsed = yaml.safe_load(rendered)
    assert parsed["version"] == 1
    assert parsed["default"]["cacheable"] is False
    assert "GITHUB_GET_REPO" in parsed["tools"]
    assert parsed["tools"]["GITHUB_GET_REPO"]["cacheable"] is True
    assert parsed["tools"]["GITHUB_CREATE_ISSUE"]["cacheable"] is False
