"""Quality-gated effort selection.

Given a raw tool payload, the user's ask, and a list of *required signals*
the agent's downstream answer must contain, walk Aperture's compression
modes from cheapest to most expensive and pick the first mode whose
compressed output still preserves every signal.

This is the operational definition of "still acceptable" the user asked for:
the schema return going to the LLM must contain the substrings (and dot-paths)
the agent will need to reason about. If `aggressive` would drop the assignee
login the user asked about, we step up to `low`. If that still drops it, we
go to `balanced`. The result is the most aggressive mode that's safe for
*this specific ask on this specific schema*.

Required signals are a permissive specification:
- Strings are checked as case-insensitive substrings of the JSON-stringified
  compressed payload (or the LLM-bound TOON string when applicable).
- Dot-paths like `assignee.login` are walked through the payload structure
  and required to resolve to a non-empty value.

Difficulty bracket → max aggression allowed:
- `simple`   — may attempt `aggressive`, then walk up toward `safe`
- `moderate` — max is `low` (aggressive prose-pruning disabled)
- `complex`  — max is `balanced` (must keep full prose, only flattening)
- `deep`     — max is `safe` (no flattening, only nulls/bookkeeping dropped)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from aperture.compression.engine import compress_tool_output
from aperture.routing.intelligent_effort import TaskComplexity, _analyze_query


# Mode order from cheapest (most aggressive) to most conservative.
_MODE_ORDER: tuple[str, ...] = ("aggressive", "low", "balanced", "safe", "off")

_MAX_AGGRESSION: dict[TaskComplexity, str] = {
    TaskComplexity.SIMPLE: "aggressive",
    TaskComplexity.MODERATE: "low",
    TaskComplexity.COMPLEX: "balanced",
    TaskComplexity.DEEP: "safe",
}


@dataclass
class ModeAttempt:
    mode: str
    tokens: int
    passed: bool
    failed_signals: list[str] = field(default_factory=list)


@dataclass
class QualityGateResult:
    selected_mode: str
    selected_tokens: int
    raw_tokens: int
    difficulty: str
    max_aggression: str   # most aggressive mode the difficulty bracket allows
    floor_mode: str       # alias for backwards compat (= max_aggression)
    attempts: list[ModeAttempt] = field(default_factory=list)
    reason: str = ""

    @property
    def saved_tokens(self) -> int:
        return max(0, self.raw_tokens - self.selected_tokens)

    @property
    def saved_percent(self) -> float:
        return (self.saved_tokens / self.raw_tokens * 100) if self.raw_tokens else 0.0


def _resolve_dot_path(payload: object, path: str) -> object | None:
    """Walk a dot-path; if a list is encountered, fan out and recurse."""
    parts = path.split(".")
    cursor: Any = payload
    for part in parts:
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        elif isinstance(cursor, list):
            results = []
            for item in cursor:
                if isinstance(item, dict) and part in item:
                    results.append(item[part])
            if not results:
                return None
            cursor = results
        else:
            return None
    return cursor


def _resolve_partial_path(payload: object, path: str) -> object | None:
    """Walk a dot-path until either it resolves fully or it hits a primitive
    that the engine produced by flattening. Returns the deepest non-empty
    value reached, or None if no part of the path resolves.

    Example: payload `{"assignee": "nikos"}`, path `"assignee.login"` →
    walk hits `"nikos"` after consuming `assignee`, returns `"nikos"`. The
    semantic is "the engine flattened this object but the identity value is
    still here."
    """
    parts = path.split(".")
    cursor: Any = payload
    deepest: Any = None
    for part in parts:
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
            if cursor not in (None, "", [], {}):
                deepest = cursor
        elif isinstance(cursor, list):
            results = []
            for item in cursor:
                if isinstance(item, dict) and part in item:
                    results.append(item[part])
            if not results:
                break
            cursor = results
            if cursor not in (None, "", [], {}):
                deepest = cursor
        else:
            # Primitive or missing — stop. If we already hit a non-empty
            # primitive, that's the engine's flattened representation.
            break
    return deepest


def _signal_present(payload: object, llm_string: str | None, signal: str) -> bool:
    """A signal is present if any of the following are true:

    1. The dot-path resolves fully to a non-empty value.
    2. A *prefix* of the dot-path resolves to a non-empty primitive (the
       engine flattened a nested object but kept the identity value).
    3. The signal appears as a case-insensitive substring in the rendered
       LLM-bound output (TOON string when applicable, else JSON).
    """
    is_path = "." in signal and not signal.startswith("/")
    if is_path:
        resolved = _resolve_dot_path(payload, signal)
        if resolved not in (None, "", [], {}):
            return True
        partial = _resolve_partial_path(payload, signal)
        if partial not in (None, "", [], {}):
            return True

    needle = signal.lstrip("/").lower()
    if not needle:
        return True

    # Try LLM-bound rendering first (TOON or normal JSON the LLM actually sees).
    if llm_string and needle in llm_string.lower():
        return True
    text = json.dumps(payload, default=str, ensure_ascii=False).lower()
    if needle in text:
        return True

    # Last fallback: leaf-name substring (assignee.login → "login").
    if is_path:
        leaf = signal.split(".")[-1].lower()
        if leaf and (
            (llm_string and leaf in llm_string.lower())
            or leaf in text
        ):
            return True
    return False


def _allowed_modes(max_aggression: str) -> list[str]:
    """Modes the difficulty bracket allows, walked cheapest first.

    `safe` is always the most conservative endpoint. We never *pick* `off`
    automatically — we fall through to it only if every allowed mode loses
    a required signal, in which case correctness wins.
    """
    start = _MODE_ORDER.index(max_aggression)
    safe_idx = _MODE_ORDER.index("safe")
    return list(_MODE_ORDER[start: safe_idx + 1])


def select_mode_for_quality(
    raw_payload: object,
    tool_slug: str,
    required_signals: list[str] | None = None,
    ask: str | None = None,
    model: str | None = "gpt-4o",
    task: str | None = None,
    explicit_required_fields: list[str] | None = None,
    difficulty_override: TaskComplexity | None = None,
) -> QualityGateResult:
    """Find the most aggressive mode that preserves every required signal.

    Args:
        raw_payload: The raw Composio tool result.
        tool_slug: Which tool produced it.
        required_signals: Substrings or dot-paths the compressed output MUST
            still contain. If empty, falls back to the most aggressive mode
            allowed by the difficulty bracket.
        ask: The user's natural-language question (used to classify difficulty
            when `difficulty_override` is None).
        model: Tokenizer hint.
        task: Optional task name for task-aware compression.
        explicit_required_fields: Forwarded to the compression engine as
            protected fields (engine-level guarantees vs. gate-level checks).
        difficulty_override: Bypass the heuristic and force a difficulty.
    """
    required_signals = required_signals or []
    difficulty = difficulty_override or _analyze_query(ask)
    max_aggression = _MAX_AGGRESSION[difficulty]

    from aperture.tokenization import count_tokens

    raw_tokens = count_tokens(raw_payload, model).tokens
    attempts: list[ModeAttempt] = []

    for mode in _allowed_modes(max_aggression):
        result = compress_tool_output(
            raw_payload,
            tool_slug,
            mode=mode,
            model=model,
            task=task,
            required_fields=explicit_required_fields,
        )
        compressed_payload = result.compressed_payload
        llm_string = result.llm_string

        failed = [
            sig for sig in required_signals
            if not _signal_present(compressed_payload, llm_string, sig)
        ]
        passed = not failed
        attempts.append(ModeAttempt(
            mode=mode,
            tokens=result.compressed_tokens,
            passed=passed,
            failed_signals=failed,
        ))

        if passed:
            reason = (
                f"ask difficulty={difficulty.value} → max_aggression={max_aggression}; "
                f"mode={mode} preserved all {len(required_signals)} required signals"
            )
            return QualityGateResult(
                selected_mode=mode,
                selected_tokens=result.compressed_tokens,
                raw_tokens=raw_tokens,
                difficulty=difficulty.value,
                max_aggression=max_aggression,
                floor_mode=max_aggression,
                attempts=attempts,
                reason=reason,
            )

    # No mode in the allowed range satisfied the gate — fall through to `off`
    # so the agent at least gets the raw payload (correctness over cost).
    raw_attempt = ModeAttempt(
        mode="off",
        tokens=raw_tokens,
        passed=True,
        failed_signals=[],
    )
    attempts.append(raw_attempt)
    fail_summary = ", ".join(
        f"{a.mode}({len(a.failed_signals)} missing)" for a in attempts if not a.passed
    )
    reason = (
        f"ask difficulty={difficulty.value} → max_aggression={max_aggression}; "
        f"no allowed mode preserved every signal ({fail_summary}); "
        "falling through to off (raw)"
    )
    return QualityGateResult(
        selected_mode="off",
        selected_tokens=raw_tokens,
        raw_tokens=raw_tokens,
        difficulty=difficulty.value,
        max_aggression=max_aggression,
        floor_mode=max_aggression,
        attempts=attempts,
        reason=reason,
    )
