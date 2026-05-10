# Aperture v1

Token-efficiency layer for Composio-powered agents. Sits between the LLM
and Composio's Tool Router as an MCP proxy, intercepts the six meta tools,
and ships three compounding optimizations:

1. **Safe execution cache** (Component A) — deny-by-default per-tool YAML
   policy, exact-match keys with policy-version coupling, partial-batch
   caching for `MULTI_EXECUTE_TOOL`, public/account/user/project/session
   scope isolation. 126 tools classified.
2. **Token attribution observability** (Component B) — every meta-tool
   response tokenized in the proxy's hot path, events flow to SQLite,
   queryable through `/api/v3.1/project/usage/...` FastAPI endpoints.
3. **Schema description optimizer** (Component C) — offline pipeline
   that rewrites verbose tool descriptions, validates with a Haiku
   judge + Sonnet spot-check, produces a JSON overlay the proxy applies
   to outbound schema responses.

Branch: `v1-realignment`. Parallel to `demo` (which stays as the salvaged
shippable demo); the two never share files.

## Run

### Backend (proxy + v3.1 API)

```bash
uv sync --extra dev

# 1. Token-attribution backend (reads SQLite event log, serves /api/v3.1/...)
APERTURE_SQLITE_EVENT_LOG=./events.db \
uvicorn aperture.observability.api_endpoints:create_api_app \
  --factory --host 0.0.0.0 --port 8002

# 2. MCP proxy (forwards to Composio's MCP URL)
APERTURE_COMPOSIO_MCP_URL_TEMPLATE="https://backend.composio.dev/v3/mcp/SERVER_ID?user_id=USER_ID" \
APERTURE_SQLITE_EVENT_LOG=./events.db \
python -m aperture.proxy
```

The LLM client points its MCP URL at `http://127.0.0.1:8001/mcp` instead
of Composio's URL.

### Dashboard

```bash
cd aperture-v1-dashboard
npm install
npm run dev   # http://localhost:5180
```

Three pages: Overview (live token + cache stats), Reports (filterable
aggregations), Schema Overlay (accepted rewrites with side-by-side diff).

## Test

```bash
uv run pytest                  # 191 passed, 1 skipped
uv run ruff check aperture/    # 0 findings
```

CI runs no live LLM and no live Composio. Live integration tests are
gated on env-var markers (`live_composio`, `live_anthropic`, `live_redis`).

## Generate v1 reports

```bash
# 6 v1-required reports
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

# Schema overlay JSON (consumed by proxy + dashboard)
uv run python -c "
from pathlib import Path
from aperture.schema_optimizer.reports import optimize_schemas, write_overlay
write_overlay(Path('aperture/schema_optimizer/_overlay.json'), optimize_schemas())
"
```

## Documentation

- `docs/architecture.md` — system overview, data flow, file layout
- `docs/caching.md` — Component A details
- `docs/token_attribution.md` — Component B details
- `docs/schema_optimization.md` — Component C details
- `docs/security_privacy.md` — opt-in tokenizer rationale, scope safety
- `docs/benchmark_methodology.md` — how the 4 v1 modes are measured
- `docs/HANDOFF_V1_REALIGNMENT.md` — the original gap analysis (on `demo`)
- `/Users/mo/.claude/plans/lets-make-a-complete-temporal-sedgewick.md` — execution plan

## Components D and E

Out of scope for v1 per user direction. The plan reserves space but
ships nothing for:
- Session State Compressor (Component D)
- Plan Quality Scorer (Component E)

## License

See `LICENSE`.
