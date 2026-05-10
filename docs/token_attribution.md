# Token Attribution (Component B)

The attribution layer answers the question every developer using Composio
asks: "which meta tool calls are costing my LLM the most?" Aperture
tokenizes every meta-tool response server-side, threads the count through
a canonical event shape, persists to SQLite, and serves aggregations via
v3.1-shape FastAPI endpoints.

## Event shape

`aperture/types.py:TokenAttributionEvent` (handoff §17.1).

Canonical `event_type` values:
- `meta_tool_response` — the proxy tokenized one upstream meta-tool response
- `argument` — the agent sent arguments to a meta tool (input cost)
- `result` — a non-meta tool result (Path-2 SDK runner)
- `compressed_result` — output compression applied (frozen v3 path)
- `cache_hit_savings` — a hit avoided an upstream call; `tokens_saved` is
  what the LLM would have read otherwise
- `schema_savings` — schema overlay swapped a verbose description for a
  compact one (`tokens_saved` is the rewrite reduction)

Canonical `payload_kind` values:
- `schema` — tools/list, GET_TOOL_SCHEMAS, SEARCH_TOOLS portion
- `execution_result` — MULTI_EXECUTE outputs
- `plan` — SEARCH_TOOLS execution-plan portion
- `compressed_result` — post-compression payload

Each event carries `session_id`, `session_turn`, `meta_tool_slug`,
`tool_slug` (when applicable), `model`, `tokenizer`,
`tokenizer_is_approximate`, byte counts, token counts, ratio, and
`aperture_version` (read from `aperture.__version__`).

## Tokenization

`aperture/tokenization/token_counter.py:count_tokens_for_payload(payload, model)`.

Resolution order for Anthropic-family models:
1. `APERTURE_USE_ANTHROPIC_TOKENIZER=true` AND `ANTHROPIC_API_KEY` set →
   `client.messages.count_tokens()` (real, `approximate=False`).
2. Else → cl100k_base via tiktoken (`approximate=True`, ~5-10% error).
3. Else → chars/4 fallback (`approximate=True`, last resort).

For OpenAI-family models, the registry maps to the right tiktoken encoding
(o200k_base, cl100k_base) and falls back to cl100k.

The Anthropic real-tokenizer path is **opt-in for privacy** — see
`security_privacy.md`.

## Hot-path tokenizer caching

`aperture/proxy/tokenize.py:TokenizerService` wraps the per-payload count
with a per-process LRU keyed by `(model, sha256(serialized)[:32])`. TTL
24h; default cap 10,000 entries.

Two methods:
- `await svc.count(payload, model)` — blocks on cache miss to do the count.
- `svc.schedule_count(payload, model, on_complete=...)` — fire-and-forget
  for the proxy hot path. Returns immediately; runs in background.

The proxy uses `schedule_count` so the LLM response is forwarded BEFORE
tokenization completes. `on_complete` emits the `TokenAttributionEvent`.

## Storage

Three sinks, all best-effort and independent — failure on one never
blocks the others:

1. **In-memory list** — `aperture/observability/event_emitter.py`.
   Reset per test via `clear_in_memory_events()`. Used for assertions.
2. **JSONL** — `APERTURE_EVENT_SINK_PATH` env var. One line per event.
   Useful for grep/jq debugging.
3. **SQLite** — `APERTURE_SQLITE_EVENT_LOG` env var (or
   `event_log_sqlite.set_default_log()`). Two tables (`token_events`,
   `cache_events`) with indexes on timestamp, meta_tool_slug, user_id,
   session_id, toolkit_slug. **The v3.1 API endpoints query this.**

## v3.1 API endpoints

Mounted by `aperture/observability/api_endpoints.py:create_api_app()`,
typically at `http://localhost:8002/api/v3.1/...`.

### `POST /api/v3.1/project/usage/input_tokens_contributed`

Body:
```json
{
  "group_by": "meta_tool_slug",
  "order_by": "total_quantity",
  "order_direction": "desc",
  "dt_gt": "2026-04-28T00:00:00Z",
  "dt_lt": "2026-05-05T23:59:59Z",
  "user_id": "...",
  "session_id": "...",
  "page": 1,
  "page_size": 100
}
```

Allowed `group_by` values: `meta_tool_slug | toolkit_slug | session_turn | user_id | tool_slug | model | date`.

Response:
```json
{
  "data": [
    {
      "group_value": "COMPOSIO_SEARCH_TOOLS",
      "total_input_tokens_contributed": 482301,
      "total_calls": 1284,
      "average_per_call": 375.6
    }
  ],
  "page": 1,
  "page_size": 100,
  "total_groups": 1,
  "queried_at": "2026-05-09T16:30:00Z"
}
```

### `POST /api/v3.1/project/usage/cache_tokens_saved`

Body uses `group_by: tool_slug | toolkit_slug | user_id | cache_status | date`.
Response carries `hits / misses / api_calls_avoided / tokens_saved` per group.

### `GET /api/v3.1/health`

Returns version + SQLite log status + event counts. Used by the dashboard
to surface "is anything connected" at a glance.

When no SQLite log is configured, all aggregation endpoints return
`{"data": [], "warning": "no_sqlite_event_log", ...}` rather than 500.

## Reports

`aperture/observability/reports.py` produces five Markdown reports
(handoff §13.2 cell 9):

- `top_expensive_tools_report`
- `compression_savings_report`
- `cache_savings_report`
- `session_cost_report`
- `schema_savings_report`

Each takes the relevant event/result list and returns a Markdown string;
`reports/` files are written by the benchmark runner and the schema
optimizer pipeline.

## Verifying

```bash
uv run pytest tests/observability/ tests/proxy/test_attribution.py
uv run python -c "
import asyncio
from aperture.benchmarks.runner import run_benchmark
from aperture.benchmarks.task_set import load_tasks
from aperture.benchmarks.report import write_benchmark_outputs
from pathlib import Path
async def main():
    tasks = load_tasks(Path('aperture/benchmarks/tasks'))
    runs = [await run_benchmark(tasks, m) for m in
            ('raw', 'aperture_compressed', 'aperture_cached', 'aperture_full')]
    write_benchmark_outputs(runs, Path('reports'))
asyncio.run(main())
"
```

After the benchmark run, `reports/benchmark_report.md` plus 5 other
Markdown reports + `benchmark_metrics.json` are populated.
