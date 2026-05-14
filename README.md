# Aperture v1

Token-efficiency layer for Composio-powered agents. Aperture sits between
the LLM and Composio's Tool Router as an MCP proxy, intercepts the
session meta-tool surface, and ships three compounding optimizations:

1. **Safe execution cache** (Component A) — deny-by-default per-tool YAML
   policy, exact-match keys with policy-version coupling (`aperture:v1:p1:`),
   partial-batch caching for `MULTI_EXECUTE_TOOL`, public/account/user/project/session
   scope isolation. **1,700+ tools classified** from live Composio across 15
   toolkits.
2. **Token attribution observability** (Component B) — every meta-tool
   response tokenized in the proxy's hot path (background, never blocks
   the response), events flow to SQLite, queryable through
   `/api/v3.1/project/usage/...` FastAPI endpoints. Backed by a real
   Anthropic `count_tokens` path (opt-in via `APERTURE_USE_ANTHROPIC_TOKENIZER=true`).
3. **Schema description optimizer** (Component C) — offline pipeline that
   rewrites verbose tool descriptions, validates with a Haiku judge +
   Sonnet spot-check, produces a JSON overlay the proxy applies to outbound
   schema responses. The committed overlay is `structural_only` quality
   today (4 tools, 9 fields, 64 tokens saved); upgrade to `llm_judged`
   when Anthropic credits permit a real judge run.

Aperture does **not** replace Composio sessions, Tool Router, auth,
workbench, usage metering, logs, or SDK modifiers. It adds a focused
token-economics layer around that traffic: per-meta-tool token attribution,
safe read caching, partial-batch cache hits, and a quality-graded schema
overlay.

## Architecture at a glance

```
┌──────────┐   MCP/HTTP   ┌──────────────────┐  Streamable HTTP   ┌──────────┐
│ LLM      │ ───────────► │ Aperture proxy   │ ─────────────────► │ Composio │
│ client   │              │  :8001 /mcp      │                    │ MCP URL  │
└──────────┘              │  ─────────────── │ ◄───── tools ───── └──────────┘
                          │  cache lookup    │
                          │  schema overlay  │
                          │  tokenize bg     │
                          │  attribution → ──┼──► SQLite event log
                          └──────────────────┘
                          ┌──────────────────┐  fastapi   ┌─────────────────────┐
                          │ aperture-v1-     │ ◄────────  │ /api/v3.1/...       │
                          │ dashboard :5180  │            │  :8002              │
                          └──────────────────┘            └─────────────────────┘
```

The LLM client points its MCP URL at the Aperture proxy. The proxy
forwards `x-api-key` and other auth headers verbatim, substitutes
`{session_id}` in the upstream URL template, and never persists or logs
secrets. Tokenization, cache, schema overlay, and attribution all happen
between the inbound and outbound halves of the round-trip.

## Branch state

| Branch | Status | Notes |
|---|---|---|
| `v1-fixes` | **active** | implementation fixes plus docs polish; use `git log --oneline` for the current head |
| `v1-realignment` | parent | base for `v1-fixes`; do not merge `v1-fixes` here without review |
| `demo` | parallel | the salvaged demo; never share files with v1 work |
| `main` | upstream | merge target if/when ready |

The implementation-fix sequence on `v1-fixes`:

1. `13ff81d1` — wired the proxy through `dispatch`, `set_default_store`,
   `RedisCacheStore`, schema overlay, and attribution. Forwarded auth
   headers, substituted `{session_id}` template.
2. `cd0b1562` — closed 11 residual gaps (CachedResult unwrap after dispatch,
   isError sentinel that prevents poisoning the cache, defense-in-depth in
   the proxy's `SchemaOverlay` loader, schema-shape `_to_anthropic_tool`
   helper, silent-pass guard in `run_judge`).
3. `e88b9122` — rewriter improvements (0% → 26.4% compression on top-15
   fixtures), prompt fixtures expanded to 50+ per toolkit, hand-wave
   sweep across proxy docstrings.
