"""Validate that schema rewrites preserve behavior-relevant structure."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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
    """Validate that rewrite preserves tool selection and parameter behavior."""

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

