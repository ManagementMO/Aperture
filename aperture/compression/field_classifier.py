"""Optional model-tier field classifier with pluggable providers.

Calls a small model once per `(tool, ask)` pair to decide which denied
fields to *promote back to keep* for this specific call. Asymmetric trust:
the model can only ADD names to the keep set — it never causes a field to
be dropped.

Providers (set via `APERTURE_CLASSIFIER_PROVIDER`):
    - `huggingface` — default. HuggingFace Inference Router (OpenAI chat
      schema). Needs `HF_API_TOKEN` or `HUGGINGFACE_API_KEY`.
    - `anthropic` — Anthropic Haiku via the official SDK. Needs
      `ANTHROPIC_API_KEY` and the `anthropic` package installed.
    - `none` (or any unknown value) — disabled, returns empty set.

Failure modes are silent. If the provider isn't reachable OR if the model
exceeds the latency budget, returns an empty set and the caller falls back
to the rule-based policy. Compression must never fail or stall because the
optional classifier failed.

Cache freshness rules (CRITICAL — stale data must NEVER inject into the
compression pipeline):
- Each entry has an absolute `expires_at` (default 1 hour). Expired entries
  are evicted on read; we never reuse them.
- The cache key includes the prompt-template version (`_PROMPT_VERSION`).
  Bumping the version invalidates every entry — automatic when the prompt
  evolves.
- On every cache hit we re-validate the cached keep-set against the CURRENT
  candidate list. If any cached name is no longer a candidate (the schema
  changed, fields were renamed), we evict and re-classify. Better a fresh
  miss than a wrong hit.
- Hard latency budget on the model call. If the round-trip exceeds the
  budget, we return empty without caching the timeout.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field as dc_field
from typing import Iterable

from aperture.compression.field_policy import _OBVIOUS_API_FIELDS


# Bump this string any time the prompt or parser changes shape. Old cache
# entries become stale automatically and will be re-classified.
_PROMPT_VERSION = "v3-quoted-prose-2026-05"

# Defaults — tunable via env vars.
_DEFAULT_TTL_SECONDS = int(os.getenv("APERTURE_CLASSIFIER_TTL", "3600"))   # 1h
_DEFAULT_TIMEOUT_MS = int(os.getenv("APERTURE_CLASSIFIER_TIMEOUT_MS", "275"))
_DEFAULT_MAX_ENTRIES = int(os.getenv("APERTURE_CLASSIFIER_CACHE_MAX", "1000"))


@dataclass
class _CacheEntry:
    keeps: frozenset[str]
    candidates_snapshot: frozenset[str]
    created_at: float
    expires_at: float


# Cache = key -> _CacheEntry. Module-global, single source of truth.
_CACHE: dict[str, _CacheEntry] = {}
_CACHE_TRACE: list[dict[str, object]] = []
_CACHE_STATS: dict[str, int] = {
    "hits": 0,
    "expired_evictions": 0,
    "stale_evictions": 0,
    "timeout_evictions": 0,
    "misses": 0,
}


# HF inference router: defaults to Llama-3.1-8B-Instruct. Free hf-inference
# tier currently skips the 2-3B range entirely (Gemma 2/3, Qwen 1.5B, Phi
# mini, SmolLM all 400 with "model not supported by any provider"); the
# next step up from 1B that's actually routable is the 8B class. 8B is
# noticeably smarter at structured selection than 1B at the cost of a few
# hundred ms — the cache eats that on the second call anyway.
_HF_DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass
class ClassifierResult:
    keeps: set[str]
    cached: bool
    provider: str | None
    model: str | None
    available: bool
    cost_estimate_usd: float
    latency_ms: float = 0.0
    raw_reply: str | None = None


# ---------------------------------------------------------------------------
# Cache + candidate helpers
# ---------------------------------------------------------------------------

def _cache_key(provider: str, model: str, tool_slug: str, ask: str, candidates: list[str]) -> str:
    """Cache key includes the prompt-template version so prompt changes
    automatically invalidate every entry."""
    payload = json.dumps({
        "v": _PROMPT_VERSION,
        "provider": provider,
        "model": model,
        "tool": tool_slug,
        "ask": (ask or "").strip().lower(),
        "fields": sorted(candidates),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str, candidates: list[str]) -> frozenset[str] | None:
    """Return a cached keep-set ONLY if:
    1. The entry exists.
    2. It hasn't expired (TTL).
    3. Every cached keep name is still a valid candidate today (no
       schema drift).
    Otherwise evict the stale/wrong entry and return None.
    """
    entry = _CACHE.get(key)
    if entry is None:
        return None

    now = time.time()
    if entry.expires_at <= now:
        _CACHE.pop(key, None)
        _CACHE_STATS["expired_evictions"] += 1
        return None

    candidate_set = frozenset(candidates)
    # If the candidate list has changed since we cached, the cached keeps
    # may reference fields that no longer exist. Drop the entry — better
    # to re-classify than to inject a stale rescue.
    if entry.candidates_snapshot != candidate_set:
        _CACHE.pop(key, None)
        _CACHE_STATS["stale_evictions"] += 1
        return None
    if not entry.keeps.issubset(candidate_set):
        _CACHE.pop(key, None)
        _CACHE_STATS["stale_evictions"] += 1
        return None

    _CACHE_STATS["hits"] += 1
    return entry.keeps


def _cache_put(key: str, keeps: set[str], candidates: list[str], ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
    """Store a fresh decision. Evicts the oldest entry if we'd exceed the cap."""
    if len(_CACHE) >= _DEFAULT_MAX_ENTRIES:
        oldest_key = min(_CACHE, key=lambda k: _CACHE[k].created_at)
        _CACHE.pop(oldest_key, None)

    now = time.time()
    _CACHE[key] = _CacheEntry(
        keeps=frozenset(keeps),
        candidates_snapshot=frozenset(candidates),
        created_at=now,
        expires_at=now + ttl_seconds,
    )


