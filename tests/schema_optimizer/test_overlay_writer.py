"""Tests for write_overlay() — the v1 schema overlay artifact."""

from __future__ import annotations

import json


from aperture import __version__
from aperture.schema_optimizer.reports import write_overlay
from aperture.types import SchemaOptimizationResult


def _result(accepted: bool, **overrides) -> SchemaOptimizationResult:
    base = dict(
        tool_slug="GITHUB_CREATE_ISSUE",
        field_path="description",
        original_text="Creates a new issue in a specified GitHub repository.",
        optimized_text="Create a GitHub issue.",
        original_tokens=68,
        optimized_tokens=8,
        reduction_tokens=60,
        reduction_pct=0.882,
        validation_cases_run=50,
        validation_passed=True,
        accepted=accepted,
        rejection_reason=None if accepted else "haiku_disagreement",
    )
    base.update(overrides)
    return SchemaOptimizationResult(**base)


def test_overlay_only_includes_accepted_rewrites(tmp_path):
    out = tmp_path / "_overlay.json"
    results = [
        _result(accepted=True, tool_slug="GITHUB_CREATE_ISSUE"),
        _result(accepted=False, tool_slug="GMAIL_SEND_EMAIL", rejection_reason="safety_terms_removed"),
    ]
    document = write_overlay(out, results)
    assert "GITHUB_CREATE_ISSUE" in document["tools"]
    assert "GMAIL_SEND_EMAIL" not in document["tools"]


def test_overlay_persists_complete_metadata(tmp_path):
    out = tmp_path / "_overlay.json"
    results = [_result(accepted=True)]
    write_overlay(out, results)
    parsed = json.loads(out.read_text())
    entry = parsed["tools"]["GITHUB_CREATE_ISSUE"]["description"]
    assert entry["original"].startswith("Creates a new")
    assert entry["optimized"] == "Create a GitHub issue."
    assert entry["original_tokens"] == 68
    assert entry["optimized_tokens"] == 8
    assert entry["reduction_tokens"] == 60
    assert entry["reduction_pct"] == 0.882
    assert entry["aperture_optimized"] is True
    assert entry["aperture_optimizer_version"] == __version__
    assert entry["validation"]["cases_run"] == 50
    assert entry["validation"]["passed"] is True


def test_overlay_top_level_metadata(tmp_path):
    out = tmp_path / "_overlay.json"
    results = [_result(accepted=True), _result(accepted=False)]
    document = write_overlay(out, results)
    assert document["version"] == 1
    assert document["aperture_optimizer_version"] == __version__
    assert "generated_at" in document
    assert document["stats"]["total_results"] == 2
    assert document["stats"]["accepted"] == 1
    assert document["stats"]["rejected"] == 1
    assert document["stats"]["total_tokens_saved"] == 60


def test_overlay_handles_multiple_fields_per_tool(tmp_path):
    out = tmp_path / "_overlay.json"
    results = [
        _result(accepted=True, field_path="description"),
        _result(
            accepted=True,
            field_path="parameters.properties.owner.description",
            original_text="The owner of the repository.",
            optimized_text="Repo owner.",
            original_tokens=8,
            optimized_tokens=2,
            reduction_tokens=6,
            reduction_pct=0.75,
        ),
    ]
    document = write_overlay(out, results)
    fields = document["tools"]["GITHUB_CREATE_ISSUE"]
    assert "description" in fields
    assert "parameters.properties.owner.description" in fields


def test_overlay_handles_zero_accepted(tmp_path):
    out = tmp_path / "_overlay.json"
    document = write_overlay(out, [_result(accepted=False), _result(accepted=False)])
    assert document["tools"] == {}
    assert document["stats"]["accepted"] == 0
    assert document["stats"]["total_tokens_saved"] == 0
