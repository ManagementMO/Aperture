"""Deterministic schema description rewrite rules.

Per handoff §6.3, we generate up to three candidates per field at increasing
compression levels. The Haiku judge (Phase 5 / Week 6) picks the most
aggressive candidate that preserves tool selection + parameter extraction
across the prompt set. If two candidates collapse to the same string after
deduplication, only one is returned.

Design principles:

1. **Imperative, not third-person.** ``Retrieves a list of`` → ``List``,
   ``Queries`` → ``Query``. LLMs handle imperative tool descriptions well;
   they don't need narration.
2. **Drop redundant type prose.** ``A string containing the X`` → ``The X``.
   The JSON schema already declares the type.
3. **Collapse required/optional sentences.** ``You must provide A and B.
   Optionally, you may include C.`` → ``Required: A, B. Optional: C.``
4. **Compound shortenings.** ``GitHub repository`` → ``repo``,
   ``database identifier`` → ``database id``, ``email message`` → ``email``.
   Heavy level only — these can lose disambiguation that the LLM judge will
   reject.
5. **Never truncate.** A truncation fallback risks dropping safety/auth
   keywords. If the rules can't compress, return ``[]`` and let the upper
   layer mark the field ``no_token_reduction``.
"""

from __future__ import annotations

import re

from aperture.schema_optimizer.models import SchemaField

# ---------------------------------------------------------------------------
# Light rules — imperative + type-prose drops. Smallest blast radius.

_LIGHT_RULES: list[tuple[str, str]] = [
    # Imperative-verb normalization (third-person → imperative).
    (r"\bRetrieves\b", "Get"),
    (r"\bReturns\b", "Return"),
    (r"\bCreates a new\b", "Create"),
    (r"\bCreate a new\b", "Create"),
    (r"\bQueries\b", "Query"),
    (r"\bSearches\b", "Search"),
    (r"\bDeletes\b", "Delete"),
    (r"\bUpdates\b", "Update"),
    (r"\bSends\b", "Send"),
    (r"\bAdds\b", "Add"),
    (r"\bRemoves\b", "Remove"),
    (r"\bLists\b", "List"),
    (r"\bGets\b", "Get"),
    (r"\bFetches\b", "Fetch"),
    (r"\bUploads\b", "Upload"),
    (r"\bDownloads\b", "Download"),
    # Verbose preambles to drop entirely.
    (r"\bThis tool allows you to\b", ""),
    (r"\bThis tool will\b", ""),
    (r"\bThis function will\b", ""),
    (r"\bThis function\b", ""),
    (r"\bThe function\b", ""),
    (r"\bThis API\b", ""),
    (r"\bThe API\b", ""),
    (r"\bThis endpoint\b", ""),
    # Type-prose drops — JSON schema already declares the type.
    (r"\bA string containing the\b", ""),
    (r"\bA string containing\b", ""),
    (r"\bA string with the\b", ""),
    (r"\bThe string\b", "The"),
    (r"\bAn integer representing the\b", "The"),
    (r"\bAn integer\b", "Integer"),
    (r"\bA number representing\b", ""),
    (r"\bA boolean indicating\b", "Whether"),
    (r"\bA boolean\b", "Boolean"),
    # "the specified/given/provided X" → "X". Schema params are always provided.
    (r"\bthe specified\b", ""),
    (r"\bthe given\b", ""),
    (r"\bthe provided\b", ""),
    (r"\ba specified\b", "a"),
    (r"\ba list of\b", ""),
    (r"\ban instance of\b", ""),
]

# ---------------------------------------------------------------------------
# Medium rules — collapse required/optional sentences + drop "connected user"
# noise. Larger blast radius but preserves all parameter mentions.

