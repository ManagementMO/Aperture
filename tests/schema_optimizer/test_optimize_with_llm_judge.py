"""Tests for the LLM-judge-integrated optimization pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aperture.schema_optimizer.llm_judge import JudgeOutcome, save_replay, _replay_key
from aperture.schema_optimizer.reports import (
    load_prompts_by_toolkit,
    optimize_schemas_with_llm_judge,
    write_overlay,
)


def test_load_prompts_by_toolkit_reads_jsonl(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "github.jsonl").write_text(
        '{"prompt": "List repos", "expects_tool": "GITHUB_LIST_REPOSITORIES"}\n'
        '{"prompt": "Make an issue", "expects_tool": "GITHUB_CREATE_ISSUE"}\n'
    )
    (prompts_dir / "gmail.jsonl").write_text(
        '{"prompt": "Send hi", "expects_tool": "GMAIL_SEND_EMAIL"}\n'
    )
    bundles = load_prompts_by_toolkit(prompts_dir)
    assert bundles["github"] == ["List repos", "Make an issue"]
    assert bundles["gmail"] == ["Send hi"]


def test_load_prompts_by_toolkit_skips_malformed(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "github.jsonl").write_text("not-json\n{}\n{\"prompt\": \"ok\"}\n")
    bundles = load_prompts_by_toolkit(prompts_dir)
    assert bundles["github"] == ["ok"]


def _seed_replay_for_candidate(
    *,
    replay_dir: Path,
    tool_slug: str,
    candidate_index: int,
    prompts: list[str],
    selected_tool: str,
    selected_args: dict[str, Any],
    judge_models: list[str],
) -> None:
    """Pre-populate replay fixtures so the judge accepts."""

    for model in judge_models:
        for label in ("orig", "cand"):
            for i, _ in enumerate(prompts):
                key = _replay_key(
                    model=model,
                    tool_slug=f"{tool_slug}::{label}",
                    candidate_index=candidate_index,
                    prompt_index=i,
                )
                save_replay(
                    replay_dir,
                    key,
                    JudgeOutcome(
                        tool_name=selected_tool,
                        tool_input_normalized=selected_args,
                    ),
                )


def test_optimize_schemas_with_llm_judge_replay_accepts_when_judge_agrees(tmp_path: Path) -> None:
    """When replay fixtures show original and candidate agree on every prompt,
    the candidate is accepted with cases_run = len(prompts) so write_overlay
    can include it."""

    # Use 50 synthetic prompts so we hit MIN_OVERLAY_VALIDATION_CASES.
    prompts = [f"prompt {i}" for i in range(50)]
    prompts_by_toolkit = {"github": prompts}

    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()

    # Two top candidates: a read tool (acceptable) and a write tool (acceptable
    # by judge but blocked by overlay safety filter).
    # We need to seed for whichever candidates the pipeline ranks highest.
    # The fixture fetcher returns a deterministic set so we can introspect.
    from aperture.schema_optimizer.fetch_schemas import fetch_tool_schemas
    from aperture.schema_optimizer.extract_fields import extract_description_fields
    from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields
    from aperture.schema_optimizer.rank_candidates import rank_schema_candidates

    schemas = fetch_tool_schemas(live=False)
    fields = []
    for schema in schemas:
        if isinstance(schema, dict):
            fields.extend(extract_description_fields(schema))
    ranked = rank_schema_candidates(tokenize_schema_fields(fields))[:3]

    # Seed replay fixtures for those top-3 candidates so the judge passes
    # for each (orig and cand resolve to the same tool/args).
    for idx, counted in enumerate(ranked):
        _seed_replay_for_candidate(
            replay_dir=replay_dir,
            tool_slug=counted.field.tool_slug,
            candidate_index=idx,
            prompts=prompts,
            selected_tool=counted.field.tool_slug,
            selected_args={"q": "ok"},
            judge_models=["claude-haiku-4-5"],
        )

    results = optimize_schemas_with_llm_judge(
        live=False,
        replay_dir=replay_dir,
        prompts_by_toolkit=prompts_by_toolkit,
        max_candidates=3,
        spot_check_fraction=0.0,  # disable Sonnet so we don't need extra fixtures
    )

    assert len(results) <= 3
    # At least one candidate should have judge cases_run == 50 and accepted=True
    accepted = [r for r in results if r.accepted]
    assert any(r.validation_cases_run == 50 for r in accepted), (
        f"expected at least one judge-accepted result with 50 cases; got "
        f"{[(r.tool_slug, r.validation_cases_run, r.accepted, r.rejection_reason) for r in results]}"
    )

    # Now exercise write_overlay to confirm the safety filter accepts the
    # judge-validated read-tool entries.
    overlay_path = tmp_path / "_overlay.json"
    document = write_overlay(overlay_path, results)
    # Whatever survives must satisfy: cases_run >= 50 AND policy.operation_type
    # is not write/auth.
    from aperture.cache.policy import load_cache_policy

    for slug in document["tools"]:
        policy = load_cache_policy(slug)
        assert policy.operation_type not in {"write", "auth"}, (
            f"overlay leaked write/auth tool {slug} despite judge integration"
        )


def test_optimize_schemas_with_llm_judge_rejects_when_no_prompts() -> None:
    """A toolkit with no prompts must produce a clear rejection_reason."""

    results = optimize_schemas_with_llm_judge(
        live=False,
        prompts_by_toolkit={},  # zero prompts for any toolkit
        max_candidates=2,
    )
    assert results
    rejection_reasons = {r.rejection_reason for r in results}
    assert any(
        reason and reason.startswith("no_prompts_for_toolkit:")
        for reason in rejection_reasons
    )


def test_optimize_schemas_with_llm_judge_respects_budget_tracker() -> None:
    """An exhausted BudgetTracker stops the loop before judging more candidates."""

    from aperture.schema_optimizer.budget import BudgetTracker

    tracker = BudgetTracker(cap_usd=0.0)  # immediately exhausted
    results = optimize_schemas_with_llm_judge(
        live=False,
        tracker=tracker,
        max_candidates=5,
    )
    assert results == [], f"expected empty results when budget is 0, got {results}"
