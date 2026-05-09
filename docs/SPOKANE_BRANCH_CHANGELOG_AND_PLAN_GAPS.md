# Spokane Branch Changelog And Plan Gaps

Date: 2026-05-09
Branch: `demo`

This document records the important changes made during the final Spokane
validation pass and maps the current branch against the original Aperture plan:

- `docs/APERTURE_PROJECT_PLAN.md`
- `docs/APERTURE_CODING_AGENT_EXECUTION_PLAN.md`

It focuses on important fixes and differences, not every small formatting or
dependency-lock detail.

## Important Changes Made

### 1. Real Composio SDK API-Key Path

Files:

- `aperture/agent/composio_agent.py`
- `dashboard/app.py`
- `scripts/honest_comparison.py`
- `scripts/record_demo.sh`
- `.env.example`
- `pyproject.toml`
- `uv.lock`

What was wrong or missing:

- Some live scripts/dashboard paths relied on implicit SDK state or hard-coded
  user/account values.
- The branch did not consistently use the SDK API-key path requested for real
  Composio testing.
- Live demos had credential assumptions embedded in code.

What changed:

- `Composio(api_key=...)` is now used where live SDK construction is required.
- The agent path keeps compatibility with SDK versions that read
  `COMPOSIO_API_KEY` from the environment and do not accept `api_key` directly.
- Connected-account IDs are read from environment variables.
- `.env.example` documents preferred connected-account variables and
  backward-compatible aliases.
- Hard-coded live credentials were removed from scripts.

Why it matters:

- The system now works with real Composio credentials without depending on the
  CLI login path or checked-in secrets.
- Private connected-account results can be scoped correctly in cache keys.

### 2. Connected-Account Cache Scoping

Files:

- `aperture/cache/policy.py`
- `aperture/cache/key_builder.py`
- `aperture/cache/interceptor.py`
- `aperture/agent/composio_agent.py`
- `dashboard/app.py`
- `api/main.py`
- `tests/test_cache.py`

What was wrong or missing:

- Cache keys could fall back to a global-ish scope when private IDs were not
  present.
- Public/private cache boundaries were not strict enough for connected-account
  tools.
- Cache key hashes were based on visible key fragments instead of a safe hash.

What changed:

- Cache policy now has explicit scope selection.
- Public scope is allowed for public GitHub repo metadata only when no
  connected-account context is present.
- Account scope requires a connected-account ID.
- Private reads without the required scope execute but do not cache.
- Cache events log a hash of the cache key, not a raw key suffix.
- Additional real Composio GitHub read slugs were added to the cacheable
  allowlist.

Why it matters:

- This prevents private account data from being reused across users/accounts.
- It keeps caching useful for safe public reads while remaining conservative
  for connected tools.

### 3. Cache Hit Compression Correctness

Files:

- `aperture/cache/interceptor.py`
- `aperture/integration.py`
- `aperture/benchmarks/harness.py`
- `aperture/demo/agent_simulator.py`
- `dashboard/app.py`
- `tests/test_cache.py`

What was wrong or missing:

- Cache hits could bypass the normal compression path.
- Some cache hit paths reported zero raw/compressed tokens or treated cached
  results as already model-facing.

What changed:

- The cache stores and returns raw successful responses.
- `ApertureRunner` compresses cached raw responses the same way it compresses
  fresh responses.
- Benchmark and dashboard paths now recompress cached raw results.
- A regression test verifies that cached hits still produce compressed tokens
  and token savings.

Why it matters:

- A cache hit should avoid external API execution, not bypass output
  optimization.
- Token reports now reflect what the model actually receives.

### 4. Cache Event Accounting Bug

Files:

- `aperture/observability/events.py`
- `tests/test_cache.py`

What was wrong or missing:

- Token/result events carry `cache_status` for attribution.
- Cache lookup events also carry `cache_status`.
- The trace summary counted all events with `cache_status`, so cache hits and
  avoided API calls could be overcounted.

What changed:

- Events now have explicit `event_kind` markers.
- Token events are marked `token`.
- Cache lookup events are marked `cache_lookup`.
- Trace summaries count only real cache lookup events.

Why it matters:

- Cache reports now reflect actual cache behavior, not attribution metadata.

### 5. Deterministic Fixture Benchmarks

Files:

- `aperture/demo/mock_data.py`
- `aperture/benchmarks/harness.py`
- `aperture/benchmarks/vanilla_vs_aperture.py`

What was wrong or missing:

- Fixture payloads used random dates, counts, Slack IDs, comments, and
  reactions.
- Re-running benchmarks could produce different raw payloads and token counts.
- Some benchmark quality checks were more field-existence-based than
  semantic.

What changed:

- Random fixture generation was replaced with stable hash-derived values from
  a fixed base date.
- The benchmark harness uses deterministic semantic probes where available.
- `GITHUB_LIST_REPOSITORY_ISSUES` is included in the GitHub issues quality
  probe mapping.

