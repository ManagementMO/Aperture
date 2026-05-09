# Aperture Roadmap

Canonical plan: [docs/APERTURE_PROJECT_PLAN.md](docs/APERTURE_PROJECT_PLAN.md)  
Technical stack: [technical.md](technical.md)

This roadmap splits Aperture across three people running three separate agents. The main goal is to avoid overlapping work while still producing one coherent system.

## Product Goal

Aperture is a token-efficiency layer for Composio-powered agents.

It should:

- show how much tool context costs
- expose fewer schemas when safe
- compact verbose tool outputs
- cache safe repeated reads
- support low, medium, and high effort modes
- prove savings with a benchmark/demo agent

## Workstream Split

| Owner | Workstream | Primary responsibility | Should avoid |
|---|---|---|---|
| Person 1 | Benchmark, demo agent, and dashboard | Build the agent and interactive dashboard that exercise Aperture and prove savings | Core Aperture internals and metric computation |
| Person 2 | Context, schema, and observability | Token counting, run traces, effort modes, schema compaction, schema optimization, dashboard-ready observability exports | Result compression, execution cache internals, and frontend UI |
| Person 3 | Result compression and safe caching | Tool output compression, raw references, result compaction cache, safe execution cache, compression/cache event payloads | Schema selection, benchmark agent logic, and dashboard routes |

## Shared Rules

- Each person owns a clear directory set.
- Do not edit another person's owned directories unless explicitly coordinated.
- Shared contracts should be small, stable, and reviewed before downstream work depends on them.
- Benchmark code should call Aperture through public interfaces, not by importing private internals.
- Dashboard code should read exported run data through the local API, not recompute core metrics.
- Unit fixtures can live with each workstream. Cross-workstream benchmark fixtures belong to Person 1.
- Safety decisions must be deterministic first. Small models can suggest ranking, rewriting, summaries, or expansion, but cannot be the sole authority for skipping writes, reusing private data, deciding freshness, or changing tool arguments.

## Shared Contracts

These should be agreed first, then treated as integration contracts.

### Run Config

```python
class ApertureRunConfig:
    run_id: str
    tenant_id: str | None
    user_id: str | None
    connected_account_id: str | None
    model: str | None
    effort_mode: str  # low | medium | high | off | shadow
    cache_bypass: bool
```

### Tool Context Event

```python
class ToolContextEvent:
    run_id: str
    toolkit_slug: str
    tool_slug: str
    schema_version: str | None
    schema_tokens_full: int
    schema_tokens_exposed: int
    schema_tokens_saved: int
    was_exposed: bool
    was_called: bool
    effort_mode: str
```

### Compression Result

```python
class CompressionResult:
    compressed_payload: object
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    raw_reference_id: str | None
    strategy: str
    omitted_fields: list[str]
    warnings: list[str]
```

### Cache Event

```python
class CacheEvent:
    run_id: str
    toolkit_slug: str | None
    tool_slug: str
    cache_status: str  # hit | miss | bypass | not_cacheable | error
    cache_scope: str
    cache_key_hash: str | None
    schema_version: str | None
    api_version: str | None
    freshness_policy: str | None
    api_call_avoided: bool
    tokens_saved_estimate: int
    reason: str | None
```

## Person 1: Benchmark, Demo Agent, and Dashboard

### Mission

Build the agent, benchmark harness, local dashboard API, and interactive dashboard that prove whether Aperture actually reduces tool-context cost without hurting task quality.

### Owned Areas

- `benchmarks/`
- `demo_agent/`
- `dashboard/`
- `dashboard_api/`
- `fixtures/benchmark/`
- `reports/benchmark_report.md`
- `reports/demo_run_report.md`
- `docs/demo_script.md`
- `docs/benchmark_methodology.md`

### Feature Set

- Raw Composio-style baseline run mode.
- Aperture low, medium, and high effort run modes.
- Repeated-request mode to test cache behavior.
- Benchmark task set for GitHub, Gmail, Slack, Notion, and mixed workflows.
- Metrics collector for schema tokens, result tokens, cache hits, API calls avoided, task success, extra tool calls, fallback rate, and latency.
- Demo script showing normal flow vs medium effort vs repeated request with cache.
- FastAPI local JSON API over exported run traces and benchmark summaries.
- Next.js dashboard with run comparison, token waterfall, tool trace table, savings cards, and failure cases.
- Final report with measured savings and failure cases.

Dashboard API endpoints:

- `GET /health`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `GET /reports/summary`

### Milestones

1. Create benchmark task schema and runner skeleton.
2. Add fixture-backed fake Composio tools so the benchmark can run before real integration is finished.
3. Add raw baseline metrics.
4. Add adapter layer that can call Aperture public interfaces once Person 2 and Person 3 expose them.
5. Add low/medium/high comparison view.
6. Add repeated-call cache scenario.
7. Add fixture-backed FastAPI dashboard API.
8. Add Next.js dashboard against the local API.
9. Produce final benchmark, demo, and dashboard report.

