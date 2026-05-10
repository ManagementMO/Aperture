# Benchmark Methodology

How Aperture measures itself. Lives in `aperture/benchmarks/`.

## Modes

| Mode | What's enabled |
|---|---|
| `raw` | None. Fixtures returned untouched, tokens counted, no cache, no compression, no schema overlay. The baseline. |
| `aperture_compressed` | Output compression only (frozen v3 pipeline). Cache disabled (`compression_bypass=False, cache_bypass=True`). |
| `aperture_cached` | Compression + cache. Each task runs twice; second run hits cache and short-circuits the upstream. |
| `aperture_full` | Compression + cache + schema overlay savings folded in via `schema_savings_by_tool()`. |
| `shadow` | Compression runs and emits events but the raw payload is returned (used to measure "what would compression have done"). |

The four primary modes (`raw`, `aperture_compressed`, `aperture_cached`,
`aperture_full`) are what handoff §13.4 cell 2 specifies. `shadow` is a
salvage-branch addition kept for ablation.

## Tasks

JSONL files at `aperture/benchmarks/tasks/{github,gmail,slack,notion,mixed}_tasks.jsonl`.

Schema per line:
```json
{
  "task_id": "github_001",
  "category": "github",
  "user_prompt": "Find auth-related issues and summarize blockers.",
  "tool_slug": "GITHUB_LIST_REPOSITORY_ISSUES",
  "params": {...},
  "fixture": "github_issues.json",
  "expected_fields": ["number","title","state","labels","body"],
  "critical_fields": ["title","state","labels"],
  "evaluation_type": "field_presence"
}
```

Current count: **20 tasks** across 5 categories (github 5, gmail 4, slack 4,
notion 4, mixed 3). v1 acceptance §13.4 cell 1 requires ≥20.

## Evaluation

`aperture/benchmarks/evaluators.py:field_presence_score(payload, expected_fields)`
recursively walks the compressed payload looking for each expected field
name as a key. Scores by fraction present.

`has_missing_critical_info(payload, critical_fields)` is binary — any
missing critical field flips it. `task_success = (score >= 0.8) and not missing_critical`.

The `llm_judge_export` evaluator is a stub that returns
`{"judge_required": False}` — Phase 5's `aperture/schema_optimizer/llm_judge.py`
is the active LLM judge. Benchmarks themselves remain LLM-free.

## Metrics

`aperture/benchmarks/metrics.py:BenchmarkMetrics` per task:
- `raw_tokens`, `compressed_tokens`, `tokens_saved`, `compression_ratio`
- `cache_hits`, `api_calls_avoided`, `schema_tokens_saved`
- `task_success`, `success_score`, `missing_critical_info`
- `extra_tool_calls`, `raw_fallback_used`, `latency_ms`

Aggregated per mode via `aggregate_run_metrics(run)`. Output sorted in
the report by descending savings.

## Runner

```python
import asyncio
from pathlib import Path
from aperture.benchmarks.runner import run_benchmark
from aperture.benchmarks.task_set import load_tasks
from aperture.benchmarks.report import write_benchmark_outputs

async def main():
    tasks = load_tasks(Path("aperture/benchmarks/tasks"))
    runs = []
    for mode in ("raw", "aperture_compressed", "aperture_cached", "aperture_full"):
        runs.append(await run_benchmark(tasks, mode))
    write_benchmark_outputs(runs, Path("reports"))

asyncio.run(main())
```

`run_benchmark()` is async because the cache interceptor is async. It
returns a `BenchmarkRunResult` with one `BenchmarkMetrics` entry per task.
`write_benchmark_outputs()` produces `reports/{benchmark_metrics.json,
benchmark_report.md, raw_token_baseline.md, compression_report.md,
cache_report.md}`.

## What "success" means

A v1 acceptance run (handoff §13.4) requires:
- `aperture_full` ≥50% aggregate token savings vs `raw`
- Quality probes pass on every workflow

The current 20-task run on the synthetic fixtures shows ~14% compression
savings because the fixture payloads are tiny (~228 raw tokens average per
task, vs ~5-10kB for real Composio responses). The mode matrix is
correctly exercised; absolute numbers will scale linearly with payload
size when Phase 1's real-token baseline lands.

To produce real numbers:
1. Phase 1 mandates 100 real Composio sessions (`scripts/v1_week_1_baseline.py`
   placeholder — needs `COMPOSIO_API_KEY` + connected accounts).
2. Replace fixture payloads with the captured real responses.
3. Re-run the benchmark suite.
4. Reports will then show realistic savings per the demo branch's prior
   75.5% number (which was on different fixtures from the same repo's
   `data/` directory).

## Determinism

`tests/benchmarks/test_runner.py:test_runner_is_deterministic` runs the
benchmark twice and asserts equality. Stable JSON serialization in
`aperture/tokenization/serializers.py` is what makes this work — every
sort_keys, every dict→tuple, every byte path is deterministic.
