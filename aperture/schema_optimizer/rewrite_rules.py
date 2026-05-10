"""Deterministic schema description rewrite rules.

Per handoff §6.3, we generate up to 3 candidates per field at increasing
compression levels. The Haiku judge (Phase 5 / Week 6) picks the most
aggressive candidate that preserves tool selection + parameter extraction
across 50 prompts. If two candidates collapse to the same string after
deduplication, only one is returned.
"""

from __future__ import annotations

import re

from aperture.schema_optimizer.models import SchemaField

# Light: rules a, c, d (handoff §6.3) — strip preambles, drop redundant type
# prose, normalize to imperative. Safest; usually retains all disambiguation.
_LIGHT_RULES: list[tuple[str, str]] = [
    (r"\bCreates a new\b", "Create"),
    (r"\bCreate a new\b", "Create"),
    (r"\bRetrieves\b", "Get"),
    (r"\bReturns\b", "Return"),
    (r"\bThis tool allows you to\b", ""),
    (r"\ba string containing the\b", ""),
    (r"\bthe specified\b", ""),
]

# Medium: light + rule b (collapse "You must provide…/Optionally, you may…"
# into "Required: …. Optional: …."). Keeps required/optional structure.
_MEDIUM_RULES: list[tuple[str, str]] = _LIGHT_RULES + [
    (r"\bYou must provide\b", "Required:"),
    (r"\bYou must specify\b", "Required:"),
    (r"\bOptionally, you may include\b", "Optional:"),
    (r"\bOptionally, you may specify\b", "Optional:"),
    (r"\bOptionally, you may provide\b", "Optional:"),
]

# Heavy: medium + rule e (compound-phrase shortenings). Most aggressive;
# more likely to be rejected by the validator.
_HEAVY_RULES: list[tuple[str, str]] = _MEDIUM_RULES + [
    (r"\brepository\b", "repo"),
    (r"\bauthenticated user\b", "user"),
    (r"\brecipient email address\b", "recipient"),
    (r"\bemail message\b", "email"),
    (r"\bGitHub repository\b", "GitHub repo"),
]


def _apply_rules(text: str, rules: list[tuple[str, str]]) -> str:
    cleaned = " ".join(text.split())
    for pattern, replacement in rules:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
    return cleaned.strip().strip(".") + "."


def _truncated(text: str, max_words: int = 18) -> str:
    """Last-resort fallback: truncate to first N words."""

    words = text.split()
    return " ".join(words[: min(len(words), max_words)]).rstrip(".,") + "."


def generate_schema_rewrite_candidates(field: SchemaField) -> list[str]:
    """Generate up to three compact description rewrite candidates.

    Returns candidates in order: [light, medium, heavy]. Duplicates are
    removed (e.g. when light and medium collapse to the same string because
    no medium-only rule matched). If every candidate is the same length or
    longer than the original, falls back to a 18-word truncation as a
    single-candidate result so the validator still has something to test.
    """

    light = _apply_rules(field.text, _LIGHT_RULES)
    medium = _apply_rules(field.text, _MEDIUM_RULES)
    heavy = _apply_rules(field.text, _HEAVY_RULES)

    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in (light, medium, heavy):
        if candidate in seen:
            continue
        if len(candidate) >= len(field.text):
            continue
        seen.add(candidate)
        candidates.append(candidate)

    if not candidates:
        candidates.append(_truncated(field.text))
    return candidates

