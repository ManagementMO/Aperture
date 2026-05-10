"""Tests for write_overlay() — the v1 schema overlay artifact."""

from __future__ import annotations

import json


from aperture import __version__
from aperture.schema_optimizer.reports import write_overlay
from aperture.types import SchemaOptimizationResult


def _result(accepted: bool, **overrides) -> SchemaOptimizationResult:
    base = dict(
        tool_slug="GITHUB_LIST_REPOSITORY_ISSUES",
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
        _result(accepted=True, tool_slug="GITHUB_LIST_REPOSITORY_ISSUES"),
        _result(accepted=False, tool_slug="GMAIL_SEND_EMAIL", rejection_reason="safety_terms_removed"),
    ]
    document = write_overlay(out, results)
    assert "GITHUB_LIST_REPOSITORY_ISSUES" in document["tools"]
    assert "GMAIL_SEND_EMAIL" not in document["tools"]


def test_overlay_persists_complete_metadata(tmp_path):
    out = tmp_path / "_overlay.json"
    results = [_result(accepted=True)]
    write_overlay(out, results)
    parsed = json.loads(out.read_text())
    entry = parsed["tools"]["GITHUB_LIST_REPOSITORY_ISSUES"]["description"]
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
    fields = document["tools"]["GITHUB_LIST_REPOSITORY_ISSUES"]
    assert "description" in fields
    assert "parameters.properties.owner.description" in fields


def test_overlay_handles_zero_accepted(tmp_path):
    out = tmp_path / "_overlay.json"
    document = write_overlay(out, [_result(accepted=False), _result(accepted=False)])
    assert document["tools"] == {}
    assert document["stats"]["accepted"] == 0
    assert document["stats"]["total_tokens_saved"] == 0


def test_overlay_rejects_write_tools_even_if_candidate_marked_accepted(tmp_path):
    out = tmp_path / "_overlay.json"
    document = write_overlay(
        out,
        [_result(accepted=True, tool_slug="GITHUB_CREATE_ISSUE")],
    )
    assert document["tools"] == {}
    assert document["stats"]["accepted"] == 0
    assert document["stats"]["rejected"] == 1


def test_overlay_requires_minimum_validation_cases(tmp_path):
    out = tmp_path / "_overlay.json"
    document = write_overlay(out, [_result(accepted=True, validation_cases_run=1)])
    assert document["tools"] == {}
    assert document["stats"]["accepted"] == 0


def test_structural_only_quality_level_lowers_min_cases_and_warns(tmp_path):
    """``quality_level='structural_only'`` lowers ``min_cases_required`` to 1
    so structurally-validated entries can ship — but the overlay file is
    explicitly stamped so operators (and the proxy at load time) know not
    to treat these as judge-validated."""

    out = tmp_path / "_overlay.json"
    document = write_overlay(
        out,
        [_result(accepted=True, validation_cases_run=1)],
        quality_level="structural_only",
    )
    assert document["quality_level"] == "structural_only"
    assert "warning" in document
    assert "STRUCTURAL_ONLY" in document["warning"]
    assert document["stats"]["min_cases_required"] == 1
    assert document["tools"], "structural_only overlay must include the entry"
    entry = next(iter(document["tools"].values()))["description"]
    assert entry["validation"]["quality_level"] == "structural_only"


def test_structural_only_does_not_bypass_read_only_filter(tmp_path):
    """Even with quality_level=structural_only, write/auth tools are still
    blocked. The read-only filter is non-negotiable; structural-only only
    relaxes the cases-run threshold."""

    out = tmp_path / "_overlay.json"
    document = write_overlay(
        out,
        [_result(accepted=True, tool_slug="GITHUB_CREATE_ISSUE", validation_cases_run=1)],
        quality_level="structural_only",
    )
    assert document["tools"] == {}, "write tools must NEVER ship even at structural_only"
    assert document["stats"]["accepted"] == 0


def test_quality_level_default_is_llm_judged(tmp_path):
    out = tmp_path / "_overlay.json"
    document = write_overlay(out, [_result(accepted=True)])
    assert document["quality_level"] == "llm_judged"
    assert document["stats"]["min_cases_required"] == 50
    assert "warning" not in document


def test_quality_level_must_be_known(tmp_path):
    import pytest

    out = tmp_path / "_overlay.json"
    with pytest.raises(ValueError, match="quality_level"):
        write_overlay(out, [], quality_level="bogus")
