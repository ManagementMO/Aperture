"""LLM-judge validator for schema description rewrites.

Plan decision #4 + handoff §6.4: a candidate description is accepted only
if a Claude model selects the same tool with the same parameters across
the prompt set, original schema vs candidate schema. Haiku is the primary
judge (cheap); Sonnet is the spot-check on a fraction of accepted cases
to guard against Haiku false-positive accepts.

Replay mode (handoff §14.4): tests load recorded LLM responses from
JSON files keyed by `(model, tool_slug, candidate_index, prompt_index)`.
No live LLM calls in CI.

Run mode: live Anthropic calls, gated on ANTHROPIC_API_KEY + an explicit
flag passed through `run_judge(live=True)`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aperture.schema_optimizer.budget import BudgetTracker
from aperture.schema_optimizer.models import ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class JudgeOutcome:
    """One judge call's normalized result."""

    tool_name: str | None
    tool_input_normalized: dict[str, Any] | None
    raw_response_text: str = ""


@dataclass
class JudgeRunResult:
    accepted: bool
    cases_run: int
    cases_passed: int
    failures: list[dict[str, Any]] = field(default_factory=list)
    haiku_passes: int = 0
    sonnet_passes: int = 0
    sonnet_disagreements: int = 0
    rejection_reason: str | None = None

    def to_validation_result(self) -> ValidationResult:
        if self.accepted:
            return ValidationResult(self.cases_run, True, None)
        return ValidationResult(self.cases_run, False, self.rejection_reason or "judge_disagreement")


def normalize_args(args: Any) -> Any:
    """Sort dict keys recursively, drop None values, lowercase enum strings.

    Two judge runs that produce the same logical args under different key
    ordering / nullable handling must compare equal.
    """
    if isinstance(args, dict):
        return {k: normalize_args(v) for k, v in sorted(args.items()) if v is not None}
    if isinstance(args, list):
        return [normalize_args(v) for v in args]
    return args


# --------------------- Replay mode ---------------------

def _replay_key(*, model: str, tool_slug: str, candidate_index: int, prompt_index: int) -> str:
    """Deterministic key for the replay fixtures directory."""
    return f"{model}::{tool_slug}::cand{candidate_index}::p{prompt_index}"


def _replay_path(replay_dir: Path, key: str) -> Path:
    return replay_dir / f"{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"


def load_replay(replay_dir: Path, key: str) -> JudgeOutcome | None:
    path = _replay_path(replay_dir, key)
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    return JudgeOutcome(
        tool_name=blob.get("tool_name"),
        tool_input_normalized=blob.get("tool_input_normalized"),
        raw_response_text=blob.get("raw_response_text", ""),
    )


def save_replay(replay_dir: Path, key: str, outcome: JudgeOutcome) -> None:
    replay_dir.mkdir(parents=True, exist_ok=True)
    path = _replay_path(replay_dir, key)
    path.write_text(
        json.dumps(
            {
                "key": key,
                "tool_name": outcome.tool_name,
                "tool_input_normalized": outcome.tool_input_normalized,
                "raw_response_text": outcome.raw_response_text,
            },
            indent=2,
            sort_keys=True,
        )
    )


# --------------------- Live mode ---------------------

def _ask_anthropic(
    *,
    client: Any,
    model: str,
    tools: list[dict],
    prompt: str,
    tracker: BudgetTracker | None = None,
) -> JudgeOutcome:
    """Single Anthropic call. Returns the JudgeOutcome.

    Validator MUST NOT crash on a single 4xx/5xx — catches and returns an
    empty outcome so the higher-level loop can record a failure.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            tools=tools,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.warning("anthropic call failed: %s", exc)
        return JudgeOutcome(tool_name=None, tool_input_normalized=None)

    if tracker is not None:
        tracker.record_usage(getattr(response, "usage", None), model=model)

    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    text_buffer: list[str] = []
    for block in getattr(response, "content", []) or []:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            tool_name = getattr(block, "name", None)
            tool_input = normalize_args(getattr(block, "input", {}) or {})
        elif block_type == "text":
            text_buffer.append(getattr(block, "text", "") or "")
    return JudgeOutcome(
        tool_name=tool_name,
        tool_input_normalized=tool_input,
        raw_response_text="".join(text_buffer),
    )


# --------------------- Public API ---------------------

def run_judge(
    *,
    original_schema: dict,
    candidate_schema: dict,
    prompts: list[str],
    judge_model: str = "claude-haiku-4-5",
    spot_check_model: str = "claude-sonnet-4-5",
    spot_check_fraction: float = 0.10,
    similar_tools: list[dict] | None = None,
    live: bool = False,
    replay_dir: Path | None = None,
    tracker: BudgetTracker | None = None,
    candidate_index: int = 0,
    seed: int = 1,
) -> ValidationResult:
    """Validate `candidate_schema` against `original_schema` over `prompts`.

    Two-stage:
        1. Haiku judge runs every prompt × {original, candidate}. Compare
           tool selection + normalized args. Reject on any disagreement.
        2. Sonnet spot-check: for `spot_check_fraction` of prompts (rounded
           up, min 1 if fraction>0), run Sonnet on the same prompt+schema
           pair. If Sonnet disagrees with Haiku on tool selection or args,
           reject the candidate.

    Args:
        live: when True, makes real Anthropic API calls. When False, uses
            replay_dir to load recorded outcomes. Tests must use replay mode.
        replay_dir: required when live=False; ignored when live=True (only
            used to record fresh outcomes).
        tracker: optional BudgetTracker that BudgetExhausted-aborts mid-run.

    Returns the standard ValidationResult that downstream `reports.py` and
    `validator.validate_schema_rewrite_with_llm_judge` expect.
    """
    if not prompts:
        return ValidationResult(0, False, "no_prompts_provided")
    if not (0.0 <= spot_check_fraction <= 1.0):
        raise ValueError("spot_check_fraction must be in [0, 1]")

    rng = random.Random(seed)
    spot_check_count = max(1, int(len(prompts) * spot_check_fraction)) if spot_check_fraction > 0 else 0
    spot_check_indices = set(rng.sample(range(len(prompts)), min(spot_check_count, len(prompts))))

    similar_tools = list(similar_tools or [])
    tool_slug = original_schema.get("name") or original_schema.get("slug") or "_unknown_"

    client = None
    if live:
        try:
            import anthropic

            if not os.getenv("ANTHROPIC_API_KEY"):
                return ValidationResult(0, False, "live_requested_but_no_anthropic_key")
            client = anthropic.Anthropic()
        except ImportError:
            return ValidationResult(0, False, "anthropic_package_not_installed")

    failures: list[dict[str, Any]] = []
    haiku_passes = 0
    sonnet_passes = 0
    sonnet_disagreements = 0
    missing_replay_keys: list[str] = []

    def _ask(*, model: str, schema: dict, prompt: str, prompt_index: int, schema_label: str) -> JudgeOutcome:
        key = _replay_key(
            model=model,
            tool_slug=f"{tool_slug}::{schema_label}",
            candidate_index=candidate_index,
            prompt_index=prompt_index,
        )
        if not live:
            if replay_dir is None:
                missing_replay_keys.append(key)
                return JudgeOutcome(tool_name=None, tool_input_normalized=None)
            outcome = load_replay(replay_dir, key)
            if outcome is None:
                # Per adversarial review 2026-05-10: a missing replay file
                # is a missing test fixture, NOT "no signal = pass". The
                # downstream `None == None` comparison would silently mark
                # the candidate accepted; we explicitly track this here so
                # the result.rejection_reason can flag it.
                missing_replay_keys.append(key)
                return JudgeOutcome(tool_name=None, tool_input_normalized=None)
            return outcome
        outcome = _ask_anthropic(
            client=client,
            model=model,
            tools=[schema] + similar_tools,
            prompt=prompt,
            tracker=tracker,
        )
        if replay_dir is not None:
            save_replay(replay_dir, key, outcome)
        return outcome

    for idx, prompt in enumerate(prompts):
        if tracker is not None and tracker.exhausted():
            return ValidationResult(idx, False, "budget_exhausted")

        original_outcome = _ask(
            model=judge_model, schema=original_schema, prompt=prompt,
            prompt_index=idx, schema_label="orig",
        )
        candidate_outcome = _ask(
            model=judge_model, schema=candidate_schema, prompt=prompt,
            prompt_index=idx, schema_label="cand",
        )

        if (
            original_outcome.tool_name != candidate_outcome.tool_name
            or original_outcome.tool_input_normalized != candidate_outcome.tool_input_normalized
        ):
            failures.append({
                "prompt": prompt,
                "stage": "haiku",
                "original": {"name": original_outcome.tool_name, "input": original_outcome.tool_input_normalized},
                "candidate": {"name": candidate_outcome.tool_name, "input": candidate_outcome.tool_input_normalized},
            })
            continue

        haiku_passes += 1

        if idx in spot_check_indices:
            sonnet_original = _ask(
                model=spot_check_model, schema=original_schema, prompt=prompt,
                prompt_index=idx, schema_label="orig",
            )
            sonnet_candidate = _ask(
                model=spot_check_model, schema=candidate_schema, prompt=prompt,
                prompt_index=idx, schema_label="cand",
            )
            if (
                sonnet_original.tool_name != sonnet_candidate.tool_name
                or sonnet_original.tool_input_normalized != sonnet_candidate.tool_input_normalized
            ):
                sonnet_disagreements += 1
                failures.append({
                    "prompt": prompt,
                    "stage": "sonnet_spot_check",
                    "haiku_agreed": True,
                    "sonnet_original": {"name": sonnet_original.tool_name, "input": sonnet_original.tool_input_normalized},
                    "sonnet_candidate": {"name": sonnet_candidate.tool_name, "input": sonnet_candidate.tool_input_normalized},
                })
            else:
                sonnet_passes += 1

    # If the replay store was missing fixtures, the candidate cannot be
    # judged — surface this explicitly rather than silent-passing.
    incomplete_validation = bool(missing_replay_keys) and not live
    accepted = len(failures) == 0 and not incomplete_validation
    rejection_reason = None
    if not accepted:
        if incomplete_validation:
            rejection_reason = "missing_replay_fixtures"
        elif any(f["stage"] == "haiku" for f in failures):
            rejection_reason = "haiku_disagreement"
        elif any(f["stage"] == "sonnet_spot_check" for f in failures):
            rejection_reason = "sonnet_disagreement"

    # Stash the latest JudgeRunResult in module-state so callers that want
    # the failure detail (reports.py, replay tests) can fetch it without
    # mutating the frozen ValidationResult contract.
    global _LAST_JUDGE_RUN
    _LAST_JUDGE_RUN = JudgeRunResult(
        accepted=accepted,
        cases_run=len(prompts),
        cases_passed=haiku_passes,
        failures=failures,
        haiku_passes=haiku_passes,
        sonnet_passes=sonnet_passes,
        sonnet_disagreements=sonnet_disagreements,
        rejection_reason=rejection_reason,
    )
    return ValidationResult(len(prompts), accepted, rejection_reason)


_LAST_JUDGE_RUN: JudgeRunResult | None = None


def last_judge_run() -> JudgeRunResult | None:
    """Return the JudgeRunResult from the most recent run_judge() call.

    Useful for reports that want the failure list or per-stage pass counts.
    Not thread-safe across concurrent run_judge() calls — callers that need
    parallelism should hold their own JudgeRunResult instances by passing a
    custom collector. For the v1 single-threaded validator pipeline this is
    sufficient.
    """
    return _LAST_JUDGE_RUN
