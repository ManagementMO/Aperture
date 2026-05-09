# Spokane Final Engineering Review

Date: 2026-05-09
Branch: `demo`

This document is the final review of the Spokane branch after the cache,
Composio, benchmark, dashboard, dependency, and validation fixes were applied
and after `origin/demo` was merged in. It is intentionally direct: what is
real, what was tested, what changed materially, and what still has caveats.

## Bottom Line

The core Aperture implementation on this branch is real and working. It is not
just static demo output or hand-written benchmark claims.

The following are implemented and validated:

- Real Composio SDK API-key construction.
- Real Composio connected-account discovery.
- Real direct `tools.execute(...)` execution.
- Real `Composio.create(...).execute(...)` session execution.
- Scoped exact-match caching with Redis/Upstash.
- Safe cache policy for public versus connected-account reads.
- No caching for writes/auth-sensitive operations.
- Compression on both fresh results and cached raw results.
- Deterministic fixture benchmark results.
- Semantic quality probes, not just token-count comparisons.
- FastAPI dashboard backend smoke endpoints.
- React/Vite frontend lint/build.
- Live Hugging Face classifier smoke.
- Secret scan for the specific provided secrets.
- Spend Studio and prompt-cache/result-cache dashboard additions from the
  updated remote branch.

The strongest evidence is the live smoke test: the branch executed real
Composio GitHub tools, stored and fetched from Redis, produced one miss and one
hit for public GitHub repo metadata, and produced one miss and one hit for an
account-scoped GitHub issues query. In both cache tests, the second call avoided
the external API and still produced compressed model-facing output.

## Review Findings

No blocker-level correctness issue remains in the reviewed critical path.

The one correctness issue found during review was fixed:

- `EventEmitter.cache_events()` previously identified cache events by the
  presence of `cache_status`, which also exists on token/result attribution
  events. This overcounted cache hits and avoided calls in summaries.
- The fix adds explicit `event_kind` markers: `token` for token events and
  `cache_lookup` for cache events.
- A regression test now verifies that one miss plus one hit reports exactly one
  cache hit and one avoided API call.

The important residual risks are non-blocking but real:

- Full Ruff is not clean. Remaining findings are style/maintenance issues such
  as line length, import ordering, unused imports, f-string placeholders, and
  whitespace. Runtime-critical undefined-name lint passes.
- The full Claude agent loop was not run because no Anthropic API key was
  available. The Composio side of that loop was tested directly.
- The RTK comparison endpoint is implemented and API-safe, but this machine
  does not have the `rtk` binary installed, so the endpoint returned
  `rtk_available=false` instead of running the head-to-head fixtures.
- Some implementation names and artifacts differ from the original plan. See
  `docs/SPOKANE_BRANCH_CHANGELOG_AND_PLAN_GAPS.md`.

## Critical Path Review

### Live Composio Path

Files:

- `aperture/agent/composio_agent.py`
- `dashboard/app.py`
- `scripts/honest_comparison.py`
- `scripts/record_demo.sh`
- `.env.example`

The branch now uses the SDK API-key path instead of relying on hidden CLI state
or hard-coded credentials. The agent helper builds `Composio(api_key=...)` when
the environment provides `COMPOSIO_API_KEY`, while retaining a fallback for SDK
versions that only read the key from the process environment.

Connected account IDs are resolved per toolkit and passed into
`ApertureRunConfig`. That matters because private tool results must not fall
back to global cache keys.

The live test verified:

- Active connected accounts were discoverable for GitHub, Gmail, Google Sheets,
  Linear, Notion, Supabase, and YouTube.
- The provided GitHub, Gmail, and YouTube connected-account IDs matched active
  accounts.
- Real schemas loaded for `GITHUB_GET_A_REPOSITORY`,
  `GITHUB_LIST_REPOSITORY_ISSUES`, and `GITHUB_GET_THE_AUTHENTICATED_USER`.
- Real `GITHUB_GET_A_REPOSITORY` returned successfully through direct
  `tools.execute(...)`.
- Real `GITHUB_GET_A_REPOSITORY` returned successfully through
  `Composio.create(...).execute(...)`.

### Cache Safety

Files:

- `aperture/cache/policy.py`
- `aperture/cache/key_builder.py`
- `aperture/cache/interceptor.py`
- `aperture/cache/store.py`
- `tests/test_cache.py`

The cache is now conservative enough for live connected tools:

- Cacheability is deny-by-default.
- Write/auth tools stay blocked.
- Public GitHub repo metadata may use public scope only when no connected
  account context is present.
- Most reads require connected-account scope.
- Missing private scope executes the tool but does not cache it.
- Failed/error responses are not cached.
- Cache logs contain a hash of the key, not the raw key.
- Cache hits return raw cached data, then the runner compresses it normally.

This fixed an earlier architectural bug where cache hits could bypass
compression and show zero compressed tokens.

### Compression And Benchmark Quality

Files:

- `aperture/compression/engine.py`
- `aperture/compression/field_policy.py`
- `aperture/compression/field_profiles.py`
- `aperture/compression/task_profiles.py`
- `aperture/compression/toon.py`
- `aperture/benchmarks/harness.py`
- `aperture/benchmarks/vanilla_vs_aperture.py`
- `aperture/demo/mock_data.py`

