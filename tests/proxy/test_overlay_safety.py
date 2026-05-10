"""Defense-in-depth tests for the proxy SchemaOverlay loader."""

from __future__ import annotations

import json
from pathlib import Path

import mcp.types as mcp_types

from aperture.proxy.overlay import SchemaOverlay


def _entry(text: str = "Optimized text.") -> dict:
    return {
        "description": {
            "original": "Original.",
            "optimized": text,
            "original_tokens": 10,
            "optimized_tokens": 5,
            "reduction_tokens": 5,
            "reduction_pct": 0.5,
            "validation": {"cases_run": 50, "passed": True},
            "aperture_optimized": True,
            "aperture_optimizer_version": "0.3.0",
        }
    }


def test_overlay_drops_write_classified_tools_at_load_time(tmp_path: Path) -> None:
    overlay_path = tmp_path / "_overlay.json"
    overlay_path.write_text(json.dumps({
        "version": 1,
        "tools": {
            # GITHUB_CREATE_ISSUE is classified write in policy.yaml.
            "GITHUB_CREATE_ISSUE": _entry("Hand-edited rewrite that should never apply"),
            # A read tool — must survive.
            "GITHUB_LIST_REPOSITORY_ISSUES": _entry("Safe rewrite"),
        },
    }))

    overlay = SchemaOverlay(overlay_path)
    assert "GITHUB_CREATE_ISSUE" in overlay.dropped_unsafe
    assert "GITHUB_LIST_REPOSITORY_ISSUES" not in overlay.dropped_unsafe
    assert overlay.enabled is True

    # Unsafe tool's description must be untouched on tools/list.
    create = mcp_types.Tool(
        name="GITHUB_CREATE_ISSUE",
        description="Original create-issue description",
        inputSchema={"type": "object"},
    )
    safe = mcp_types.Tool(
        name="GITHUB_LIST_REPOSITORY_ISSUES",
        description="Original list-issues description",
        inputSchema={"type": "object"},
    )
    rewritten = overlay.apply_to_tools([create, safe])
    by_name = {tool.name: tool for tool in rewritten}
    assert by_name["GITHUB_CREATE_ISSUE"].description == "Original create-issue description"
    assert by_name["GITHUB_LIST_REPOSITORY_ISSUES"].description == "Safe rewrite"


def test_overlay_drops_send_class_write_tools_at_load_time(tmp_path: Path) -> None:
    """A send-class tool (operation_type=write) — separate test from
    create-class to exercise different policy.yaml entries."""

    overlay_path = tmp_path / "_overlay.json"
    overlay_path.write_text(json.dumps({
        "version": 1,
        "tools": {
            # GMAIL_SEND_EMAIL is write in policy.yaml.
            "GMAIL_SEND_EMAIL": _entry("Hand-edited send rewrite"),
        },
    }))
    overlay = SchemaOverlay(overlay_path)
    assert "GMAIL_SEND_EMAIL" in overlay.dropped_unsafe
    assert overlay.enabled is False  # nothing left


def test_overlay_disabled_when_file_missing(tmp_path: Path) -> None:
    overlay = SchemaOverlay(tmp_path / "missing.json")
    assert overlay.enabled is False
    assert overlay.dropped_unsafe == []


def test_overlay_drops_unknown_classified_tools(tmp_path: Path) -> None:
    """Defense-in-depth: 'unknown' operation_type also gets dropped — only
    explicit 'read' classifications survive."""

    overlay_path = tmp_path / "_overlay.json"
    overlay_path.write_text(json.dumps({
        "version": 1,
        "tools": {
            # GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE is classified 'unknown' in policy.yaml
            "GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE": _entry("Hand-edited unknown rewrite"),
        },
    }))
    overlay = SchemaOverlay(overlay_path)
    assert "GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE" in overlay.dropped_unsafe
    assert overlay.enabled is False