### Interfaces Consumed

- `select_tool_context(...)` from Person 2.
- `record_run_event(...)` or exported run trace from Person 2.
- `compress_tool_output(...)` from Person 3.
- `execute_with_cache(...)` from Person 3.

### Definition of Done

- Same benchmark tasks can run in raw, low, medium, high, compressed, cached, and full modes.
- Reports show token savings and task quality side by side.
- Demo can show at least one repeated safe read served from cache.
- Dashboard can load fixture-backed runs before core Aperture is complete.
- Dashboard can compare raw, low, medium, high, cached, and full modes.
- Failure cases are documented instead of hidden.

## Person 2: Context, Schema, and Observability

### Mission

Build the front half of Aperture: measurement, effort modes, tool-context budgeting, schema compaction, schema optimization, and run-level observability.

### Owned Areas

- `aperture/tokenization/`
- `aperture/observability/`
- `aperture/routing/`
- `aperture/schema_optimizer/`
- `aperture/contracts.py`
- `fixtures/schema/`
- `reports/raw_token_baseline.md`
- `reports/schema_exposure_report.md`
- `reports/schema_optimization_report.md`
- `docs/token_attribution.md`
- `docs/effort_modes.md`
- `docs/tool_context_budgeting.md`
- `docs/schema_compaction.md`
- `docs/schema_optimization.md`
- `docs/dashboard.md`

### Feature Set

- Stable JSON serialization.
- Tokenizer registry and token counter.
- Run trace data model.
- Tool context events.
- Token waterfall report.
- Tools exposed vs tools called report.
- Dashboard-ready run summary exports consumed by Person 1's API.
- Low, medium, and high effort mode configs.
- Request normalizer.
- Tool relevance selector.
- Schema compactor for toolkit/tool/field/example/enum reduction.
- Schema variant cache or schema variant export owned inside this lane.
- Progressive schema expansion policy.
- Description rewrite candidate generator and validator.

### Milestones

1. Define `aperture/contracts.py` with shared dataclasses and type contracts.
2. Implement stable serializer and token counter.
3. Implement run trace and event emitter.
4. Build schema fixture loader and baseline schema token report.
5. Implement effort mode config.
6. Implement schema compactor and tool selector.
7. Add fallback expansion event logging.
8. Add schema optimization rewrite pipeline.
9. Export dashboard-ready run summaries for Person 1's dashboard API.

### Interfaces Exposed

```python
count_tokens(payload: object, model: str | None) -> TokenCount
select_tool_context(request, tools, config: ApertureRunConfig) -> ToolContextResult
record_tool_context_event(event: ToolContextEvent) -> None
export_run_trace(run_id: str) -> dict
optimize_schema_descriptions(schema_set, config) -> SchemaOptimizationReport
```

### Definition of Done

- Token counts are deterministic for the same payload and tokenizer.
- Low, medium, and high schema modes work on representative fixtures.
- Required fields are never removed.
- Schema compaction savings are measured.
- Run traces expose schema, argument, result, retry, cache, and output token buckets.
- Person 1 can consume exported traces without importing private modules.
- Person 1 can display observability metrics without recomputing them in the dashboard.

## Person 3: Result Compression and Safe Caching

### Mission

Build the back half of Aperture: compacting tool outputs, preserving raw access, caching compacted results, and safely avoiding repeated read executions.

### Owned Areas

- `aperture/compression/`
- `aperture/cache/`
- `fixtures/results/`
- `fixtures/cache/`
- `reports/compression_report.md`
- `reports/cache_report.md`
- `docs/output_compression.md`
- `docs/caching.md`
- `docs/security_privacy.md`

### Feature Set

- Compression profile loader.
- Safe and balanced result compression modes.
- Field pruning.
- Nested object flattening.
- List compaction.
- Deduplication.
- Long-text extractive summarization where allowed.
- Raw output store with opaque references.
- Result compaction cache by raw result hash, profile version, schema version, and effort mode.
- Cache policy loader.
- Parameter normalizer.
- Exact-match cache key builder.
- Redis or in-memory execution cache.
- Cache interceptor.
- Cache bypass support.
- Cache events and reports.
- Compression/cache event payloads and summaries consumed by the dashboard.

### Milestones

1. Implement compression profile format and loader.
2. Implement generic safe compression fallback.
3. Add balanced profiles for GitHub, Gmail, Slack, Notion, and one mixed/unknown fixture.
4. Add raw output references.
5. Add result compaction cache.
6. Implement cache policy format.
7. Implement exact cache key builder with tenant, account, auth scope, schema version, API version, freshness policy, tool slug, and normalized args.
8. Implement execution cache interceptor.
9. Emit cache and compression events for Person 2 exports and Person 1 dashboard views.

### Interfaces Exposed

