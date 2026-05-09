"""Tokenize schema description fields."""

from __future__ import annotations

from aperture.schema_optimizer.models import SchemaField, SchemaFieldTokenCount
from aperture.tokenization.token_counter import count_tokens_for_payload


def tokenize_schema_fields(fields: list[SchemaField]) -> list[SchemaFieldTokenCount]:
    """Count tokens for schema description fields."""

    return [SchemaFieldTokenCount(field=field, tokens=count_tokens_for_payload(field.text).tokens) for field in fields]

