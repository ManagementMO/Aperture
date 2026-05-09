"""Caveman-style prose pruning.

Lifts the deterministic word lists from juliusbrussee/caveman (the rules,
not the architecture — caveman uses an LLM at runtime, we don't) to drop
fluff from detected prose fields. Runs ONLY on free-text fields like email
bodies, comments, and snippets, never on JSON keys, URLs, file paths, or
identifiers.

Three strictness levels (mapped to the engine's modes):

- `lite`     → drop filler / hedging / pleasantries.
- `full`     → also drop articles + connective fluff + apply phrase rewrites.
- `ultra`    → also collapse runs of whitespace and trim trailing punctuation.

Empirical reduction on long prose (caveman's own README):
- lite: ~25%
- full: ~46%
- ultra: ~65% (lossy on style, lossless on facts)

We are conservative by default: stopword pruning only kicks in at
`mode=aggressive` and only on string values longer than 200 chars.
"""

from __future__ import annotations

import re

# Word-only token regex (preserves hyphens, periods, apostrophes).
_TOKEN_RE = re.compile(r"\S+")

# Read-only zones — passages we never touch. URLs, file paths, code spans,
# inline backticks, env vars, version numbers.
_PROTECTED_PATTERNS = [
    re.compile(r"`[^`]+`"),
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"https?://\S+"),
    re.compile(r"\b/[\w./\-]+\b"),
    re.compile(r"\$[A-Z_]+"),
    re.compile(r"\b\d+(?:\.\d+){1,}\b"),  # version-ish
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),  # ALLCAPS identifiers / consts
]

_FILLER = {
    "just", "really", "basically", "actually", "simply", "essentially",
    "generally", "literally", "honestly", "obviously", "clearly", "very",
    "quite", "extremely", "absolutely", "totally", "definitely",
    "certainly", "perhaps", "probably",
}

_HEDGING_PHRASES = [
    re.compile(r"\bit might be worth\b", re.IGNORECASE),
    re.compile(r"\byou could consider\b", re.IGNORECASE),
    re.compile(r"\bit would be (?:good|nice|helpful) to\b", re.IGNORECASE),
    re.compile(r"\bI'd recommend\b", re.IGNORECASE),
    re.compile(r"\bI think\b", re.IGNORECASE),
]

_PLEASANTRIES = [
    re.compile(r"\bof course\b", re.IGNORECASE),
    re.compile(r"\bhappy to (?:help|assist)\b", re.IGNORECASE),
    re.compile(r"\bplease note that\b", re.IGNORECASE),
]

_ARTICLES = {"a", "an", "the"}

_CONNECTIVE_FLUFF = {
    "however", "furthermore", "additionally", "moreover", "nevertheless",
    "nonetheless", "hence", "thus", "therefore",
}

# Phrase rewrites applied verbatim — order matters (longer first).
_PHRASE_REWRITES = [
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bmake sure to\b", re.IGNORECASE), "ensure"),
    (re.compile(r"\bthe reason is because\b", re.IGNORECASE), "because"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bin spite of the fact that\b", re.IGNORECASE), "although"),
    (re.compile(r"\bat this point in time\b", re.IGNORECASE), "now"),
    (re.compile(r"\butilize\b", re.IGNORECASE), "use"),
    (re.compile(r"\bimplement a solution for\b", re.IGNORECASE), "fix"),
]

# Heuristics for "this looks like code" — skip pruning.
_LOOKS_LIKE_CODE = re.compile(
    r"^\s*(?:import |from |def |class |function |return |if\s*\(|for\s*\(|"
    r"while\s*\(|@\w+|\{\s*$|\}\s*$|var |let |const )",
    re.MULTILINE,
)


def looks_like_prose(text: object) -> bool:
    """Heuristic: long-ish, low symbol density, no obvious code markers."""
    if not isinstance(text, str) or len(text) < 200:
        return False
    if _LOOKS_LIKE_CODE.search(text):
        return False
    word_count = sum(1 for _ in _TOKEN_RE.finditer(text))
    if word_count == 0:
        return False
    symbols = sum(1 for c in text if c in "{}[]<>=;:|/\\")
    if symbols / len(text) > 0.06:
        return False
    return True


def _mask_protected(text: str) -> tuple[str, list[str]]:
    """Replace protected zones with `\x00N\x00` placeholders so they survive pruning."""
    saved: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return f"\x00{len(saved) - 1}\x00"

    masked = text
    for pattern in _PROTECTED_PATTERNS:
        masked = pattern.sub(_stash, masked)
    return masked, saved


def _restore_protected(text: str, saved: list[str]) -> str:
    def _restore(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        if 0 <= idx < len(saved):
            return saved[idx]
        return match.group(0)

    return re.sub(r"\x00(\d+)\x00", _restore, text)


def caveman_prune(text: str, level: str = "full") -> str:
    """Apply caveman-style pruning to a single string.

    Returns the original text unchanged if it doesn't look like prose.
    """
    if not looks_like_prose(text):
        return text

    masked, saved = _mask_protected(text)

    out = masked
    for pattern in _HEDGING_PHRASES + _PLEASANTRIES:
        out = pattern.sub("", out)
    for pattern, replacement in _PHRASE_REWRITES:
        out = pattern.sub(replacement, out)

    drop_words = set(_FILLER)
    if level in ("full", "ultra"):
        drop_words |= _ARTICLES | _CONNECTIVE_FLUFF

    if drop_words:
        def _filter_word(match: re.Match[str]) -> str:
            token = match.group(0)
            stripped = token.strip(".,;:!?'\"()").lower()
            if stripped in drop_words:
                return ""
            return token

        out = _TOKEN_RE.sub(_filter_word, out)

    if level == "ultra":
        out = re.sub(r"\s{2,}", " ", out)
        out = re.sub(r"\s+([.,;:!?])", r"\1", out)

    out = re.sub(r"[ \t]+", " ", out).strip()
    return _restore_protected(out, saved)


def prune_payload(payload: object, level: str = "full") -> object:
    """Walk a payload and apply `caveman_prune` to long prose strings only."""
    if isinstance(payload, dict):
        return {k: prune_payload(v, level) for k, v in payload.items()}
    if isinstance(payload, list):
        return [prune_payload(v, level) for v in payload]
    if isinstance(payload, str):
        return caveman_prune(payload, level)
    return payload
