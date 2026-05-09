"""Rank schema rewrite candidates."""

from __future__ import annotations

from aperture.schema_optimizer.models import SchemaFieldTokenCount


def rank_schema_candidates(fields: list[SchemaFieldTokenCount]) -> list[SchemaFieldTokenCount]:
    """Rank fields by token cost and usage impact if available."""

    return sorted(fields, key=lambda item: item.tokens, reverse=True)