```python
compress_tool_output(raw_payload: object, context: CompressionContext) -> CompressionResult
store_raw_output(raw_payload: object, context) -> RawReference
execute_with_cache(tool_call, executor, config: ApertureRunConfig) -> CachedExecutionResult
build_cache_key(tool_call, config: ApertureRunConfig) -> str | None
```

### Definition of Done

- Unknown tools use safe mode.
- Preserved fields are never removed.
- Compressed outputs include enough IDs, URLs, timestamps, and fields for follow-up tool calls.
- Raw references are created when significant detail is omitted.
- Writes and auth flows cannot be cached.
- Cache keys change when tenant, account, auth scope, schema version, API version, freshness policy, or normalized args change.
- Person 1 can demonstrate repeated safe reads being served from cache.
- Person 1 can display cache/compression events in the dashboard tool trace without importing cache internals.

## Integration Roadmap

### Phase 0: Contracts and Skeleton

Owners:

- Person 2 creates shared contracts.
- Person 1 creates benchmark skeleton against fake adapters.
- Person 1 creates dashboard and dashboard API skeletons against fixture data.
- Person 3 creates compression/cache module skeletons against shared contracts.

Gate:

- All three agents can run tests without importing private workstream internals.
- Dashboard can run against fixture data without waiting for core Aperture internals.

### Phase 1: Prove the Waste

Owners:

- Person 1 builds raw benchmark runs.
- Person 1 serves raw benchmark summaries through the dashboard API.
- Person 2 measures schema/result/argument/retry tokens.
- Person 3 supplies representative raw result fixtures if needed.

Gate:

- Report shows schemas exposed, tools called, raw result tokens, and estimated unused schema context.
- Dashboard shows the same baseline values from exported summaries.

### Phase 2: First Savings

Owners:

- Person 2 ships low/medium/high schema compaction.
- Person 3 ships safe/balanced result compression.
- Person 1 compares raw vs low/medium/high on fixed tasks.

Gate:

- Schema and result token savings are visible without breaking benchmark task completion.

### Phase 3: Safe Reuse

Owners:

- Person 3 ships exact-match execution cache and result compaction cache.
- Person 2 records cache events in run traces.
- Person 1 adds repeated-request benchmark scenarios and cache views.

Gate:

- Demo shows cache hits, API calls avoided, and token savings with no writes cached.
- Dashboard tool trace shows cache status and compression status per tool call.

### Phase 4: Smart Routing and Validation

Owners:

- Person 2 adds tool relevance ranking, schema expansion, and description optimization.
- Person 3 hardens compression/cache safety and policies.
- Person 1 adds failure-case review and extra tool-call metrics.

Gate:

- Low/medium modes can expand when needed, and all safety constraints are visible in reports.

### Phase 5: Final Demo and Report

Owners:

- Person 1 owns final benchmark report and demo.
- Person 1 owns final interactive dashboard.
- Person 2 owns observability/schema sections.
- Person 3 owns compression/cache/security sections.

Gate:

- Final claims are measured, not guessed.

## Non-Overlap Boundaries

### Person 1 Must Not Own

- Tokenizer implementation.
- Schema compaction internals.
- Compression profile logic.
- Cache key safety logic.
- Core metric computation.

### Person 2 Must Not Own

- Benchmark task runner internals.
- Frontend UI.
- Dashboard API routes.
- Output compression algorithms.
- Execution cache interceptor.
- Raw output storage.

### Person 3 Must Not Own

- Benchmark scoring logic.
- Dashboard routes.
- Frontend UI.
- Effort-mode schema selection.
- Tool relevance ranking.
- Schema description rewrite validation.

## Integration Risks

| Risk | Mitigation |
|---|---|
| Shared contracts churn | Freeze `aperture/contracts.py` early and version breaking changes |
| Benchmark waits on internals | Person 1 starts with fake adapters and fixtures |
| Schema cache and execution cache overlap | Person 2 owns schema variants; Person 3 owns execution/result caches |
| Compression removes needed fields | Person 3 preserves IDs, URLs, timestamps, and raw references; Person 1 measures fallback/tool-call regressions |
| Low effort becomes unsafe | Person 2 enforces deterministic expansion rules; Person 3 prevents unsafe cache reuse |
| Reports disagree | Person 2 owns run trace aggregation; Person 1 owns benchmark presentation using exported traces |
| Dashboard duplicates metric logic | Person 1 only serves and visualizes exported summaries; Person 2 and Person 3 own metric/event computation |

## First Build Order

1. Person 2 creates shared contracts, token counter, and run trace exporter.
2. Person 1 creates fixture-backed benchmark runner, dashboard API, and dashboard shell.
3. Person 3 creates compression profile loader and safe compression fallback.
4. Person 2 adds effort modes and schema compaction.
5. Person 3 adds exact-match cache key builder and cache policy.
6. Person 1 wires raw vs Aperture comparisons.
7. Person 1 wires dashboard views to exported summaries and events.
8. All owners run integration tests and produce reports.