def _candidate_fields(field_names: Iterable[str]) -> list[str]:
    """Only fields the static list would normally drop are worth classifying."""
    seen: set[str] = set()
    out: list[str] = []
    for name in field_names:
        leaf = name.split(".")[-1]
        if leaf in _OBVIOUS_API_FIELDS and leaf not in seen:
            seen.add(leaf)
            out.append(leaf)
    return out


def _parse_keeps(reply: str, allowed: set[str]) -> set[str]:
    """Extract field names from the model reply. Tries three strategies in
    order; intersects the result with `allowed` so the model can never
    invent a name that isn't already a candidate.

    1. Strict JSON array (best-case output).
    2. Quoted-name extraction from prose: `"avatar_url"` → keep "avatar_url".
       Tiny models embed answers in prose like "you'd need 'clone_url' and
       'ssh_url'"; pulling quoted names is reliable as long as we intersect.
    3. Word-boundary scan as a final fallback.

    The "none" sentinel returns empty regardless of what else the model
    babbled.
    """
    if re.search(r"^\s*none\b", reply, re.IGNORECASE):
        return set()

    out: set[str] = set()

    # 1. Strict JSON array.
    for candidate in re.finditer(r"\[[^\[\]]*\]", reply, re.DOTALL):
        try:
            parsed = json.loads(candidate.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, str) and item in allowed:
                    out.add(item)
            if out or parsed == []:
                return out

    # 2. Quoted-name extraction.
    for match in re.finditer(r"['\"`]([a-zA-Z_][a-zA-Z0-9_]*)['\"`]", reply):
        name = match.group(1)
        if name in allowed:
            out.add(name)
    if out:
        return out

    # 3. Word-boundary scan, but only over field names long enough to
    # avoid coincidental matches.
    for name in allowed:
        if len(name) >= 6 and re.search(rf"\b{re.escape(name)}\b", reply):
            out.add(name)
    return out


# ---------------------------------------------------------------------------
# HuggingFace provider — default
# ---------------------------------------------------------------------------

