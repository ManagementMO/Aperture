"""Schema optimization reports."""

from __future__ import annotations

from pathlib import Path

from aperture.observability.reports import schema_savings_report
from aperture.schema_optimizer.extract_fields import extract_description_fields
from aperture.schema_optimizer.fetch_schemas import fetch_tool_schemas
from aperture.schema_optimizer.rank_candidates import rank_schema_candidates
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates
from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields
from aperture.schema_optimizer.validator import set_description_at_path, validate_schema_rewrite
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import SchemaOptimizationResult


def optimize_schemas(live: bool = False) -> list[SchemaOptimizationResult]:
    """Run deterministic schema optimization over fixture or live schemas."""

    schemas = fetch_tool_schemas(live=live)
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