4. `28f66883` — read-only ranker filter at the optimizer entry, quality-graded
   overlay (`llm_judged` / `structural_only`), populated artifact.

Later docs commits (`8d617e87` and newer) explain the verified state without
changing the runtime contract.

## Run

### 0. Install

```bash
uv sync --extra dev
cp .env.example .env   # then fill in COMPOSIO_API_KEY, ANTHROPIC_API_KEY (opt)
```

### 1. v3.1 attribution API (port 8002)

```bash
APERTURE_SQLITE_EVENT_LOG=./events.db \
uvicorn aperture.observability.api_endpoints:create_api_app \
  --factory --host 0.0.0.0 --port 8002
```

Endpoints:
- `GET /api/v3.1/health`
- `POST /api/v3.1/project/usage/input_tokens_contributed`
- `POST /api/v3.1/project/usage/cache_tokens_saved`
- `GET /api/v3.1/overlay` (serves `_overlay.json` for the dashboard)

### 2. MCP proxy (port 8001)

```bash
APERTURE_COMPOSIO_MCP_URL_TEMPLATE="https://backend.composio.dev/tool_router/{session_id}/mcp" \
APERTURE_SQLITE_EVENT_LOG=./events.db \
APERTURE_REDIS_URL=redis://localhost:6379  \  # optional; falls back to in-memory
python -m aperture.proxy
```

Point your LLM client's MCP URL at `http://127.0.0.1:8001/mcp`.

### 3. Dashboard (port 5180)

```bash
cd aperture-v1-dashboard
npm install
npm run dev
```

Three pages, all reading real data:
- **Overview** — health + top meta tools by tokens + top cache savings
- **Reports** — paginated v3.1 aggregations with group-by/date filters
- **Schema Overlay** — accepted rewrites with side-by-side diff + a
  `quality_level` warning banner when the overlay is `structural_only`

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `COMPOSIO_API_KEY` | — | live integration (`aperture-live-check`, schema fetcher) |
| `COMPOSIO_USER_ID` | `default` | live session creation + proxy context fallback |
| `COMPOSIO_CONNECTED_ACCOUNT_ID` | — | proxy/cache fallback for account-scoped calls |
| `COMPOSIO_PROJECT_ID` | — | attribution event field |
| `ANTHROPIC_API_KEY` | — | LLM judge live mode + opt-in tokenizer |
| `APERTURE_USE_ANTHROPIC_TOKENIZER` | `false` | route `count_tokens_for_payload` through Anthropic's `count_tokens` API |
| `APERTURE_MODE` | `balanced` | legacy Path-2 runner mode |
| `APERTURE_RAW_STORE_PATH` | `.aperture/raw_store` | legacy raw payload store path |
| `APERTURE_PROXY_HOST` | `127.0.0.1` | proxy bind |
| `APERTURE_PROXY_PORT` | `8001` | proxy bind |
| `APERTURE_COMPOSIO_MCP_URL_TEMPLATE` | `https://backend.composio.dev/tool_router/{session_id}/mcp` | upstream URL template |
| `APERTURE_PROXY_LOG_LEVEL` | `INFO` | proxy log verbosity |
| `APERTURE_PROXY_PARTIAL_BATCH` | `true` | enables per-inner-tool cache fan-out for `MULTI_EXECUTE_TOOL` |
| `APERTURE_PROXY_UPSTREAM_TIMEOUT` | `30.0` | upstream Composio MCP timeout in seconds |
| `APERTURE_PROXY_FALLBACK_TOKENIZER` | `auto` | proxy tokenizer fallback mode |
| `APERTURE_REDIS_URL` | — | Redis backing for cache; falls back to in-memory store |
| `APERTURE_SQLITE_EVENT_LOG` | — | SQLite event log path; events also still flow to JSONL |
| `APERTURE_EVENT_SINK_PATH` | `reports/events.jsonl` | JSONL event sink path |
| `APERTURE_OVERLAY_PATH` | `aperture/schema_optimizer/_overlay.json` | optional overlay override |
| `APERTURE_ENABLE_LIVE_TESTS` | `false` | opt-in gate for live Composio tests |

