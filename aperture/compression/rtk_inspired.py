"""RTK-inspired enhancements grafted onto Aperture.

Two ideas worth stealing from rtk-ai/rtk:

1. **Ultra-summary line**: a one-line symbol-encoded headline at the top
   of the compressed payload. RTK does this for CLI output (`[ok]N [x]N
   [skip]N (123ms)`). We do it for known *tool-response shapes* — when
   the LLM asks for a GitHub repo overview we render
   `★28130 ⚡143 ⚙TS` in 6 tokens, then the full compressed payload.
   The summary lets the model answer single-fact questions without
   reading the body at all (huge for prompt-cache-heavy workflows).

2. **3-tier degradation tier marker**: every compressed payload now
   carries a tier — Full, Degraded, Passthrough — borrowed straight
   from RTK's parser. If quality probes pass and no fallback fired,
   we're Full. If we fell back from `low` → `safe` because a probe
   failed, we're Degraded. If compression itself raised, we ship the
   raw payload truncated and mark it Passthrough so the agent knows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Tier(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"
    PASSTHROUGH = "passthrough"


@dataclass
class UltraSummary:
    """A one-line symbolized headline for a known tool shape."""

    line: str
    fields_used: list[str]
    tool_slug: str


# ---------------------------------------------------------------------------
# Per-tool ultra-summary renderers. Each takes the raw payload (post unwrap)
# and returns either an UltraSummary or None when the shape doesn't match.
# Symbols are chosen to be 1 token each in tiktoken cl100k_base.
# ---------------------------------------------------------------------------

def _summarize_github_repo(payload: Any) -> UltraSummary | None:
    if not isinstance(payload, dict) or "stargazers_count" not in payload:
        return None
    stars = payload.get("stargazers_count", 0)
    issues = payload.get("open_issues_count", 0)
    forks = payload.get("forks_count", 0)
    lang = payload.get("language") or "?"
    full = payload.get("full_name") or payload.get("name") or "?"
    line = f"{full} | star:{stars} issue:{issues} fork:{forks} lang:{lang}"
    return UltraSummary(
        line=line,
        fields_used=["full_name", "stargazers_count", "open_issues_count", "forks_count", "language"],
        tool_slug="GITHUB_GET_A_REPOSITORY",
    )


def _summarize_github_issue_list(payload: Any) -> UltraSummary | None:
    if not isinstance(payload, list) or not payload:
        return None
    if not isinstance(payload[0], dict) or "number" not in payload[0]:
        return None
    open_n = sum(1 for it in payload if it.get("state") == "open")
    closed_n = len(payload) - open_n
    bug_n = sum(
        1 for it in payload
        if any("bug" in (l.get("name", "") if isinstance(l, dict) else str(l)).lower()
               for l in (it.get("labels") or []))
    )
    line = f"issues:{len(payload)} open:{open_n} closed:{closed_n} bug:{bug_n}"
    return UltraSummary(
        line=line,
        fields_used=["state", "labels"],
        tool_slug="GITHUB_LIST_ISSUES",
    )


def _summarize_linear_issues(payload: Any) -> UltraSummary | None:
    if not isinstance(payload, list) or not payload:
        return None
    if not isinstance(payload[0], dict) or "title" not in payload[0]:
        return None
    states: dict[str, int] = {}
    for it in payload:
        st = it.get("state")
        if isinstance(st, dict):
            st = st.get("name", "?")
        states[st or "?"] = states.get(st or "?", 0) + 1
    parts = " ".join(f"{k.lower()}:{v}" for k, v in sorted(states.items())[:4])
    line = f"linear total:{len(payload)} {parts}"
    return UltraSummary(
        line=line,
        fields_used=["state"],
        tool_slug="LINEAR_GET_LINEAR_USER_ISSUES",
    )


def _summarize_gmail_messages(payload: Any) -> UltraSummary | None:
    if isinstance(payload, dict):
        msgs = payload.get("messages") or payload.get("data") or []
    else:
        msgs = payload if isinstance(payload, list) else None
    if not isinstance(msgs, list) or not msgs:
        return None
    if not isinstance(msgs[0], dict):
        return None
    unread = sum(1 for m in msgs if "UNREAD" in (m.get("labelIds") or []))
    line = f"gmail msgs:{len(msgs)} unread:{unread}"
    return UltraSummary(
        line=line,
        fields_used=["labelIds"],
        tool_slug="GMAIL_FETCH_EMAILS",
    )


def _summarize_table_rows(payload: Any) -> UltraSummary | None:
    """Generic tabular payload — Supabase rows, Notion search results."""
    rows = payload if isinstance(payload, list) else None
    if not rows or not isinstance(rows[0], dict):
        return None
    cols = list(rows[0].keys())[:5]
    line = f"rows:{len(rows)} cols:{len(rows[0])} ({','.join(cols)})"
    return UltraSummary(
        line=line,
        fields_used=cols,
        tool_slug="TABLE",
    )


_SUMMARIZERS = {
    "GITHUB_GET_A_REPOSITORY": _summarize_github_repo,
    "GITHUB_LIST_ISSUES": _summarize_github_issue_list,
    "GITHUB_FIND_PULL_REQUESTS": _summarize_github_issue_list,
    "LINEAR_GET_LINEAR_USER_ISSUES": _summarize_linear_issues,
    "LINEAR_GET_LINEAR_ISSUE": _summarize_linear_issues,
    "GMAIL_FETCH_EMAILS": _summarize_gmail_messages,
    "GMAIL_SEARCH_EMAILS": _summarize_gmail_messages,
    "GMAIL_LIST_THREADS": _summarize_gmail_messages,
    "SUPABASE_FETCH_TABLE_ROWS": _summarize_table_rows,
    "NOTION_FETCH_DATA": _summarize_table_rows,
    "NOTION_SEARCH_NOTION_PAGE": _summarize_table_rows,
}


def render_ultra_summary(payload: Any, tool_slug: str) -> UltraSummary | None:
    """Pick a per-tool summarizer; fall back to the table-row generic
    when the tool slug isn't known but the shape is a list of dicts."""
    fn = _SUMMARIZERS.get(tool_slug)
    if fn is not None:
        result = fn(payload)
        if result is not None:
            return result
    return _summarize_table_rows(payload)


def classify_tier(
    *,
    raised: bool,
    fell_back: bool,
    probe_pass: int,
    probe_total: int,
) -> Tier:
    """Choose the three-tier degradation marker. Mirrors RTK's
    `ParseResult::{Full, Degraded, Passthrough}`."""
    if raised:
        return Tier.PASSTHROUGH
    if fell_back or (probe_total > 0 and probe_pass < probe_total):
        return Tier.DEGRADED
    return Tier.FULL
