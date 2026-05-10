"""Replay-mode tests for the LLM judge.

Per handoff §14.4, validator tests MUST NOT call live LLM in CI. This file
seeds JudgeOutcome JSON files into a temp replay dir, then exercises
run_judge() in replay mode to assert accept/reject behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aperture.schema_optimizer.llm_judge import (
    JudgeOutcome,
    _replay_key,
    load_replay,
    normalize_args,
    run_judge,
    save_replay,
)


_ORIGINAL = {
    "name": "GITHUB_CREATE_ISSUE",
    "description": "Creates a new issue in a specified GitHub repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["owner", "repo", "title"],
    },
}

_CANDIDATE = {
    "name": "GITHUB_CREATE_ISSUE",
    "description": "Create a GitHub issue. Required: owner, repo, title.",
    "input_schema": _ORIGINAL["input_schema"],
}


def _seed_passing_replays(replay_dir: Path, prompts: list[str]) -> None:
    """Seed replay outcomes that match between original and candidate
    schemas for both Haiku and Sonnet — should produce ACCEPT."""
    for idx, _prompt in enumerate(prompts):
        for model in ("claude-haiku-4-5", "claude-sonnet-4-5"):
            for label in ("orig", "cand"):
                key = _replay_key(
                    model=model,
                    tool_slug=f"GITHUB_CREATE_ISSUE::{label}",
                    candidate_index=0,
                    prompt_index=idx,
                )
                save_replay(
                    replay_dir,
                    key,
                    JudgeOutcome(
                        tool_name="GITHUB_CREATE_ISSUE",
                        tool_input_normalized=normalize_args({"owner": "ACME", "repo": "X", "title": "T"}),
                    ),
                )


def _seed_haiku_disagreement(replay_dir: Path, prompts: list[str]) -> None:
    """Seed replays where Haiku picks the wrong tool on the candidate.
    Should produce REJECT (rejection_reason=haiku_disagreement)."""
    for idx, _prompt in enumerate(prompts):
        for model in ("claude-haiku-4-5", "claude-sonnet-4-5"):
            for label in ("orig", "cand"):
                # Same args/tool except Haiku on candidate diverges on first prompt.
                tool_name = "GITHUB_CREATE_ISSUE"
                if model == "claude-haiku-4-5" and label == "cand" and idx == 0:
                    tool_name = "GITHUB_CREATE_PULL_REQUEST"  # simulated disagreement
                key = _replay_key(
                    model=model,
                    tool_slug=f"GITHUB_CREATE_ISSUE::{label}",
                    candidate_index=0,
                    prompt_index=idx,
                )
                save_replay(
                    replay_dir,
                    key,
                    JudgeOutcome(
                        tool_name=tool_name,
                        tool_input_normalized=normalize_args({"owner": "ACME", "repo": "X", "title": "T"}),
                    ),
                )


def _seed_sonnet_disagreement(replay_dir: Path, prompts: list[str]) -> None:
    """Haiku agrees on every prompt; Sonnet disagrees on at least one
    spot-checked prompt. Should produce REJECT (rejection_reason=sonnet_disagreement)."""
    for idx, _prompt in enumerate(prompts):
        for model in ("claude-haiku-4-5", "claude-sonnet-4-5"):
            for label in ("orig", "cand"):
                input_dict = {"owner": "ACME", "repo": "X", "title": "T"}
                if model == "claude-sonnet-4-5" and label == "cand" and idx in (0, 1, 2):
                    # Sonnet picks different params on candidate — treats it as a different tool call.
                    input_dict = {"owner": "ACME", "repo": "X", "title": "DIFFERENT"}
                key = _replay_key(
                    model=model,
                    tool_slug=f"GITHUB_CREATE_ISSUE::{label}",
                    candidate_index=0,
                    prompt_index=idx,
                )
                save_replay(
                    replay_dir,
                    key,
                    JudgeOutcome(
                        tool_name="GITHUB_CREATE_ISSUE",
                        tool_input_normalized=normalize_args(input_dict),
                    ),
                )


def test_normalize_args_sorts_keys_and_drops_none():
    raw = {"b": 1, "a": None, "c": {"y": 2, "x": 1}}
    result = normalize_args(raw)
    assert list(result.keys()) == ["b", "c"]
    assert list(result["c"].keys()) == ["x", "y"]


def test_replay_key_is_deterministic():
    a = _replay_key(model="m", tool_slug="t", candidate_index=0, prompt_index=0)
    b = _replay_key(model="m", tool_slug="t", candidate_index=0, prompt_index=0)
    assert a == b


def test_replay_round_trip(tmp_path):
    key = "test-key"
    outcome = JudgeOutcome(tool_name="X", tool_input_normalized={"a": 1})
    save_replay(tmp_path, key, outcome)
    loaded = load_replay(tmp_path, key)
    assert loaded is not None
    assert loaded.tool_name == "X"
    assert loaded.tool_input_normalized == {"a": 1}


def test_load_replay_returns_none_for_missing_key(tmp_path):
    assert load_replay(tmp_path, "absent-key") is None


def test_run_judge_accepts_when_all_replays_match(tmp_path):
    prompts = [f"prompt_{i}" for i in range(10)]
    _seed_passing_replays(tmp_path, prompts)
    result = run_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=prompts,
        live=False,
        replay_dir=tmp_path,
        spot_check_fraction=0.20,
    )
    assert result.passed is True
    assert result.rejection_reason is None
    assert result.validation_cases_run == 10


def test_run_judge_rejects_on_haiku_disagreement(tmp_path):
    prompts = [f"prompt_{i}" for i in range(5)]
    _seed_haiku_disagreement(tmp_path, prompts)
    result = run_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=prompts,
        live=False,
        replay_dir=tmp_path,
        spot_check_fraction=0.0,  # don't bother with sonnet for this test
    )
    assert result.passed is False
    assert result.rejection_reason == "haiku_disagreement"


def test_run_judge_rejects_on_sonnet_disagreement(tmp_path):
    prompts = [f"prompt_{i}" for i in range(10)]
    _seed_sonnet_disagreement(tmp_path, prompts)
    result = run_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=prompts,
        live=False,
        replay_dir=tmp_path,
        spot_check_fraction=0.5,  # high enough to land on prompts 0-2
        seed=1,
    )
    # Spot check at fraction=0.5 with seed=1 should include at least one of prompts 0,1,2.
    assert result.passed is False
    # Could be either reason — sonnet_disagreement is the typical one here
    assert result.rejection_reason in {"sonnet_disagreement", "haiku_disagreement"}


def test_run_judge_handles_empty_prompts():
    result = run_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=[],
        live=False,
        replay_dir=Path("/tmp/nonexistent"),
    )
    assert result.passed is False
    assert result.rejection_reason == "no_prompts_provided"


def test_run_judge_rejects_on_invalid_spot_check_fraction(tmp_path):
    with pytest.raises(ValueError):
        run_judge(
            original_schema=_ORIGINAL,
            candidate_schema=_CANDIDATE,
            prompts=["x"],
            live=False,
            replay_dir=tmp_path,
            spot_check_fraction=2.0,
        )


def test_run_judge_with_missing_replay_fixtures_rejects(tmp_path):
    """A missing replay file is a missing test fixture, NOT 'no signal = pass'.

    Pre-fix (commit 4743a2d7): the validator silent-passed when both
    original and candidate replay outcomes returned `None` (file didn't
    exist), because `None == None` skipped the failure-append. This test
    locks in the corrected behavior: missing replays produce rejection
    with reason='missing_replay_fixtures'.
    """
    # Use a tmp_path with NO seeded replays. Every _ask() will return None.
    result = run_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=["x", "y"],
        live=False,
        replay_dir=tmp_path,  # exists but empty
        spot_check_fraction=0.0,
    )
    assert result.passed is False, "missing replays MUST not silent-pass"
    assert result.rejection_reason == "missing_replay_fixtures"
    assert result.validation_cases_run == 2


def test_validator_calls_into_judge_when_present(tmp_path):
    """validate_schema_rewrite_with_llm_judge() in validator.py imports from
    llm_judge and calls run_judge. With llm_judge present, it should NOT
    raise NotImplementedError anymore."""
    from aperture.schema_optimizer.validator import validate_schema_rewrite_with_llm_judge

    prompts = [f"prompt_{i}" for i in range(5)]
    _seed_passing_replays(tmp_path, prompts)

    result = validate_schema_rewrite_with_llm_judge(
        original_schema=_ORIGINAL,
        candidate_schema=_CANDIDATE,
        prompts=prompts,
        live=False,
        replay_dir=tmp_path,
        spot_check_fraction=0.0,
    )
    assert result.passed is True
    assert result.validation_cases_run == 5