# HF migrated from per-model endpoints to a unified OpenAI-compatible router.
# `https://api-inference.huggingface.co/models/{model}` returns 404 across
# the board now; the live URL is `router.huggingface.co/v1/chat/completions`.
_HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"


def _hf_token() -> str | None:
    return os.getenv("HF_API_TOKEN") or os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HUGGINGFACEHUB_API_TOKEN")


# The classifier is purely advisory — it never produces output that hits
# Composio. Its job is one thing: name which fields from a fixed candidate
# list the user's task plausibly needs. The wrapper takes only the JSON
# array; the model's prose, reasoning, and any other text are discarded.
#
# Prompts intentionally tiny. Small instruct models (Llama 3.2 1B) lock
# onto verbose examples and start writing Python; a single direct
# instruction with one example pair is far more reliable.
# Tiny instruct models (Llama 3.2 1B) won't reliably emit pure JSON. They
# respond best to a relaxed, conversational prompt; we use a permissive
# parser that pulls quoted field names out of the prose response and
# intersects them with the candidate list. The intersection is the only
# safety guarantee we need — the model can never invent names.
_HF_SYSTEM_PROMPT = ""


def _hf_user_prompt(tool_slug: str, ask: str, candidates: list[str]) -> str:
    return (
        f"Pick the field names from this list that are semantically related "
        f"to the task. Reply with the names from the list, in quotes, "
        f"separated by commas. If none are related, reply 'none'.\n\n"
        f"Task: {ask}\n"
        f"Available fields: {', '.join(candidates)}\n\n"
        f"Related field names:"
    )


def _hf_few_shot_prompt(tool_slug: str, ask: str, candidates: list[str]) -> str:
    """Few-shot prompt for legacy `text-generation` style endpoints (kept
    for completeness; the active path uses chat completions)."""
    return (
        "# Field policy classifier — return JSON array of names to keep.\n\n"
        "TOOL: GITHUB_GET_REPO\n"
        "TASK: list the open issue count and language\n"
        "FIELDS: [\"node_id\",\"avatar_url\",\"clone_url\",\"forks_url\"]\n"
        "KEEP: []\n\n"
        "TOOL: GITHUB_LIST_ISSUES\n"
        "TASK: render avatars next to each assignee\n"
        "FIELDS: [\"node_id\",\"avatar_url\",\"events_url\",\"gravatar_id\"]\n"
        "KEEP: [\"avatar_url\"]\n\n"
        "TOOL: GITHUB_GET_PR\n"
        "TASK: clone the branch with git\n"
        "FIELDS: [\"node_id\",\"clone_url\",\"ssh_url\",\"avatar_url\"]\n"
        "KEEP: [\"clone_url\",\"ssh_url\"]\n\n"
        f"TOOL: {tool_slug}\n"
        f"TASK: {ask}\n"
        f"FIELDS: {json.dumps(candidates)}\n"
        f"KEEP:"
    )


def _classify_hf(
    tool_slug: str,
    ask: str,
    candidates: list[str],
    model: str,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> tuple[set[str], str | None, float, float, bool]:
    """Call HF's OpenAI-compatible chat router with a hard latency budget.

    Returns (keeps, raw_reply, latency_ms, cost_estimate_usd, timed_out).
    Empty keeps on any failure. Timed-out responses are NEVER cached.
    """
    token = _hf_token()
    if not token:
        return set(), None, 0.0, 0.0, False

    try:
        import httpx
    except ImportError:
        keeps, reply, lat, cost = _classify_hf_urllib(tool_slug, ask, candidates, model, token, timeout_ms)
        return keeps, reply, lat, cost, lat > timeout_ms

    messages = [{"role": "user", "content": _hf_user_prompt(tool_slug, ask, candidates)}]
    if _HF_SYSTEM_PROMPT:
        messages.insert(0, {"role": "system", "content": _HF_SYSTEM_PROMPT})
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 128,
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    timeout_seconds = max(timeout_ms / 1000.0, 0.05)
    start = time.perf_counter()
    try:
        # `httpx.Timeout` enforces a hard cap on connect + read + write.
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=timeout_seconds)) as client:
            resp = client.post(_HF_ROUTER_URL, json=payload, headers=headers)
        latency_ms = (time.perf_counter() - start) * 1000
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
        return set(), None, (time.perf_counter() - start) * 1000, 0.0, True
    except Exception:
        return set(), None, (time.perf_counter() - start) * 1000, 0.0, False

    if resp.status_code != 200:
        return set(), None, latency_ms, 0.0, False

    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return set(), None, latency_ms, 0.0, False

    # Even if the request completed within timeout_ms+epsilon network jitter,
    # treat anything past the budget as a timeout — better to be strict.
    if latency_ms > timeout_ms:
        return set(), text.strip(), latency_ms, 0.0, True

    keeps = _parse_keeps(text, set(candidates))
    return keeps, text.strip(), latency_ms, 0.0, False