Why it matters:

- The benchmark is now repeatable.
- Quality claims are more meaningful because they check concrete task signals.

### 6. Live Redis/Upstash Behavior

Files:

- `aperture/cache/store.py`
- Live validation scripts run during review

What was wrong or missing:

- The local test suite covered in-memory behavior well, but live Redis needed
  explicit validation with the provided environment.

What changed:

- The final review validated set/get/delete against the configured Upstash
  Redis backend.
- The live Aperture cache smoke proved Redis-backed misses and hits.

Why it matters:

- The cache is not just a local-memory demo path.

### 7. Frontend Dependency And Build Hardening

Files:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.ts`
- `frontend/src/index.css`
- `frontend/eslint.config.js`
- `frontend/src/components/CommandPalette.tsx`
- `frontend/src/pages/SchemaCompaction.tsx`

What was wrong or missing:

- The frontend dependency stack needed security/build cleanup.
- CSS import order and lint issues caused noisy or failing gates.

What changed:

- Vite and React plugin versions were upgraded.
- `esbuild` was added and configured for CSS minification.
- Frontend lint/build issues were fixed.
- The lockfile was updated.

Why it matters:

- `npm run lint`, `npm run build`, and `npm audit --audit-level=moderate` now
  pass.

### 8. Remote Branch RTK And Spend Additions Preserved

Files:

- `aperture/compression/rtk_inspired.py`
- `aperture/benchmarks/vs_rtk.py`
- `aperture/agent/composio_agent.py`
- `api/main.py`
- `frontend/src/pages/VsRtk.tsx`
- `frontend/src/pages/SpendStudio.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/Demo.tsx`
- `aperture/agent/tool_cache.py`

What was added by the remote branch:

- RTK-inspired ultra-summary lines.
- Three-tier degradation markers: `full`, `degraded`, `passthrough`.
- A head-to-head RTK benchmark harness.
- A dashboard page for `/vs-rtk`.
- API endpoint `/api/bench/rtk`.
- Spend Studio dashboard page.
- Whole-question result cache for repeated asks.
- Prompt-cache prewarm endpoint.
- Tool-cache API endpoints for spend/call-savings visualization.

What changed during final integration:

- The local Composio SDK/cache changes were merged with the remote RTK
  and Spend Studio additions.
- The merge conflict in `aperture/agent/composio_agent.py` was resolved by
  retaining RTK imports, result-cache/prewarm behavior, Spend Studio telemetry,
  and the safer `ApertureRunConfig`/`CachedExecutor` live execution path.
- The newly added `SpendStudio.tsx` lint/build errors were fixed after the
  latest remote update.

Why it matters:

- The branch keeps the coworker additions while preserving the safety and live
  SDK work from the validation pass.
- The authoritative live tool execution cache remains the scoped
  `CachedExecutor` path. `aperture.agent.tool_cache` remains present for
  read-only/write helpers, approximate cost helpers, and dashboard endpoints,
  but its process-local lookup/store path is not the private-data cache used by
  the final live agent execution path.

## What Is Implemented From The Original Plan

### Token Attribution

Implemented:

- Stable payload serialization.
- Token counting with tokenizer fallback.
- Per-run token events.
- Argument and result attribution.
- Compression savings in traces and benchmark output.
- Context budget tracking.

Different from plan:

- The dataclass names are not exact plan names. The code uses `TokenEvent`,
  `ApertureRunConfig`, and related contracts instead of every named contract in
  the execution plan.
- Report generation is mostly via dashboard/API/CLI, not dedicated Markdown
  report files in `reports/`.

### Output Compression

Implemented:

- Tool-aware normalization.
- Field pruning.
- Flattening/list compaction.
- Long-text and stopword pruning.
- Task-aware required-field protection.
- TOON rendering for tabular outputs.
- Optional ask-aware/model-assisted field promotion.
- Lazy hydration utilities.
- RTK-inspired ultra-summary and degradation tier marker.

Different from plan:

- Compression profiles are Python registries/modules, not YAML profiles.
- Raw reference storage exists but is not wired into every main compression
  path as a visible envelope by default.
- The visible model-facing envelope is not exactly the execution-plan format;
  the system returns compressed payloads plus metadata/trace objects.

### Safe Repeated-Call Caching

Implemented:

- Deny-by-default cache policy.
- Explicit read allowlist.
- Write/auth denylist.
- Exact-match keying.
- Public/account/user/tenant scope support.
- Required private scope enforcement.
- In-memory and Redis/Upstash storage.
- Cache bypass support.
- Cache events and safe key hashes.
- Cache hits avoid real API calls.
- Failed responses are not cached.

Different from plan:

- There is no async `maybe_execute_with_cache(...)`; the implementation is
  synchronous through `CachedExecutor.execute(...)`.
- Policy is code, not a YAML policy file.
- Cache keys do not yet include schema version, API version, or freshness
  policy dimensions, even though the event contract has those fields.

### Schema Compaction And Optimization

Implemented:

- Effort-mode schema selection.
- Optional-field/schema compaction behavior.
- Type-grouped schema compaction.
- Auto-profile generation from payload shape.
- Dashboard/API surfaces for schema compaction.

Different from plan:

- The full schema description optimization pipeline is only partial.
- There is not yet a complete description extractor, candidate rewrite
  generator, structural validator, accepted/rejected report, and rollback
  workflow matching the execution plan.

### Effort Routing And Context Budgeting

Implemented:

- `low`, `medium`, `high`, `auto`, and `off` effort behavior.
- Intelligent effort selection.
- Context budget manager.
- Quality gate for required signals.
- Semantic route selector.

Different from plan:

- The effort modes are functional but not wired into every originally planned
  schema-cache/result-cache variant.

### Benchmarking

Implemented:

- Deterministic vanilla vs Aperture benchmark.
- Mode matrix benchmark.
- Semantic quality probes.
- Fixture scenarios for repo research, bug triage, onboarding, and large
  dataset summarization.
- Dashboard benchmark surfaces.
- RTK comparison endpoint/page, gracefully disabled when `rtk` is absent.

Different from plan:

- Benchmark mode names differ from the execution plan. Current modes are
  `off`, `low`, `medium`, `high`, and `auto`, plus the vanilla-vs-Aperture
  script.
- There is no generated `reports/benchmark_report.md` artifact yet.
- JSONL task loading in the exact planned shape is not the main benchmark
  interface on this branch.

### Docs And Dashboard

Implemented:

- README update.
- `.env.example`.
- API backend.
- React/Vite dashboard.
- Streamlit dashboard.
- Spend Studio and RTK comparison dashboard surfaces.
- Docs for project plan, execution plan, technical stack, roadmap, and this
  final review.

Different from plan:

- The docs are not yet organized into the exact full architecture/security/
  methodology report set requested by the original execution plan.
- Workbench boundary is documented in the plan docs, but not implemented as a
  production storage service.

## What Still Needs To Be Done For Strict Plan Parity

These are not claims that the branch is broken. They are the remaining items
if the target is literal completion of the original plans.

1. Add exact public contracts or compatibility aliases for the planned data
   classes:
   - `ExecutionContext`
   - `TokenAttributionEvent`
   - `CompressionContext`
   - `CachePolicy`
   - `SchemaOptimizationResult`
   - planned benchmark result types

2. Move or mirror policy/profile definitions into planned files:
   - YAML compression profiles.
   - YAML cache policy.
   - Explicit bypass parser module.
   - Explicit parameter normalizer module.

3. Add the async integration function:
   - `maybe_execute_with_cache(...)`
   - Or document that the sync runner is the supported interface.

4. Complete raw reference envelope wiring:
   - Store raw output during main compression.
   - Return opaque `raw_reference_id`.
   - Add visible retrieval hints where the model-facing payload needs them.

5. Complete schema description optimization:
   - Fetch schemas.
   - Extract description fields.
   - Rank token-heavy descriptions.
   - Generate rewrite candidates.
   - Validate unchanged slugs, parameter names, types, enums, and required
     fields.
   - Emit accepted/rejected reports.

6. Add generated report artifacts:
   - `reports/token_report.md`
   - `reports/compression_report.md`
   - `reports/cache_report.md`
   - `reports/schema_optimization_report.md`
   - `reports/benchmark_report.md`

7. Add optional live pytest markers:
   - Composio live smoke tests skipped unless credentials are present.
   - Redis live smoke tests skipped unless credentials are present.

8. Clean full Ruff:
   - Line length.
   - Import ordering.
   - Unused imports.
   - Minor style findings.

9. Run a full live Claude agent loop:
   - Requires `ANTHROPIC_API_KEY`.
   - Current validation covered real Composio SDK execution, but not the
     complete Claude tool-use loop.

10. Decide whether RTK comparison is part of Aperture core:
    - The remote branch additions are useful.
    - The endpoint gracefully handles missing `rtk`.
    - A CI story would need either installing `rtk` or keeping it as an
      optional local comparison.

11. Align the Spend Studio tool-cache stats with the scoped execution cache:
    - The UI/API surface exists and is useful.
    - The final agent path now uses `CachedExecutor` for safer account-scoped
      caching.
    - A follow-up should either make `aperture.agent.tool_cache` delegate to
      `CachedExecutor` or remove the separate process-local stats surface.

## Final Position

This branch is a strong, working Aperture implementation for the main thesis:
measure tool-context cost, compress model-facing tool output, safely cache
repeated reads, route effort, and prove savings with deterministic benchmarks.

It is accurate to the spirit and most important behavior of the original plan.
It is not yet identical to every file/module/report/interface in the written
execution plan. The remaining work is mostly contract parity, report artifacts,
schema optimization completion, and production polish.
