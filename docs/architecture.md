# Aperture v1 Architecture

This is the system overview for the v1 realignment. The branch `v1-realignment`
is the home for everything in this document; the `demo` branch is parallel
and untouched.

## High-level data flow

```
LLM client (Claude Desktop, custom agent, OpenAI Agents SDK, ...)
    │  HTTP  POST /mcp  (Streamable HTTP, JSON-RPC 2.0 + SSE)
    ▼
┌──────────────────────────────────────────────────────────────┐
│  aperture/proxy/                                              │
│                                                                │
│   server.py        mcp.server.lowlevel.Server                  │
│   router.py        dispatch by meta-tool slug                  │
│   intercept/       per-meta-tool handlers                      │
│     search_tools.py         cache + overlay + tokenize         │
│     multi_execute.py        partial-batch cache fan-out        │
│     get_tool_schemas.py     overlay + tokenize                 │
│     manage_connections.py   tokenize, never cache              │
│     workbench.py            tokenize, never cache              │
│     bash_tool.py            tokenize, never cache              │
│   cache_bridge.py  → aperture.cache.maybe_execute_with_cache   │
│   tokenize.py      async LRU around count_tokens_for_payload   │
│   attribution.py   build TokenAttributionEvent + emit          │
│   session.py       per-MCP-connection session+turn registry    │
│   upstream.py      mcp.client.streamablehttp_client to         │
│                    Composio's MCP URL                           │
│   errors.py        @safe(fallback) — enrichment never blocks   │
│                    forwarding                                   │
└──────────────────────────────────────────────────────────────┘
    │  HTTPX  POST  https://backend.composio.dev/tool_router/{session_id}/mcp
    ▼
Composio Tool Router  →  external APIs (GitHub, Gmail, ...)
```

## Where each component lives

| v1 Component | Owner module | Backed by |
|---|---|---|
| A. Cross-agent execution cache | `aperture/cache/` (interceptor, key_builder, normalizer, policy.yaml, redis_store, search_tools_cache, bypass) | Redis or in-memory store; deny-by-default policy |
| B. Token attribution observability | `aperture/observability/` (events, event_emitter, event_log_sqlite, aggregations, api_endpoints, reports, trace) | SQLite default log + JSONL secondary; FastAPI v3.1 endpoints |
| C. Schema description optimizer | `aperture/schema_optimizer/` (fetch, extract, tokenize, rank, rewrite_rules, validator, llm_judge, budget, reports) | Anthropic Haiku judge + Sonnet spot-check; structural pre-filter; replay-mode for CI |

## Key invariants

1. **The proxy never blocks the LLM response on enrichment.** Cache lookup,
   tokenization, and overlay are decorated with `@safe(fallback_value=...)` —
   any exception or timeout falls back and the upstream forward proceeds.
   See `aperture/proxy/errors.py`.
2. **Cache keys carry policy version.** Format
   `aperture:v1:p1:{scope}:{scope_id}:{tool_slug}:{sha256(normalized_params)}`.
   Bumping the YAML's `version:` field invalidates all keys at the `p1:` segment.
3. **Cache keys carry scope identity.** Public-scope keys reject when a
   `connected_account_id` is present in the request context, preventing
   leakage of personalized data through nominally-public reads.
4. **Write/auth tools are never cacheable.** Enforced both in the YAML
   (every entry classified `operation_type: write|auth` has `cacheable: false`)
   and in the runtime via `key_builder.py`'s gate.
5. **Anthropic's `count_tokens` API is opt-in.** Default tokenization for
   Claude models uses cl100k_base via tiktoken (marked `approximate=True`).
   Setting `APERTURE_USE_ANTHROPIC_TOKENIZER=true` switches to the real API,
   sending payloads to Anthropic — privacy-relevant; document for users.
6. **No live LLM in CI.** All schema-optimizer LLM-judge tests load
   recorded `JudgeOutcome` JSON files from `tests/schema_optimizer/replay/`.
   `live=True` is gated on `ANTHROPIC_API_KEY` and an explicit flag.
7. **The validator is two-stage.** Haiku judges every prompt; Sonnet
   spot-checks 10% of accepted prompts. Reject if either disagrees on
   tool selection or normalized parameter extraction.

## Configuration surface

Via env vars (read by `aperture.config.ApertureConfig` and `aperture.proxy.config.ProxyConfig`):

| Env var | Default | Used by |
|---|---|---|
| `COMPOSIO_API_KEY` | — | live Composio paths (live_check, schema fetcher) |
| `COMPOSIO_USER_ID` | `default` | live Composio session creation and proxy context fallback |
| `COMPOSIO_CONNECTED_ACCOUNT_ID` | — | proxy/cache context fallback for account-scoped calls |
| `ANTHROPIC_API_KEY` | — | LLM judge live mode + Anthropic tokenizer |
| `APERTURE_USE_ANTHROPIC_TOKENIZER` | `false` | enables real Claude tokenizer (privacy) |
| `APERTURE_PROXY_HOST` | `127.0.0.1` | proxy bind |
| `APERTURE_PROXY_PORT` | `8001` | proxy bind |
| `APERTURE_COMPOSIO_MCP_URL_TEMPLATE` | `https://backend.composio.dev/tool_router/{session_id}/mcp` | upstream URL template |
| `APERTURE_PROXY_LOG_LEVEL` | `INFO` | proxy log verbosity |
| `APERTURE_PROXY_PARTIAL_BATCH` | `true` | MULTI_EXECUTE partial-batch cache |
| `APERTURE_PROXY_UPSTREAM_TIMEOUT` | `30.0` | seconds |
| `APERTURE_REDIS_URL` | — | Redis backing for the cache |
| `APERTURE_SQLITE_EVENT_LOG` | — | SQLite event log path |
| `APERTURE_EVENT_SINK_PATH` | `reports/events.jsonl` | JSONL event sink path |
| `APERTURE_OVERLAY_PATH` | `aperture/schema_optimizer/_overlay.json` | optional schema overlay override |

## File layout (post-Phase 6)

```
aperture/
  proxy/                  MCP proxy (router + cache + attribution + overlay)
  cache/                  Component A
  observability/          Component B
  schema_optimizer/       Component C
  tokenization/           shared
  benchmarks/             v1 benchmark harness
  fixtures/               schema + payload fixtures
  integration/            Path-2 SDK runner + live-check CLI
  compression/            v3 compression pipeline (frozen at salvage state)
  types.py                v1 contracts
  config.py
  cli.py

aperture-v1-dashboard/    new React dashboard (Phase 6)
api/                      legacy demo API (owned by demo branch)
dashboard/                legacy Streamlit (owned by demo branch)
frontend/                 legacy 14-page React (owned by demo branch)
scripts/                  benchmark + seed_cache_policy CLIs
tests/                    pytest suite (197+ tests)
docs/                     this directory
reports/                  generated artifacts (gitignored: events.jsonl)
```

## Other docs in this directory

- `caching.md` — Component A details
- `token_attribution.md` — Component B details
- `schema_optimization.md` — Component C details
- `security_privacy.md` — opt-in tokenizer rationale, scope safety, log retention
- `benchmark_methodology.md` — how the 4 v1 modes are measured
