"""Schema optimization reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from aperture import __version__
from aperture.cache.policy import load_cache_policy
from aperture.observability.reports import schema_savings_report
from aperture.schema_optimizer.budget import BudgetTracker
from aperture.schema_optimizer.extract_fields import extract_description_fields
from aperture.schema_optimizer.fetch_schemas import fetch_tool_schemas
from aperture.schema_optimizer.rank_candidates import rank_schema_candidates
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates
from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields
from aperture.schema_optimizer.validator import (
    set_description_at_path,
    validate_schema_rewrite,
    validate_schema_rewrite_with_llm_judge,
)
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import SchemaOptimizationResult


MIN_OVERLAY_VALIDATION_CASES = 50
"""Minimum LLM-judged validation cases to land in the overlay.

Matches the handoff §6.4 plan-spec target. The prompt fixtures in
``aperture/schema_optimizer/prompts/*.jsonl`` ship at least 50 per toolkit
(github=50, gmail=50, linear=60, notion=50, slack=50), so this gate is
attainable with the inventory we have."""

logger = logging.getLogger(__name__)


def _toolkit_for_slug(tool_slug: str) -> str:
    """Map a tool slug like ``GITHUB_CREATE_ISSUE`` to ``github``."""

    head, _, _ = tool_slug.partition("_")
    return head.lower()


def load_prompts_by_toolkit(prompts_dir: Path | None = None) -> dict[str, list[str]]:
    """Load prompt strings from ``aperture/schema_optimizer/prompts/*.jsonl``.

    Returns a mapping from lower-case toolkit slug to a list of prompt strings.
    Each line in the JSONL is a dict with at least a ``prompt`` key.
    """

    if prompts_dir is None:
        prompts_dir = Path(__file__).resolve().parent / "prompts"
    prompts: dict[str, list[str]] = {}
    if not prompts_dir.exists():
        return prompts
    for path in sorted(prompts_dir.glob("*.jsonl")):
        toolkit = path.stem.lower()
        bucket: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("prompt"), str):
                bucket.append(obj["prompt"])
        if bucket:
            prompts[toolkit] = bucket
    return prompts


def _unwrap_openai_envelope(schema: dict) -> dict:
    """Mirror of extract_fields._unwrap_openai_envelope.

    Composio's default `client.tools.get()` returns OpenAI-shape
    `{function: {name, description, parameters}, type: 'function'}` dicts;
    the Anthropic provider returns the inner shape directly. The optimizer
    pipeline normalizes here so downstream code sees one shape.
    """
    if isinstance(schema, dict) and schema.get("type") == "function" and isinstance(schema.get("function"), dict):
        return schema["function"]
    return schema


def optimize_schemas(live: bool = False) -> list[SchemaOptimizationResult]:
    """Run deterministic schema optimization over fixture or live schemas."""

    raw_schemas = fetch_tool_schemas(live=live)
    schemas = [_unwrap_openai_envelope(s) for s in raw_schemas if isinstance(s, dict)]
    schema_by_tool = {schema.get("slug") or schema.get("name"): schema for schema in schemas}
    fields = []
    for schema in schemas:
        fields.extend(extract_description_fields(schema))

    results: list[SchemaOptimizationResult] = []
    for counted in rank_schema_candidates(tokenize_schema_fields(fields)):
        field = counted.field
        original_schema = schema_by_tool[field.tool_slug]
        candidates = generate_schema_rewrite_candidates(field)
        if not candidates:
            results.append(
                _empty_result(field, counted.tokens, "rewriter_no_candidate")
            )
            continue
        # Pick the most aggressive candidate that passes structural validation.
        chosen = _pick_best_structural_candidate(original_schema, field, candidates)
        candidate_text, candidate_schema, validation = chosen
        optimized_tokens = count_tokens_for_payload(candidate_text).tokens
        reduction = max(0, counted.tokens - optimized_tokens)
        accepted = validation.passed and reduction > 0
        results.append(
            SchemaOptimizationResult(
                tool_slug=field.tool_slug,
                field_path=field.field_path,
                original_text=field.text,
                optimized_text=candidate_text,
                original_tokens=counted.tokens,
                optimized_tokens=optimized_tokens,
                reduction_tokens=reduction,
                reduction_pct=(reduction / counted.tokens) if counted.tokens else 0.0,
                validation_cases_run=validation.validation_cases_run,
                validation_passed=validation.passed,
                accepted=accepted,
                rejection_reason=None if accepted else validation.rejection_reason or "no_token_reduction",
            )
        )
    return results


def _empty_result(field, original_tokens: int, reason: str) -> SchemaOptimizationResult:
    return SchemaOptimizationResult(
        tool_slug=field.tool_slug,
        field_path=field.field_path,
        original_text=field.text,
        optimized_text=field.text,
        original_tokens=original_tokens,
        optimized_tokens=original_tokens,
        reduction_tokens=0,
        reduction_pct=0.0,
        validation_cases_run=0,
        validation_passed=False,
        accepted=False,
        rejection_reason=reason,
    )


def _pick_best_structural_candidate(original_schema, field, candidates):
    """Return (text, schema, ValidationResult) for the most aggressive candidate
    that passes the structural validator, or the first candidate's failure if
    none passes — so the upper layer still sees a real rejection_reason.
    """

    last_failure = None
    for candidate_text in reversed(candidates):  # heaviest first
        candidate_schema = set_description_at_path(original_schema, field.field_path, candidate_text)
        validation = validate_schema_rewrite(original_schema, candidate_schema)
        if validation.passed:
            return candidate_text, candidate_schema, validation
        last_failure = (candidate_text, candidate_schema, validation)
    # Every candidate failed structural — return the first failure as the
    # canonical rejection so callers can see the reason.
    return last_failure


def optimize_schemas_with_llm_judge(
    *,
    live: bool = False,
    replay_dir: Path | None = None,
    tracker: BudgetTracker | None = None,
    prompts_by_toolkit: dict[str, list[str]] | None = None,
    judge_model: str = "claude-haiku-4-5",
    spot_check_model: str = "claude-sonnet-4-5",
    spot_check_fraction: float = 0.10,
    max_candidates: int | None = None,
    seed: int = 1,
) -> list[SchemaOptimizationResult]:
    """Optimize schemas with LLM-judged behavioral validation.

    Same deterministic pipeline as ``optimize_schemas()``, but each candidate
    is run through ``validate_schema_rewrite_with_llm_judge``. The judge's
    ``cases_run`` is reflected in the resulting ``SchemaOptimizationResult``,
    so only candidates with ``cases_run >= MIN_OVERLAY_VALIDATION_CASES``
    AND ``policy.operation_type not in {write, auth}`` will land in the
    overlay (see ``write_overlay``).

    Args:
        live: when True, calls real Anthropic. False uses ``replay_dir``.
        replay_dir: required for replay; can be passed in live mode to also
            record fresh outcomes for future replay.
        tracker: BudgetTracker that aborts mid-run when the cap is hit.
        prompts_by_toolkit: dict from toolkit slug (lower-case) to prompt list.
            Falls back to ``load_prompts_by_toolkit()`` when None.
        max_candidates: hard cap on how many top-ranked candidates to judge
            (useful for budget control during live runs).

    Returns the list of results — same shape as ``optimize_schemas()`` but
    with judge-gated ``accepted`` flags.
    """

    raw_schemas = fetch_tool_schemas(live=live)
    schemas = [_unwrap_openai_envelope(s) for s in raw_schemas if isinstance(s, dict)]
    schema_by_tool = {schema.get("slug") or schema.get("name"): schema for schema in schemas}
    fields = []
    for schema in schemas:
        fields.extend(extract_description_fields(schema))

    prompts_lookup = (
        prompts_by_toolkit if prompts_by_toolkit is not None else load_prompts_by_toolkit()
    )

    results: list[SchemaOptimizationResult] = []
    ranked = rank_schema_candidates(tokenize_schema_fields(fields))
    if max_candidates is not None:
        ranked = ranked[:max_candidates]

    for idx, counted in enumerate(ranked):
        if tracker is not None and tracker.exhausted():
            logger.info("optimize_schemas_with_llm_judge: budget exhausted at idx=%s", idx)
            break

        field = counted.field
        original_schema = schema_by_tool[field.tool_slug]
        candidates = generate_schema_rewrite_candidates(field)
        if not candidates:
            results.append(_empty_result(field, counted.tokens, "rewriter_no_candidate"))
            continue
        # Most aggressive candidate that passes structural — heaviest wins.
        chosen = _pick_best_structural_candidate(original_schema, field, candidates)
        candidate_text, candidate_schema, structural = chosen
        optimized_tokens = count_tokens_for_payload(candidate_text).tokens
        reduction = max(0, counted.tokens - optimized_tokens)

        # Structural pre-filter — cheap, cuts impossible candidates.
        if not structural.passed:
            results.append(
                SchemaOptimizationResult(
                    tool_slug=field.tool_slug,
                    field_path=field.field_path,
                    original_text=field.text,
                    optimized_text=candidate_text,
                    original_tokens=counted.tokens,
                    optimized_tokens=optimized_tokens,
                    reduction_tokens=reduction,
                    reduction_pct=(reduction / counted.tokens) if counted.tokens else 0.0,
                    validation_cases_run=structural.validation_cases_run,
                    validation_passed=False,
                    accepted=False,
                    rejection_reason=structural.rejection_reason or "structural_failed",
                )
            )
            continue

        toolkit = _toolkit_for_slug(field.tool_slug)
        prompts = prompts_lookup.get(toolkit, [])

        if not prompts:
            results.append(
                SchemaOptimizationResult(
                    tool_slug=field.tool_slug,
                    field_path=field.field_path,
                    original_text=field.text,
                    optimized_text=candidate_text,
                    original_tokens=counted.tokens,
                    optimized_tokens=optimized_tokens,
                    reduction_tokens=reduction,
                    reduction_pct=(reduction / counted.tokens) if counted.tokens else 0.0,
                    validation_cases_run=0,
                    validation_passed=False,
                    accepted=False,
                    rejection_reason=f"no_prompts_for_toolkit:{toolkit}",
                )
            )
            continue

        judge = validate_schema_rewrite_with_llm_judge(
            original_schema,
            candidate_schema,
            prompts=prompts,
            judge_model=judge_model,
            spot_check_model=spot_check_model,
            spot_check_fraction=spot_check_fraction,
            live=live,
            replay_dir=replay_dir,
            tracker=tracker,
            candidate_index=idx,
            seed=seed,
        )
        accepted = judge.passed and reduction > 0
        results.append(
            SchemaOptimizationResult(
                tool_slug=field.tool_slug,
                field_path=field.field_path,
                original_text=field.text,
                optimized_text=candidate_text,
                original_tokens=counted.tokens,
                optimized_tokens=optimized_tokens,
                reduction_tokens=reduction,
                reduction_pct=(reduction / counted.tokens) if counted.tokens else 0.0,
                validation_cases_run=judge.validation_cases_run,
                validation_passed=judge.passed,
                accepted=accepted,
                rejection_reason=None if accepted else (judge.rejection_reason or "no_token_reduction"),
            )
        )
    return results


def write_schema_optimization_report(
    path: Path,
    live: bool = False,
    *,
    use_llm_judge: bool = False,
    replay_dir: Path | None = None,
    tracker: BudgetTracker | None = None,
    prompts_by_toolkit: dict[str, list[str]] | None = None,
    max_candidates: int | None = None,
) -> list[SchemaOptimizationResult]:
    """Write a Markdown schema optimization report.

    By default uses ``optimize_schemas()`` (structural-only, fast, free) so
    this function is safe to call as a dry-run diagnostic. Pass
    ``use_llm_judge=True`` (with optional ``tracker`` and ``replay_dir``) to
    route through the canonical ``optimize_schemas_with_llm_judge()`` pipeline
    instead — the same path that produces a shippable overlay.
    """

    if use_llm_judge:
        results = optimize_schemas_with_llm_judge(
            live=live,
            replay_dir=replay_dir,
            tracker=tracker,
            prompts_by_toolkit=prompts_by_toolkit,
            max_candidates=max_candidates,
        )
    else:
        results = optimize_schemas(live=live)
    path.parent.mkdir(parents=True, exist_ok=True)
    detail_rows = []
    for result in results:
        detail_rows.append(
            f"| {result.tool_slug} | {result.field_path} | {result.original_tokens} | "
            f"{result.optimized_tokens} | {result.reduction_tokens} | {result.accepted} | {result.rejection_reason or ''} |"
        )
    details = "\n".join(
        [
            "| Tool | Field | Original | Optimized | Saved | Accepted | Rejection |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            *detail_rows,
        ]
    )
    path.write_text(schema_savings_report(results) + "\n\n## Details\n\n" + details + "\n", encoding="utf-8")
    return results


def _overlay_safe(result: SchemaOptimizationResult) -> bool:
    """Defense-in-depth: only ship overlays for tools we know are safe to rewrite.

    Three gates:
      1. ``result.accepted`` (judge or structural agreed)
      2. judge ran ``MIN_OVERLAY_VALIDATION_CASES`` or more cases
      3. ``policy.operation_type == "read"`` — positive list, not just
         ``not in {write, auth}``. ``unknown`` operation types are blocked
         until they're explicitly classified in policy.yaml. This prevents
         a misclassified write tool from sneaking into the overlay just
         because policy.yaml hasn't been updated to mark it write yet.
    """

    if not result.accepted:
        return False
    if result.validation_cases_run < MIN_OVERLAY_VALIDATION_CASES:
        return False
    policy = load_cache_policy(result.tool_slug)
    return policy.operation_type == "read"


def write_overlay(path: Path, results: list[SchemaOptimizationResult]) -> dict:
    """Persist accepted rewrites to `_overlay.json` for the proxy to consume.

    Per handoff §6.7: the optimizer can't write into Composio's registry
    (no internal access), so accepted rewrites land in this overlay file.
    The proxy's overlay layer (PR 4) loads this file and substitutes the
    optimized description into outbound `tools/list` and `GET_TOOL_SCHEMAS`
    responses.

    Schema:
        {
          "version": 1,
          "aperture_optimizer_version": "0.3.0",
          "generated_at": "2026-05-09T16:00:00Z",
          "tools": {
            "GITHUB_CREATE_ISSUE": {
              "description": {"path": "...", "original": "...", "optimized": "...",
                              "original_tokens": 68, "optimized_tokens": 28,
                              "reduction_pct": 0.59, "validation": {...}}
            }
          }
        }
    """
    accepted = [r for r in results if _overlay_safe(r)]
    by_tool: dict[str, dict] = {}
    for r in accepted:
        # Multiple fields per tool — top-level field name is the path's last segment.
        # Currently the pipeline only optimizes the top-level "description" field, so
        # tool entries have one entry keyed by "description".
        tool_entry = by_tool.setdefault(r.tool_slug, {})
        tool_entry[r.field_path] = {
            "original": r.original_text,
            "optimized": r.optimized_text,
            "original_tokens": r.original_tokens,
            "optimized_tokens": r.optimized_tokens,
            "reduction_tokens": r.reduction_tokens,
            "reduction_pct": round(r.reduction_pct, 4),
            "validation": {
                "cases_run": r.validation_cases_run,
                "passed": r.validation_passed,
            },
            "aperture_optimized": True,
            "aperture_optimizer_version": __version__,
        }

    document = {
        "version": 1,
        "aperture_optimizer_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tools": by_tool,
        "stats": {
            "total_results": len(results),
            "accepted": len(accepted),
            "rejected": len(results) - len(accepted),
            "total_tokens_saved": sum(r.reduction_tokens for r in accepted),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True))
    return document