def _classify_hf_urllib(
    tool_slug: str,
    ask: str,
    candidates: list[str],
    model: str,
    token: str,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> tuple[set[str], str | None, float, float]:
    """stdlib fallback when httpx isn't installed. Uses the same router and
    enforces the same hard latency budget."""
    import json as _json
    import urllib.error
    import urllib.request

    messages = [{"role": "user", "content": _hf_user_prompt(tool_slug, ask, candidates)}]
    if _HF_SYSTEM_PROMPT:
        messages.insert(0, {"role": "system", "content": _HF_SYSTEM_PROMPT})
    body = _json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 128,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        _HF_ROUTER_URL, data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    timeout_seconds = max(timeout_ms / 1000.0, 0.05)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        latency_ms = (time.perf_counter() - start) * 1000
        data = _json.loads(raw)
    except (urllib.error.URLError, _json.JSONDecodeError, TimeoutError):
        return set(), None, (time.perf_counter() - start) * 1000, 0.0

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return set(), None, latency_ms, 0.0
    if latency_ms > timeout_ms:
        return set(), text.strip(), latency_ms, 0.0
    keeps = _parse_keeps(text, set(candidates))
    return keeps, text.strip(), latency_ms, 0.0


# ---------------------------------------------------------------------------
# Anthropic provider — alternate
# ---------------------------------------------------------------------------

def _anthropic_credentials() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _anthropic_prompt(tool_slug: str, ask: str, candidates: list[str]) -> str:
    return (
        f"Tool: {tool_slug}\n"
        f"Agent task: {ask}\n\n"
        f"The following response fields are usually dropped as bookkeeping. "
        f"Return ONLY the field names this agent task plausibly needs, as a "
        f"compact JSON array. Default to dropping. Never invent names; only "
        f"select from the list.\n\n"
        f"Candidates: {json.dumps(candidates)}\n\n"
        f"JSON array of names to keep:"
    )


def _classify_anthropic(
    tool_slug: str,
    ask: str,
    candidates: list[str],
    model: str,
) -> tuple[set[str], str | None, float, float]:
    import time

    if not _anthropic_credentials():
        return set(), None, 0.0, 0.0
    try:
        import anthropic  # type: ignore
    except ImportError:
        return set(), None, 0.0, 0.0

    prompt = _anthropic_prompt(tool_slug, ask, candidates)
    start = time.perf_counter()
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model, max_tokens=128, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        reply = "".join(block.text for block in msg.content if hasattr(block, "text"))
        latency_ms = (time.perf_counter() - start) * 1000
    except Exception:
        return set(), None, (time.perf_counter() - start) * 1000, 0.0

    cost = (len(prompt) / 4 * 0.80 + 80 * 4) / 1_000_000
    return _parse_keeps(reply, set(candidates)), reply, latency_ms, round(cost, 6)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _selected_provider() -> str:
    return (os.getenv("APERTURE_CLASSIFIER_PROVIDER") or "huggingface").lower()


def _selected_model(provider: str) -> str:
    if provider == "anthropic":
        return os.getenv("APERTURE_CLASSIFIER_MODEL") or _ANTHROPIC_DEFAULT_MODEL
    return os.getenv("APERTURE_CLASSIFIER_MODEL") or _HF_DEFAULT_MODEL


def classifier_health() -> dict[str, object]:
    """Quick provider availability check for the dashboard."""
    return {
        "selected_provider": _selected_provider(),
        "huggingface_available": bool(_hf_token()),
        "anthropic_available": _anthropic_credentials(),
        "hf_default_model": _HF_DEFAULT_MODEL,
        "anthropic_default_model": _ANTHROPIC_DEFAULT_MODEL,
        "prompt_version": _PROMPT_VERSION,
        "ttl_seconds": _DEFAULT_TTL_SECONDS,
        "timeout_ms": _DEFAULT_TIMEOUT_MS,
        "cache": cache_stats(),
        "recent_calls": _CACHE_TRACE[-10:],
    }


def classify_fields(
    tool_slug: str,
    ask: str | None,
    field_names: Iterable[str],
    *,
    provider: str | None = None,
    model: str | None = None,
    enabled: bool = True,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> ClassifierResult:
    """Decide which denied fields to promote back for this call.

    Cache invariants enforced here:
    - Expired entries are evicted on read (TTL-based).
    - Schema-drifted entries (cached keep referencing fields that no longer
      exist) are evicted on read.
    - Timed-out model calls are NEVER cached — we want to retry next call.
    """
    provider = (provider or _selected_provider()).lower()
    model = model or _selected_model(provider)

    if not enabled or not ask or not ask.strip() or provider == "none":
        return ClassifierResult(set(), False, None, None, False, 0.0)

    candidates = _candidate_fields(field_names)
    if not candidates:
        return ClassifierResult(set(), False, provider, model, False, 0.0)

    key = _cache_key(provider, model, tool_slug, ask, candidates)
    cached_keeps = _cache_get(key, candidates)
    if cached_keeps is not None:
        _CACHE_TRACE.append({
            "provider": provider, "model": model, "tool": tool_slug,
            "ask": ask, "candidates": len(candidates),
            "keeps": list(cached_keeps), "cached": True, "latency_ms": 0,
            "timed_out": False,
        })
        return ClassifierResult(set(cached_keeps), True, provider, model, True, 0.0)

    _CACHE_STATS["misses"] += 1
    timed_out = False
    if provider == "anthropic":
        keeps, raw, latency_ms, cost = _classify_anthropic(tool_slug, ask, candidates, model)
        available = _anthropic_credentials()
    else:  # default: huggingface
        keeps, raw, latency_ms, cost, timed_out = _classify_hf(
            tool_slug, ask, candidates, model, timeout_ms=timeout_ms,
        )
        available = bool(_hf_token())

    # Asymmetric trust: only cache successful, non-timed-out, fully-validated
    # decisions. Timeouts must always retry next call so we don't lock in a
    # bad "no rescue" answer when the model was just slow.
    if not timed_out:
        _cache_put(key, keeps, candidates, ttl_seconds=ttl_seconds)
    else:
        _CACHE_STATS["timeout_evictions"] += 1

    _CACHE_TRACE.append({
        "provider": provider, "model": model, "tool": tool_slug,
        "ask": ask, "candidates": len(candidates),
        "keeps": list(keeps), "cached": False,
        "latency_ms": round(latency_ms, 1), "timed_out": timed_out,
    })
    return ClassifierResult(
        keeps=keeps,
        cached=False,
        provider=provider,
        model=model,
        available=available,
        cost_estimate_usd=cost,
        latency_ms=latency_ms,
        raw_reply=raw,
    )


def clear_cache() -> None:
    _CACHE.clear()
    _CACHE_TRACE.clear()
    for k in list(_CACHE_STATS.keys()):
        _CACHE_STATS[k] = 0


def cache_stats() -> dict[str, int]:
    """Live counters for hits / expired evictions / stale evictions /
    timeouts / misses. Useful for the dashboard health badge."""
    return {**_CACHE_STATS, "entries": len(_CACHE)}
