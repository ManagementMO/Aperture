"""Deterministic benchmark evaluators."""

from __future__ import annotations

from typing import Any


def _unwrap_payload(payload: object) -> object:
    if isinstance(payload, dict) and payload.get("aperture_compressed") is True:
        return payload.get("data")
    return payload


def _contains_field(payload: Any, field: str) -> bool:
    if isinstance(payload, list):
        return any(_contains_field(item, field) for item in payload)
    if isinstance(payload, dict):
        if field in payload:
            return True
        return any(_contains_field(item, field) for item in payload.values())
    return False


def field_presence_score(payload: object, fields: list[str]) -> float:
    """Return the fraction of fields found anywhere in payload."""

    if not fields:
        return 1.0
    unwrapped = _unwrap_payload(payload)
    found = sum(1 for field in fields if _contains_field(unwrapped, field))
    return found / len(fields)


def has_missing_critical_info(payload: object, critical_fields: list[str]) -> bool:
    """Return whether any critical field is absent."""

    return field_presence_score(payload, critical_fields) < 1.0


def exact_evaluator(actual: object, expected: object) -> bool:
    """Return exact equality for deterministic checks."""

    return actual == expected


def trace_comparison_evaluator(raw_calls: list[str], aperture_calls: list[str]) -> bool:
    """Return whether Aperture used no more unique tools than raw mode."""

    return set(aperture_calls).issubset(set(raw_calls))


def llm_judge_export(payload: object) -> dict:
    """Return a stub export object for optional human or LLM judging."""

    return {"judge_required": False, "payload": payload}