## Test

```bash
uv run pytest                          # full pytest suite
uv run ruff check aperture/ tests/ scripts/    # 0 findings
uv run python scripts/secret_scan.py $(git ls-files)   # 0 findings
```

CI runs no live LLM and no live Composio. Live integration tests are
gated on env-var markers (`live_composio`, `live_anthropic`, `live_redis`).
A pre-commit hook (`.pre-commit-config.yaml` + `scripts/secret_scan.py`)
blocks committing known Composio (`ak_…`) and Anthropic (`sk-ant-api…`)
credential formats.

## Console scripts

| Script | Purpose |
|---|---|
| `aperture-benchmark` | run the 4-mode benchmark suite (`raw`, `aperture_compressed`, `aperture_cached`, `aperture_full`) over `aperture/benchmarks/tasks/` |
| `aperture-live-check` | live Composio smoke (used by the salvage adapter / Path 2 fallback) |
| `aperture-schema-report` | structural-only schema optimization report |
| `aperture-connect` | live OAuth connection helper for one toolkit at a time |
| `python -m aperture.proxy` | start the MCP proxy directly |

## Schema overlay generation

The optimizer pipeline ranks fields by `tokens × frequency`, runs them
through three deterministic rewrite levels (light → medium → heavy), and
then validates each accepted candidate. Two paths:

```bash
# Production-grade (LLM-judged, paid). Anthropic credit required.
ANTHROPIC_API_KEY=... uv run python -c "
from pathlib import Path
from aperture.schema_optimizer.budget import BudgetTracker
from aperture.schema_optimizer.reports import (
    optimize_schemas_with_llm_judge, write_overlay,
)
results = optimize_schemas_with_llm_judge(
    live=True, tracker=BudgetTracker(cap_usd=2.0),
    max_candidates=15, spot_check_fraction=0.10,
)
write_overlay(Path('aperture/schema_optimizer/_overlay.json'),
              results, quality_level='llm_judged')
"

# Preview-grade (structural-only, free, ships a populated overlay today).
uv run python -c "
from pathlib import Path
from aperture.schema_optimizer.reports import optimize_schemas, write_overlay
write_overlay(Path('aperture/schema_optimizer/_overlay.json'),
              optimize_schemas(),
              quality_level='structural_only')
"
```

The overlay file contains a top-level `quality_level` field plus a
`warning` string for `structural_only` runs. The dashboard surfaces both.
The proxy's `SchemaOverlay` loader applies a **read-only positive list**
at startup — write/auth/unknown tools never apply, even if hand-edited
into the overlay.

## Defense-in-depth (the safety story)

The schema overlay has four independent layers gating what gets rewritten:

1. **Rewriter** never produces a candidate that strips safety/auth keywords
   (`send`, `delete`, `auth`, `oauth`, `token`, `permission`).
2. **`_overlay_safe`** in `reports.write_overlay` requires
   `policy.operation_type == "read"` AND `validation_cases_run >= 50`
   (default `llm_judged`) or `>= 1` (`structural_only`).
3. **`SchemaOverlay.reload`** in the proxy applies the same read-only
   positive list at load time. Write/auth/unknown tools listed in the
   overlay are dropped with a logged warning; `dropped_unsafe` is exposed
   for ops visibility.
4. **LLM judge silent-pass guard** — when both `original` and `candidate`
   Anthropic calls return empty (e.g. credit exhaustion, rate limit), the
   judge records `anthropic_call_failed` rather than letting `None == None`
   silently agree (a bug that was actually live in this codebase before
   `cd0b1562`).

