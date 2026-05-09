"""Internal schema optimizer models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaField:
    tool_slug: str
    field_path: str
    text: str


@dataclass(frozen=True)
class SchemaFieldTokenCount:
    field: SchemaField
    tokens: int


@dataclass(frozen=True)
class ValidationResult:
    validation_cases_run: int
    passed: bool
    rejection_reason: str | None = None

