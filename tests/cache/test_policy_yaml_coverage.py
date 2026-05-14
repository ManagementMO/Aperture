"""Tests for the v1 cache policy.yaml at scale.

Plan + handoff §13.1: every slug the team uses must appear in the YAML
(deny-by-default for unrecognized is fine, but the slug should be listed).
This file enforces that for the seed list we ship.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_YAML = REPO_ROOT / "aperture" / "cache" / "policy.yaml"
SEED_JSON = REPO_ROOT / "scripts" / "_seed_tool_list.json"


def _load_yaml() -> dict:
    return yaml.safe_load(POLICY_YAML.read_text())


def _load_seed() -> list[str]:
    return json.loads(SEED_JSON.read_text())


def test_policy_yaml_exists_and_parses():
    doc = _load_yaml()
    assert doc["version"] == 1
    assert "default" in doc
    assert "tools" in doc


def test_policy_yaml_default_is_deny():
    doc = _load_yaml()
    default = doc["default"]
    assert default["cacheable"] is False
    assert default["operation_type"] == "unknown"
    assert default["matching"] == "none"


def test_policy_yaml_covers_at_least_1500_tools():
    doc = _load_yaml()
    assert len(doc["tools"]) >= 1500, (
        f"policy.yaml has {len(doc['tools'])} entries; v1 acceptance "
        "(handoff §13.1 cell 2) requires broad Composio coverage. Run scripts/seed_cache_policy.py to "
        "regenerate from a Composio dump."
    )


def test_every_seed_slug_appears_in_policy():
    """Every slug in the seed list must be classified in policy.yaml."""
    doc = _load_yaml()
    tools = doc["tools"]
    seed = _load_seed()
    missing = [slug for slug in seed if slug not in tools]
    assert missing == [], f"seed slugs missing from policy: {missing[:10]}"


def test_no_write_or_auth_tool_is_cacheable():
    """Hard safety invariant: write/auth ops MUST be cacheable=False."""
    doc = _load_yaml()
    for slug, entry in doc["tools"].items():
        if entry.get("operation_type") in ("write", "auth"):
            assert entry["cacheable"] is False, (
                f"{slug} is operation_type={entry.get('operation_type')} "
                f"but cacheable={entry['cacheable']}; this would let "
                "Aperture serve a stale write/auth response from cache."
            )


def test_every_cacheable_entry_has_ttl_and_scope():
    doc = _load_yaml()
    for slug, entry in doc["tools"].items():
        if entry.get("cacheable") is True:
            assert entry.get("ttl_seconds") is not None, f"{slug}: cacheable=true but no ttl_seconds"
            assert entry.get("privacy_scope") in {"public", "account", "user", "project", "session"}, (
                f"{slug}: invalid privacy_scope {entry.get('privacy_scope')}"
            )
            assert entry.get("matching") == "exact", f"{slug}: cacheable=true but matching != exact"


def test_load_cache_policy_returns_yaml_entry_for_known_slug():
    """Smoke test: the existing load_cache_policy() reads the new big YAML correctly."""
    from aperture.cache.policy import load_cache_policy

    policy = load_cache_policy("GITHUB_GET_REPO")
    assert policy.cacheable is True
    assert policy.operation_type == "read"
    assert policy.privacy_scope == "public"


def test_load_cache_policy_returns_default_for_unknown_slug():
    from aperture.cache.policy import load_cache_policy

    policy = load_cache_policy("TOTALLY_MADE_UP_TOOL")
    assert policy.cacheable is False
    assert policy.operation_type == "unknown"


@pytest.mark.parametrize(
    "slug,expected_op,expected_scope,expected_cacheable",
    [
        ("GITHUB_GET_REPO", "read", "public", True),
        ("GITHUB_LIST_ISSUES", "read", "account", True),
        ("GITHUB_CREATE_ISSUE", "write", "account", False),
        ("GMAIL_SEARCH_EMAILS", "read", "account", True),
        ("GMAIL_SEND_EMAIL", "write", "account", False),
        ("COMPOSIO_MANAGE_CONNECTIONS", "auth", "account", False),
        ("COMPOSIO_WAIT_FOR_CONNECTIONS", "auth", "account", False),
        ("OAUTH_REFRESH_TOKEN", "auth", "account", False),
    ],
)
def test_critical_slug_classifications(slug, expected_op, expected_scope, expected_cacheable):
    doc = _load_yaml()
    entry = doc["tools"][slug]
    assert entry["operation_type"] == expected_op, f"{slug}: operation_type"
    assert entry["privacy_scope"] == expected_scope, f"{slug}: privacy_scope"
    assert entry["cacheable"] is expected_cacheable, f"{slug}: cacheable"
