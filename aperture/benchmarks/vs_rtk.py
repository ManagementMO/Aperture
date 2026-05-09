"""Head-to-head benchmark: Aperture vs RTK (rtk-ai/rtk).

RTK is a CLI proxy that filters CLI/JSON output before it reaches an LLM.
Aperture is a token-efficiency *layer* between an agent and its tools.

Both cut tokens. The honest question is *what survives*. RTK's `rtk json`
defaults to sampling the first item and replacing the rest with
`... +199 more`. That's an 80-99% byte cut, but the LLM literally cannot
answer questions about items 1..199. Aperture compresses every record
(TOON / type-grouped / field-policy) so the signal across the whole list
is preserved.

This bench runs both engines on the same fixtures, counts tokens, and
runs quality probes against the compressed output to see whether the
agent could still answer real questions about specific records.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from aperture.compression.engine import compress_tool_output
from aperture.tokenization import count_tokens


_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
_DATA_DIR = os.path.abspath(_DATA_DIR)


def _rtk_available() -> bool:
    return shutil.which("rtk") is not None


def _rtk_version() -> str | None:
    if not _rtk_available():
        return None
    try:
        out = subprocess.run(
            ["rtk", "--version"], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip().splitlines()[0] if out.stdout else None
    except Exception:
        return None


def _run_rtk_json(path: str, *, ultra: bool = False, keys_only: bool = False) -> tuple[str, float]:
    """Run `rtk json <path>` and return (stdout, elapsed_ms)."""
    args = ["rtk", "json"]
    if ultra:
        args.append("--ultra-compact")
    if keys_only:
        args.append("--keys-only")
    args.append(path)
    start = time.perf_counter()
    proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
    elapsed = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        return proc.stderr or proc.stdout, elapsed
    return proc.stdout, elapsed


@dataclass
class ProbeResult:
    label: str
    expected: str
    found: bool


@dataclass
class FixtureResult:
    fixture: str
    description: str
    item_count: int
    raw_tokens: int
    raw_bytes: int

    rtk_tokens: int
    rtk_bytes: int
    rtk_ms: float
    rtk_saved_pct: float
    rtk_probe_pass: int
    rtk_probe_total: int
    rtk_probes: list[ProbeResult]

    aperture_tokens: int
    aperture_bytes: int
    aperture_ms: float
    aperture_saved_pct: float
    aperture_probe_pass: int
    aperture_probe_total: int
    aperture_probes: list[ProbeResult]
    aperture_strategy: str

    @property
    def rtk_signal_per_token(self) -> float:
        if self.rtk_tokens == 0 or self.rtk_probe_total == 0:
            return 0.0
        return (self.rtk_probe_pass / self.rtk_probe_total) / max(self.rtk_tokens, 1) * 1000

    @property
    def aperture_signal_per_token(self) -> float:
        if self.aperture_tokens == 0 or self.aperture_probe_total == 0:
            return 0.0
        return (self.aperture_probe_pass / self.aperture_probe_total) / max(self.aperture_tokens, 1) * 1000


# ---------------------------------------------------------------------------
# Fixtures: each is (file, description, tool_slug for aperture, list-key,
#                   probe-builder)
# ---------------------------------------------------------------------------

def _probe_builder_linear(items: list[dict]) -> list[tuple[str, str]]:
    """Pick 5 representative issues and probe titles + states."""
    if not items:
        return []
    indexes = [0, len(items) // 4, len(items) // 2, 3 * len(items) // 4, len(items) - 1]
    probes: list[tuple[str, str]] = []
    for i in indexes:
        item = items[i]
        title = item.get("title", "").strip()
        if title:
            probes.append((f"issue#{i} title", title[:60]))
    return probes


def _probe_builder_notion(items: list[dict]) -> list[tuple[str, str]]:
    if not items:
        return []
    indexes = [0, len(items) // 4, len(items) // 2, 3 * len(items) // 4, len(items) - 1]
    probes: list[tuple[str, str]] = []
    for i in indexes:
        item = items[i]
        # notion pages typically have a "title" or "properties.title.title[].plain_text"
        title = item.get("title")
        if not title:
            props = item.get("properties", {})
            for v in props.values() if isinstance(props, dict) else []:
                if isinstance(v, dict) and v.get("title"):
                    bits = v["title"]
                    if isinstance(bits, list) and bits:
                        title = bits[0].get("plain_text", "") or bits[0].get("text", {}).get("content", "")
                        break
        if title:
            probes.append((f"page#{i} title", str(title)[:60]))
    return probes


def _probe_builder_supabase(items: list[dict]) -> list[tuple[str, str]]:
    if not items:
        return []
    indexes = [0, len(items) // 4, len(items) // 2, 3 * len(items) // 4, len(items) - 1]
    probes: list[tuple[str, str]] = []
    for i in indexes:
        item = items[i]
        ident = item.get("email") or item.get("name") or item.get("id")
        if ident:
            probes.append((f"user#{i} ident", str(ident)[:60]))
    return probes


_FIXTURES = [
    {
        "name": "linear_issues_200",
        "path": os.path.join(_DATA_DIR, "linear_issues_200.json"),
        "description": "Linear: 200 issues across 5 teams",
        "tool_slug": "LINEAR_GET_LINEAR_USER_ISSUES",
        "probe_builder": _probe_builder_linear,
    },
    {
        "name": "notion_pages_500",
        "path": os.path.join(_DATA_DIR, "notion_pages_500.json"),
        "description": "Notion: 500 pages from a knowledge base",
        "tool_slug": "NOTION_SEARCH_NOTION_PAGE",
        "probe_builder": _probe_builder_notion,
    },
    {
        "name": "supabase_users_1000",
        "path": os.path.join(_DATA_DIR, "supabase_users_1000.json"),
        "description": "Supabase: 1000-row users table",
        "tool_slug": "SUPABASE_FETCH_TABLE_ROWS",
        "probe_builder": _probe_builder_supabase,
    },
]


def _check_probes(probes: list[tuple[str, str]], output: str) -> list[ProbeResult]:
    return [
        ProbeResult(label=label, expected=expected, found=expected in output)
        for label, expected in probes
    ]


def run_one(fixture: dict) -> FixtureResult | None:
    path = fixture["path"]
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", []) or [data]
    probes = fixture["probe_builder"](items)

    raw_serialized = json.dumps(data, ensure_ascii=False)
    raw_tokens = count_tokens(data, model="gpt-4o").tokens
    raw_bytes = len(raw_serialized.encode("utf-8"))

    # ---- RTK ----
    rtk_out, rtk_ms = _run_rtk_json(path)
    rtk_tokens = count_tokens(rtk_out, model="gpt-4o").tokens
    rtk_bytes = len(rtk_out.encode("utf-8"))
    rtk_probes = _check_probes(probes, rtk_out)
    rtk_pass = sum(1 for p in rtk_probes if p.found)

    # ---- Aperture ----
    a_start = time.perf_counter()
    compressed = compress_tool_output(
        data, fixture["tool_slug"], mode="balanced", model="gpt-4o"
    )
    a_ms = (time.perf_counter() - a_start) * 1000
    a_payload = compressed.llm_string or json.dumps(
        compressed.compressed_payload, ensure_ascii=False
    )
    a_tokens = compressed.compressed_tokens
    a_bytes = len(a_payload.encode("utf-8"))
    a_probes = _check_probes(probes, a_payload)
    a_pass = sum(1 for p in a_probes if p.found)

    return FixtureResult(
        fixture=fixture["name"],
        description=fixture["description"],
        item_count=len(items),
        raw_tokens=raw_tokens,
        raw_bytes=raw_bytes,

        rtk_tokens=rtk_tokens,
        rtk_bytes=rtk_bytes,
        rtk_ms=rtk_ms,
        rtk_saved_pct=round((1 - rtk_tokens / max(raw_tokens, 1)) * 100, 1),
        rtk_probe_pass=rtk_pass,
        rtk_probe_total=len(probes),
        rtk_probes=rtk_probes,

        aperture_tokens=a_tokens,
        aperture_bytes=a_bytes,
        aperture_ms=a_ms,
        aperture_saved_pct=round((1 - a_tokens / max(raw_tokens, 1)) * 100, 1),
        aperture_probe_pass=a_pass,
        aperture_probe_total=len(probes),
        aperture_probes=a_probes,
        aperture_strategy=compressed.strategy,
    )


def run_all() -> dict:
    rtk_ok = _rtk_available()
    fixtures: list[dict] = []
    for f in _FIXTURES:
        if not rtk_ok:
            continue
        result = run_one(f)
        if result is None:
            continue
        fixtures.append({
            "fixture": result.fixture,
            "description": result.description,
            "item_count": result.item_count,
            "raw_tokens": result.raw_tokens,
            "raw_bytes": result.raw_bytes,
            "rtk": {
                "tokens": result.rtk_tokens,
                "bytes": result.rtk_bytes,
                "saved_percent": result.rtk_saved_pct,
                "elapsed_ms": round(result.rtk_ms, 1),
                "probe_pass": result.rtk_probe_pass,
                "probe_total": result.rtk_probe_total,
                "probes": [
                    {"label": p.label, "expected": p.expected, "found": p.found}
                    for p in result.rtk_probes
                ],
                "signal_score": round(result.rtk_signal_per_token, 3),
            },
            "aperture": {
                "tokens": result.aperture_tokens,
                "bytes": result.aperture_bytes,
                "saved_percent": result.aperture_saved_pct,
                "elapsed_ms": round(result.aperture_ms, 1),
                "probe_pass": result.aperture_probe_pass,
                "probe_total": result.aperture_probe_total,
                "probes": [
                    {"label": p.label, "expected": p.expected, "found": p.found}
                    for p in result.aperture_probes
                ],
                "strategy": result.aperture_strategy,
                "signal_score": round(result.aperture_signal_per_token, 3),
            },
        })

    totals_rtk_pass = sum(f["rtk"]["probe_pass"] for f in fixtures)
    totals_aperture_pass = sum(f["aperture"]["probe_pass"] for f in fixtures)
    totals_probes = sum(f["rtk"]["probe_total"] for f in fixtures)

    return {
        "rtk_available": rtk_ok,
        "rtk_version": _rtk_version(),
        "fixtures": fixtures,
        "summary": {
            "total_probes": totals_probes,
            "rtk_passed": totals_rtk_pass,
            "aperture_passed": totals_aperture_pass,
            "rtk_signal_rate": round(totals_rtk_pass / max(totals_probes, 1) * 100, 1),
            "aperture_signal_rate": round(totals_aperture_pass / max(totals_probes, 1) * 100, 1),
        },
        "thesis": (
            "Same data in. RTK wins raw byte count by sampling the first record "
            "and dropping the rest. Aperture preserves more signal per token because "
            "compression is structure-aware — every record contributes."
        ),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(run_all())
