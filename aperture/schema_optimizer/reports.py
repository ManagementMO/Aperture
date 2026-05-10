"""Schema optimization reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aperture import __version__
from aperture.observability.reports import schema_savings_report
from aperture.schema_optimizer.extract_fields import extract_description_fields
from aperture.schema_optimizer.fetch_schemas import fetch_tool_schemas
from aperture.schema_optimizer.rank_candidates import rank_schema_candidates
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates
from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields
from aperture.schema_optimizer.validator import set_description_at_path, validate_schema_rewrite
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import SchemaOptimizationResult


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
        candidate_text = generate_schema_rewrite_candidates(field)[0]
        candidate_schema = set_description_at_path(original_schema, field.field_path, candidate_text)
        validation = validate_schema_rewrite(original_schema, candidate_schema)
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


def write_schema_optimization_report(path: Path, live: bool = False) -> list[SchemaOptimizationResult]:
    """Write a Markdown schema optimization report."""

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
    accepted = [r for r in results if r.accepted]
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