_MEDIUM_RULES: list[tuple[str, str]] = _LIGHT_RULES + [
    # Required/optional structure.
    (r"\bYou must provide the\b", "Required:"),
    (r"\bYou must provide\b", "Required:"),
    (r"\bYou must specify the\b", "Required:"),
    (r"\bYou must specify\b", "Required:"),
    (r"\bYou must include\b", "Required:"),
    # Anchor "Requires" → "Required:" only at sentence boundaries (start of
    # string, after a period, or after a bullet) so we don't mangle prose like
    # "A filter that requires the user to authenticate" → "...Required: user...".
    (r"(^|\.\s+)Requires the\b", r"\1Required:"),
    (r"(^|\.\s+)Requires that you\b", r"\1Required:"),
    (r"(^|\.\s+)Requires\b", r"\1Required:"),
    (r"\bOptionally, you may include\b", "Optional:"),
    (r"\bOptionally, you may specify\b", "Optional:"),
    (r"\bOptionally, you may provide\b", "Optional:"),
    (r"\bOptionally, you can\b", "Optional:"),
    (r"\bYou may optionally\b", "Optional:"),
    (r"\band may include\b", "Optional:"),
    (r"\band can optionally specify\b", "Optional:"),
    (r"\band can include\b", "Optional:"),
    (r"\band can also include\b", "Optional:"),
    # "for the connected user/account" — drop, that context is always implicit.
    (r"\bfor the connected user account\b", ""),
    (r"\bfor the connected account\b", ""),
    (r"\bfor the authenticated user\b", ""),
    (r"\bin the connected account\b", ""),
    (r"\bavailable to the connected user account\b", "available to the user"),
    (r"\bavailable to the connected user\b", "available to the user"),
    # Outcome-clause simplifications.
    (r"\bto filter the returned issues\b", "to filter results"),
    (r"\bto filter the returned\b", "to filter"),
    (r"\bto retrieve matching\b", ""),
    (r"\bsearch operation\b", "search"),
    (r"\bquery string\b", "query"),
    (r"\bsearch query\b", "query"),
]

# ---------------------------------------------------------------------------
# Heavy rules — compound shortenings. Higher false-reject rate from the LLM
# judge, so always run the structural validator + judge before accepting.

_HEAVY_RULES: list[tuple[str, str]] = _MEDIUM_RULES + [
    # Repository terminology.
    (r"\bGitHub repository owner username\b", "owner"),
    (r"\brepository owner username\b", "owner"),
    (r"\bGitHub repository\b", "repo"),
    (r"\brepository name\b", "repo name"),
    (r"\brepository\b", "repo"),
    # Auth/user terminology — keep "user" so the judge spots permission scope.
    (r"\bauthenticated user\b", "user"),
    # Email / messaging terminology.
    (r"\brecipient email address\b", "recipient"),
    (r"\bemail message[s]?\b", "email"),
    (r"\bemail conversation[s]?\b", "email"),
    (r"\bemail address\b", "email"),
    (r"\bemail thread[s]?\b", "thread"),
    # Filtering / pagination.
    (r"\bfiltering or sorting options\b", "filter, sort"),
    (r"\bpagination options\b", "pagination"),
    (r"\bsearch terms\b", "search"),
    (r"\bdatabase identifier\b", "database id"),
    (r"\bunique identifier\b", "id"),
    (r"\bMaximum number of\b", "Max"),
    (r"\bMinimum number of\b", "Min"),
    # NB: dropped a previous "\bnumber of\b → n" because it mangled prose like
    # "the number of seconds" → "the n seconds". The "Maximum/Minimum number of"
    # rules above cover the high-frequency case.
    # Date/time.
    (r"\btimestamp value\b", "timestamp"),
    # Drop final "options" filler.
    (r"\boptions to filter\b", "to filter"),
    (r"\boptions for\b", "for"),
]

# Tracking which rules fire helps debug "why didn't this compress more".
# Not exposed publicly; used by the report generator if the user wants a diff.

_PUNCT_FIXUPS: list[tuple[str, str]] = [
    (r"\s+,", ","),
    (r"\s+\.", "."),
    # "Required: X Y Z Optional: A" → "Required: X Y Z. Optional: A"
    # Insert a missing period between a Required: clause and Optional: clause.
    (r"([^.])\s+Optional:", r"\1. Optional:"),
    (r",\s*Optional:", ". Optional:"),
    (r"\.\s*\.", "."),  # collapse "..".
    (r"\s+", " "),  # collapse runs of whitespace.
]


def _apply_rules(text: str, rules: list[tuple[str, str]]) -> str:
    cleaned = " ".join(text.split())
    for pattern, replacement in rules:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    for pattern, replacement in _PUNCT_FIXUPS:
        cleaned = re.sub(pattern, replacement, cleaned)
    cleaned = cleaned.strip()
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    return cleaned


def generate_schema_rewrite_candidates(field: SchemaField) -> list[str]:
    """Generate up to three compact description rewrite candidates.

    Returns candidates in order: ``[light, medium, heavy]``. Duplicates are
    removed (e.g. when light and medium collapse to the same string because
    no medium-only rule matched). If every candidate is the same length or
    longer than the original, returns ``[]`` so the upper layer can mark the
    field ``no_token_reduction`` cleanly — we explicitly do **not** truncate
    as a fallback, because truncation can drop safety/auth keywords.
    """

    light = _apply_rules(field.text, _LIGHT_RULES)
    medium = _apply_rules(field.text, _MEDIUM_RULES)
    heavy = _apply_rules(field.text, _HEAVY_RULES)

    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in (light, medium, heavy):
        if not candidate or candidate in seen:
            continue
        if len(candidate) >= len(field.text):
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates
