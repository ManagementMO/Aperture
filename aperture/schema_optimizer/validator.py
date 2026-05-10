"""Validate that schema rewrites preserve behavior-relevant structure."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from aperture.schema_optimizer.budget import BudgetTracker
from aperture.schema_optimizer.models import ValidationResult

SAFETY_TERMS = {"delete", "send", "auth", "oauth", "token", "permission", "private", "public"}


def _parameters(schema: dict[str, Any]) -> dict[str, Any]:
    params = schema.get("parameters") or schema.get("input_schema") or {}
    return params if isinstance(params, dict) else {}


def _required(schema: dict[str, Any]) -> list[str]:
    params = _parameters(schema)
    return sorted(params.get("required") or [])


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    return dict(_parameters(schema).get("properties") or {})


def _types(schema: dict[str, Any]) -> dict[str, str | None]:
    return {name: prop.get("type") for name, prop in _properties(schema).items() if isinstance(prop, dict)}


def _safety_terms(text: str) -> set[str]:
    lower = text.lower()
    return {term for term in SAFETY_TERMS if term in lower}


def set_description_at_path(schema: dict, field_path: str, value: str) -> dict:
    """Return a copy of schema with one description path replaced."""

    output = deepcopy(schema)
    current: Any = output
    parts = field_path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value
    return output


def validate_schema_rewrite(
    original_schema: dict,
    candidate_schema: dict,
    validation_cases: list[dict] | None = None,
) -> ValidationResult:
    """Structural validation that a rewrite preserves behavior-relevant fields.

    This is the FAST path: no LLM call, just structural diffs (tool slug,
    parameter names, required fields, parameter types, safety-term retention).
    Cheap enough to run on every candidate during the rewrite phase.

    For v1 acceptance per handoff §13.3 cells 5-6, structural validation is
    NOT sufficient — the validator also needs to confirm behavioral
    equivalence by running prompts through an LLM judge (Haiku primary +
    Sonnet spot-check). That layer lives in `aperture/schema_optimizer/llm_judge.py`
    and is wired below as `validate_schema_rewrite_with_llm_judge`. Phase 5
    Week 6 implements `llm_judge.py`; until then it raises NotImplementedError.
    """

    cases_run = len(validation_cases or [{"case_id": "structural"}])
    if (original_schema.get("slug") or original_schema.get("name")) != (candidate_schema.get("slug") or candidate_schema.get("name")):
        return ValidationResult(cases_run, False, "tool_slug_changed")
    if sorted(_properties(original_schema)) != sorted(_properties(candidate_schema)):
        return ValidationResult(cases_run, False, "parameter_names_changed")
    if _required(original_schema) != _required(candidate_schema):
        return ValidationResult(cases_run, False, "required_fields_changed")
    if _types(original_schema) != _types(candidate_schema):
        return ValidationResult(cases_run, False, "parameter_types_changed")
    original_text = str(original_schema)
    candidate_text = str(candidate_schema)
    missing_safety = _safety_terms(original_text) - _safety_terms(candidate_text)
    if missing_safety:
        return ValidationResult(cases_run, False, "safety_terms_removed:" + ",".join(sorted(missing_safety)))
    return ValidationResult(cases_run, True, None)


def validate_schema_rewrite_with_llm_judge(
    original_schema: dict,
    candidate_schema: dict,
    prompts: list[str],
    *,
    judge_model: str = "claude-haiku-4-5",
    spot_check_model: str = "claude-sonnet-4-5",
    spot_check_fraction: float = 0.10,
    similar_tools: list[dict] | None = None,
    live: bool = False,
    replay_dir: str | Path | None = None,
    tracker: BudgetTracker | None = None,
    candidate_index: int = 0,
    seed: int = 1,
) -> ValidationResult:
    """Behavioral validation: a rewrite is accepted only if a Claude model
    selects the same tool and extracts the same parameters across all prompts.

    Per handoff §6.4 + decision #4:
        - Run every prompt through `judge_model` (Haiku) with original schema,
          then with candidate schema. Compare `tool_use.name` and normalized args.
        - For 10% of prompts (configurable via `spot_check_fraction`), also run
          through `spot_check_model` (Sonnet) and reject if Sonnet disagrees
          with Haiku on either selection or parameters.
        - Accept only if 100% of judged prompts and 100% of spot-checked
          prompts pass.
        - Disambiguation: include `similar_tools` (e.g. GITHUB_CREATE_ISSUE
          alongside GITHUB_CREATE_PULL_REQUEST) so the model has a real choice.

    Implementation lives in `aperture/schema_optimizer/llm_judge.py` and is
    constructed in Phase 5 Week 6. Calling this function before that phase
    raises NotImplementedError so misuse is loud.

    Tests for this function MUST use replay-recorded LLM responses
    (see `tests/schema_optimizer/replay/`) — never live LLM in CI per handoff §14.4.
    """

    try:
        from aperture.schema_optimizer.llm_judge import run_judge as _run_judge
    except ImportError as exc:
        raise NotImplementedError(
            "LLM judge not yet implemented; structural validation only. "
            "Phase 5 Week 6 fills in aperture/schema_optimizer/llm_judge.py. "
            "Until then call validate_schema_rewrite() instead."
        ) from exc

    return _run_judge(
        original_schema=original_schema,
        candidate_schema=candidate_schema,
        prompts=prompts,
        judge_model=judge_model,
        spot_check_model=spot_check_model,
        spot_check_fraction=spot_check_fraction,
        similar_tools=similar_tools or [],
        live=live,
        replay_dir=Path(replay_dir) if replay_dir is not None else None,
        tracker=tracker,
        candidate_index=candidate_index,
        seed=seed,
    )
