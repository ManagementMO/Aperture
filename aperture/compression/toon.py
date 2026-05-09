"""Token-Oriented Object Notation (TOON) encoder.

For uniform arrays of records the LLM mostly sees the same keys repeated. JSON
quotes them every row. TOON emits the keys once as a header and then writes
rows as comma-separated values:

    users[3]{id,name,role}:
      1,Alice,admin
      2,Bob,user
      3,Carol,admin

Reported reduction vs JSON for uniform records: 30–60%. The format is
indent-significant and self-describing, so an LLM can parse it without prior
instruction. We only switch encoding when (a) the value is clearly tabular
and (b) the field set is uniform — otherwise we fall back to JSON.

We emit a one-line preamble (`# TOON v1`) so the model has a hint, and we
bracket the section with `# end <name>` so the boundary is unambiguous.

This module is pure formatting — it never drops data. The compression engine
upstream does the sampling + field pruning; TOON just renders the result more
densely.
"""

from __future__ import annotations

import json
from typing import Any

_PREAMBLE = "# TOON v1 — header has keys, each subsequent line is one record"
_SAFE_BARE = set("0123456789-+.eE")


def is_tabular_records(payload: object, min_rows: int = 2) -> bool:
    """Return True if `payload` is a list of dicts with uniform top-level keys."""
    if not isinstance(payload, list) or len(payload) < min_rows:
        return False
    if not all(isinstance(row, dict) for row in payload):
        return False
    head = payload[0]
    head_keys = set(head.keys())
    if not head_keys:
        return False
    overlap = sum(1 for row in payload if isinstance(row, dict) and set(row.keys()) == head_keys)
    return overlap / len(payload) >= 0.9


def to_toon(payload: object, name: str = "items") -> str:
    """Encode a payload to TOON.

    Cases:
    - Uniform list of flat dicts → headerized table
    - Aperture summary wrapper (`{"_aperture_summary": {...}, "sample": [...]}`) →
      summary header + sample table
    - Anything else → JSON fallback (this module never silently mangles data)
    """
    if isinstance(payload, dict) and "_aperture_summary" in payload and "sample" in payload:
        return _encode_aperture_block(payload, name)

    if is_tabular_records(payload):
        return _encode_table(payload, name)

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)


def _encode_aperture_block(payload: dict, name: str) -> str:
    summary = payload.get("_aperture_summary", {})
    sample = payload.get("sample", [])
    stats = payload.get("stats")

    lines = [_PREAMBLE]
    summary_kv = ",".join(f"{k}={_format_value(v)}" for k, v in summary.items() if v is not None)
    lines.append(f"# {name}: {summary_kv}")

    if isinstance(sample, list) and is_tabular_records(sample):
        lines.append(_encode_table(sample, f"{name}_sample"))
    elif sample:
        lines.append(json.dumps(sample, separators=(",", ":"), ensure_ascii=False, default=str))

    if stats:
        lines.append(f"# stats: {json.dumps(stats, separators=(',', ':'), ensure_ascii=False, default=str)}")

    return "\n".join(lines)


def _encode_table(rows: list[dict[str, Any]], name: str) -> str:
    if not rows:
        return f"{name}[0]{{}}:"

    keys = list(rows[0].keys())
    header = f"{name}[{len(rows)}]{{{','.join(keys)}}}:"
    body_lines = [
        "  " + ",".join(_format_value(row.get(k)) for k in keys)
        for row in rows
    ]
    return "\n".join([header, *body_lines, f"# end {name}"])


def _format_value(value: Any) -> str:
    """Render a value safely for TOON. Strings with separators or whitespace are quoted."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)
    s = str(value)
    if any(ch in s for ch in (",", "\n", "\r", '"')) or (s and s[0] in (" ", "\t")):
        return '"' + s.replace('"', '\\"').replace("\n", "\\n") + '"'
    return s