Compression is structure-aware, not a blind truncation layer. It performs
normalization, field pruning, task-aware protection, TOON rendering for
tabular payloads, optional small-model field rescue, and deterministic quality
checks.

The benchmark harness now uses semantic quality probes where available instead
of only checking whether generated "critical field" strings exist somewhere in
the compressed output. Fixture data is deterministic: prior random timestamps,
counts, Slack IDs, and issue stats were replaced with stable hash-derived
values from a fixed base date.

The deterministic benchmark proof is strong:

- `scripts/vanilla_vs_aperture.py`: 487,381 raw tokens to 119,629 Aperture
  tokens, 367,752 tokens saved, 75.5 percent savings, quality PASS.
- `scripts/benchmark.py --all`: every scenario and every mode reported 100
  percent quality; compressed modes saved about 70 to 73 percent depending on
  scenario and mode.

### Observability

Files:

- `aperture/observability/events.py`
- `aperture/observability/trace.py`

The event model now distinguishes token events from cache lookup events. This
is important because token events also carry `cache_status` for attribution,
but they are not cache lookup records. Run summaries now count real cache hits,
misses, and avoided API calls only.

### Dashboard And Frontend

Files:

- `api/main.py`
- `dashboard/app.py`
- `frontend/src/pages/*`
- `frontend/package.json`
- `frontend/vite.config.ts`

The FastAPI backend exposes real measured endpoints for data, compression,
cache stats, demo runs, and the RTK comparison endpoint. The React frontend
builds successfully against Vite 8 and TypeScript, and the known Vite security
issue was addressed by upgrading the package set and forcing CSS minification
through `esbuild`.

The remote branch additions were retained:

- RTK-inspired ultra-summary line.
- Three-tier `full/degraded/passthrough` marker.
- `/api/bench/rtk`.
- `VsRtk` dashboard page.
- Spend Studio dashboard page.
- Whole-question result cache for repeated agent asks.
- Prompt-cache prewarm endpoint.
- Tool-cache API surfaces for the spend dashboard.

One integration note: the live agent execution path now uses the safer
`CachedExecutor` path for exact-match scoped execution caching. The remote
`aperture.agent.tool_cache` module remains for read-only/write classification,
cost-estimate helpers, and dashboard cache endpoints, but its process-local
lookup/store path is not the authoritative private-data execution cache.

## Validation Commands Run

Backend and package:

```bash
uv run pytest
uv run python -m compileall -q aperture api scripts
uv run ruff check --select F821
uv run ruff check --statistics
```

Results:

- `uv run pytest`: 180 passed.
- Compileall: passed.
- Undefined-name Ruff check: passed.
- Full Ruff: failed with 283 style/maintenance findings.

Benchmarks:

```bash
uv run python scripts/vanilla_vs_aperture.py
uv run python scripts/benchmark.py --all
```

Results:

- Vanilla vs Aperture: 75.5 percent savings, quality PASS.
- Full benchmark matrix: 100 percent quality across all scenarios and modes.

Frontend:

```bash
cd frontend
npm run lint
npm run build
npm audit --audit-level=moderate
```

Results:

- ESLint: passed.
- Production build: passed.
- Audit: 0 vulnerabilities at moderate threshold.

API smoke:

```bash
uv run python - <<'PY'
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
for path in [
    "/api/health",
    "/api/datasets",
    "/api/cache/stats",
    "/api/bench/rtk",
    "/api/cache/runtime",
    "/api/cache/tools",
]:
    response = client.get(path)
    assert response.status_code == 200
PY
```

Results:

- All six endpoints returned 200.
- `/api/bench/rtk` returned gracefully with `rtk_available=false` because the
  binary is not installed on this machine.

Live integration smoke:

- Real Composio connected-account list succeeded.
- Real Composio schema fetch succeeded.
- Real direct GitHub repo execution succeeded.
- Real session-style GitHub repo execution succeeded.
- Real Redis/Upstash set/get/delete succeeded.
- Public GitHub cache path: first call miss, second call hit, one API call
  avoided.
- Account-scoped GitHub issues cache path: first call miss, second call hit,
  one API call avoided.
- Remote Spend Studio additions were integrated and the new cache/prewarm API
  endpoints smoke-test successfully.
- Gmail search policy is cacheable only with account scope.
- Gmail send policy is not cacheable.

Secret hygiene:

- A scan for the exact secret values provided during testing found no tracked
  matches in the workspace, excluding ignored `.env`, `.context`, virtualenv,
  and dependency directories.

## Engineering Assessment

This branch is engineered well for a demo/prototype that is meant to prove the
Aperture thesis. The highest-value parts are implemented with actual runtime
behavior and tests:

- The cache path is conservative and validated with live data.
- The compression path is deterministic and quality-gated.
- The benchmarks measure actual token counts and preserve concrete signals.
- The SDK integration uses the real API-key path.
- The dashboard displays measured data instead of hard-coded numbers.

It should not be described as a fully production-hardened service yet. The next
engineering bar is plan-contract parity, report generation, schema optimization
completion, full Ruff cleanup, and a live Claude-agent test with an Anthropic
key.