The cache layer has parallel guarantees:

- **`isError` upstream responses** are tagged with
  `_aperture_upstream_error` so `_success_response` refuses to cache
  them; the marker is stripped before the LLM client sees the response.
- **Cache key includes a policy-version segment** (`aperture:v1:p1:`) so
  changing `policy.yaml`'s scope rules invalidates old entries.
- **Cache hits return `CachedResult(data, cached_age_seconds, original_cost_tokens)`**
  — explicit dataclass with original token cost preserved at write time,
  not recomputed on every read.

These were verified live: a 522-call Anthropic run against real Haiku +
Sonnet validated each layer. Two candidates the judge accepted were both
write tools that the safety filter correctly blocked.

## Project layout

```
aperture/
  proxy/                 MCP proxy (server, upstream, router, intercept handlers,
                         cache bridge, schema overlay, tokenizer, attribution)
  cache/                 Component A: policy YAML loader, key builder, normalizer,
                         interceptor, in-memory + Redis stores, search-tools split
  observability/         Component B: event schema/emitter, aggregations, reports,
                         SQLite log, /api/v3.1/... FastAPI endpoints
  schema_optimizer/      Component C: fetch/extract/tokenize/rank/rewrite pipeline,
                         budget tracker, LLM judge with replay mode, prompts/, overlay writer
  tokenization/          deterministic serializer, tiktoken + Anthropic count_tokens path
  benchmarks/            evaluators, metrics, runner, task set, 4-mode report
  integration/           userspace SDK runner (Path 2 fallback) — proxy does NOT use this
  fixtures/              real schema + payload fixtures (used in tests, not in CI proxy)
  cli.py                 console-script entry points
  config.py              ApertureConfig.from_env()
  types.py               TokenAttributionEvent, CacheEvent, ExecutionContext, etc.
aperture-v1-dashboard/   Vite + React 19 dashboard (3 pages)
docs/                    architecture, caching, token_attribution,
                         schema_optimization, security_privacy, benchmark_methodology
scripts/                 seed_cache_policy.py, secret_scan.py
tests/                   pytest suite
```

## Reports + benchmarks

The benchmark runner produces six v1-required Markdown reports:

```bash
uv run python -c "
import asyncio
from pathlib import Path
from aperture.benchmarks.runner import run_benchmark
from aperture.benchmarks.task_set import load_tasks
from aperture.benchmarks.report import write_benchmark_outputs
async def main():
    tasks = load_tasks(Path('aperture/benchmarks/tasks'))
    runs = [await run_benchmark(tasks, m) for m in
            ('raw', 'aperture_compressed', 'aperture_cached', 'aperture_full')]
    write_benchmark_outputs(runs, Path('reports'))
asyncio.run(main())
"
```

Modes: `raw` (no Aperture), `aperture_compressed` (output compression
only), `aperture_cached` (cache only), `aperture_full` (everything).
Reports are emitted to `reports/`.

## Documentation

- `docs/architecture.md` — system overview, data flow, file layout
- `docs/caching.md` — Component A details (policy gates, key format, scope)
- `docs/token_attribution.md` — Component B details (events, aggregations, API)
- `docs/schema_optimization.md` — Component C pipeline, quality levels, run recipes
- `docs/security_privacy.md` — opt-in tokenizer rationale, scope safety, secret scanning
- `docs/benchmark_methodology.md` — how the 4 v1 modes are measured
- `docs/V1_CODEX_REVIEW.md` — independent audit (basis for `13ff81d1` fixes)
- `docs/V1_FINAL_VERIFICATION.md` — earlier verification report (corrections at top)
- `docs/HANDOFF_V1_REALIGNMENT.md` — original gap analysis (on `demo` branch)

## Out of scope

The v1 plan reserved space for two more components but ships nothing for
them per user direction:

- **Component D** — Session State Compressor
- **Component E** — Plan Quality Scorer

## License

See `LICENSE`.
