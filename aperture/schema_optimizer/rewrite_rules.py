"""Deterministic schema description rewrite rules."""

from __future__ import annotations

import re

from aperture.schema_optimizer.models import SchemaField


def _compact(text: str) -> str:
    cleaned = " ".join(text.split())
    replacements = [
        (r"\bCreates a new\b", "Create"),
        (r"\bCreate a new\b", "Create"),
        (r"\bRetrieves\b", "Get"),
        (r"\bReturns\b", "Return"),
        (r"\bThis tool allows you to\b", ""),
        (r"\bYou must provide\b", "Required:"),
        (r"\bOptionally, you may include\b", "Optional:"),
        (r"\ba string containing the\b", ""),
        (r"\bthe specified\b", ""),
    ]
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
    return cleaned.strip().strip(".") + "."


def generate_schema_rewrite_candidates(field: SchemaField) -> list[str]:
    """Generate compact description rewrite candidates."""

    candidate = _compact(field.text)
    if len(candidate) >= len(field.text):
        words = field.text.split()
        candidate = " ".join(words[: min(len(words), 18)]).rstrip(".,") + "."
    return [candidate]

