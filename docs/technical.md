# Aperture Technical Stack

Roadmap: [roadmap.md](roadmap.md)  
Canonical plan: [docs/APERTURE_PROJECT_PLAN.md](docs/APERTURE_PROJECT_PLAN.md)  
Composio Python SDK reference: [docs.composio.dev/reference/sdk-reference/python](https://docs.composio.dev/reference/sdk-reference/python)

This file defines the default technical stack for Aperture so the three implementation agents can make compatible choices.

## Stack Summary

| Layer | Choice | Reason |
|---|---|---|
| Primary language | Python | Best fit for Composio SDK integration, benchmark scripting, tokenization, and fast prototyping |
| Package manager | `uv` | Fast dependency management, repeatable local setup, simple `uv add` workflow |
| Runtime target | Python 3.11+ | Modern typing and broad package compatibility |
| Project format | `pyproject.toml` package | Keeps Aperture importable by tests, benchmark agent, and future integrations |
| Data contracts | Python dataclasses first, optional Pydantic later | Keeps shared interfaces lightweight while contracts are changing |
| Token counting | `tiktoken` plus provider-specific adapters where available | Deterministic local token estimates for OpenAI-style tokenizers, adapter path for other providers |
| Composio integration | `composio` Python SDK | Official SDK exposes tool fetch/execute APIs and modifier hooks |
| Cache backend | In-memory for tests, Redis for integration/demo | Tests stay simple; Redis proves realistic repeated-read caching |
| Dashboard | Next.js, React, TypeScript, App Router, Tailwind CSS | Interactive MVP dashboard for benchmark/demo analysis |
| Dashboard API | FastAPI and Uvicorn | Local JSON API over exported run traces and reports |
| Reports | Markdown, JSONL, JSON summaries, and interactive dashboard | Reports remain source artifacts; dashboard is the primary review surface |
| Tests | `pytest` | Standard Python test runner with simple fixture support |
| Type checks | `mypy` or `pyright` after contracts stabilize | Useful once shared contracts stop changing daily |
| Formatting | `ruff format` and `ruff check` | Single fast tool for formatting and linting |
| Frontend tooling | Node 20+ and `pnpm` | Stable modern frontend runtime and fast package installation |

## Repository Shape

Target package layout:

```text
aperture/
  pyproject.toml
  README.md
  .env.example

  aperture/
    contracts.py
    config.py

    tokenization/
    observability/
    routing/
    schema_optimizer/
    compression/
    cache/

  benchmarks/
  demo_agent/
  dashboard_api/
  dashboard/
  fixtures/
  reports/
  tests/
  docs/
```

The current repo already has planning docs. The first implementation step should create this package structure without moving the planning docs unless the team agrees.

## Core Dependencies

### Required MVP Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "composio",
  "tiktoken",
  "pyyaml",
  "redis",
  "orjson",
  "rich",
  "typer",
  "fastapi",
  "uvicorn",
]
```

Recommended dev dependencies:

```toml
[dependency-groups]
dev = [
  "pytest",
  "pytest-cov",
  "ruff",
  "mypy",
]
```

### Why These

- `composio`: official Python SDK for fetching and executing Composio tools.
- `tiktoken`: deterministic token counting for OpenAI-compatible tokenizers.
- `pyyaml`: profiles and cache policies should be editable as YAML.
- `redis`: realistic execution cache and result-compaction cache backend.
- `orjson`: fast stable JSON serialization for hashing/token counting.
- `rich`: readable local CLI reports and debugging output.
- `typer`: small CLI surface for running benchmarks and reports.
- `fastapi`: local API for serving run traces, events, and summary data to the dashboard.
- `uvicorn`: local ASGI server for the dashboard API.
- `pytest`: test runner for all three workstreams.
- `ruff`: formatting and linting with minimal tool sprawl.

### Frontend Dependencies

The interactive dashboard is part of MVP.

Use a dedicated Next.js app:

```text
dashboard/
  package.json
  next.config.ts
  app/
  components/
  lib/
```

Recommended frontend dependencies:

```json
{
  "dependencies": {
    "@tanstack/react-table": "latest",
    "lucide-react": "latest",
    "next": "latest",
    "react": "latest",
    "react-dom": "latest",
    "recharts": "latest"
  },
  "devDependencies": {
    "tailwindcss": "latest",
    "typescript": "latest"
  }
}
```

Use `shadcn/ui` for dashboard components. Treat the generated UI components as dashboard-owned code under Person 1's lane.

## Composio Integration

Aperture should integrate around Composio tool loading and execution.

Current Composio docs show:

- install via `pip install composio` or `uv add composio`
- instantiate `Composio`
- fetch tools with `composio.tools.get(...)`
- execute tools with `composio.tools.execute(...)`
- use hooks/decorators such as `before_execute`, `after_execute`, and `schema_modifier`

Expected integration points:

| Aperture feature | Composio touchpoint |
|---|---|
| Schema token measurement | Around tool fetch/schema loading |
| Schema compaction | Schema modifier or pre-model tool-context builder |
| Execution cache | Before tool execution |
| Result compression | After tool execution |
| Run trace | Around schema loading, tool execution, compression, and cache events |

The MVP can start with an adapter wrapper instead of deep SDK hooks:

```python
class ComposioAdapter:
    def get_tools(self, user_id: str, toolkits: list[str]) -> list[dict]:
        ...

    def execute_tool(self, tool_slug: str, arguments: dict, user_id: str) -> object:
        ...
```

This lets the benchmark agent use fake tools before live Composio credentials are available.

## Shared Contracts

Shared contracts live in:

```text
aperture/contracts.py
```

They are owned by Person 2 but consumed by all workstreams.

Use dataclasses for MVP:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApertureRunConfig:
    run_id: str
    tenant_id: str | None
    user_id: str | None
    connected_account_id: str | None
    model: str | None
    effort_mode: str
    cache_bypass: bool = False


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    tokenizer: str
    approximate: bool


@dataclass(frozen=True)
class ToolCall:
    toolkit_slug: str | None
    tool_slug: str
    arguments: dict[str, Any]
    user_id: str | None = None
```

Add Pydantic later only if runtime validation becomes necessary for API boundaries or persisted records.

## Serialization and Hashing

Stable serialization is required for:

- token counting
- cache keys
- raw result hashes
- schema variant hashes
- reproducible benchmark reports

Use one canonical serializer:

```python
def stable_json_dumps(payload: object) -> str:
    ...
```

Requirements:

- sorted object keys
- compact separators
- no payload mutation
- deterministic treatment of dataclasses
- safe fallback for unknown objects
- UTF-8 output

Use `orjson` for speed if it can meet the deterministic requirements. Otherwise use standard `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)` first and optimize later.

## Tokenization

Tokenization modules:

```text
aperture/tokenization/
  serializers.py
  tokenizer_registry.py
  token_counter.py
```

MVP behavior:

- use model-specific tokenizer when known
- use provider-family tokenizer when known
- fall back to a default tokenizer when unknown
- mark fallback counts as approximate
- keep measured counts separate from estimated savings

Initial tokenizer registry:

```text
gpt-4.1 / gpt-4o family -> tiktoken OpenAI-compatible tokenizer
unknown -> default approximate tokenizer
```

Do not block MVP on perfect Anthropic/Gemini counting. Add provider-specific adapters after the benchmark harness works.

## Configuration

Use YAML for human-edited policies and profiles:

```text
aperture/routing/effort_modes.yaml
aperture/compression/profiles.yaml
aperture/cache/policy.yaml
```

Use environment variables only for secrets and runtime endpoints:

```text
COMPOSIO_API_KEY=
APERTURE_CACHE_URL=redis://localhost:6379/0
APERTURE_ENV=local
```

Use `.env.example` for documented local setup. Do not commit real credentials.

## Caching Stack

Two cache backends:

1. `InMemoryCache`
2. `RedisCache`

In-memory is used for unit tests and local dry runs. Redis is used for integration testing and demos.

Cache classes:

| Cache class | Owner | Backend |
|---|---|---|
| Schema variant cache | Person 2 | file/in-memory first, Redis optional |
| Result compaction cache | Person 3 | in-memory and Redis |
| Execution cache | Person 3 | in-memory and Redis |

Execution cache keys must include:

- tenant ID
- scope
- toolkit slug
- tool slug
- normalized arguments hash
- connected account ID where applicable
- auth scope hash where applicable
- schema version
- API version
- freshness policy

Writes, auth flows, failed responses, and partial responses are not cached by default.

## Storage

MVP storage should stay simple.

| Data | MVP storage | Later option |
|---|---|---|
| Unit fixtures | JSON files / JSONL | No change needed |
| Benchmark tasks | JSONL | SQLite if queries get painful |
| Run traces | JSONL | SQLite/Postgres |
| Reports | Markdown plus JSON summaries | Hosted dashboard |
| Dashboard API data | Local JSON/JSONL files read by FastAPI | SQLite/Postgres |
| Raw output references | local files under ignored `.aperture/raw/` | object store |
| Cache entries | in-memory / Redis | Redis or managed cache |

Avoid building a database-backed service before the core behavior is proven.

## Interactive Dashboard

The MVP includes an interactive, local-first dashboard.

### Frontend

Use:

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- `shadcn/ui`
- `lucide-react`
- `recharts`
- `@tanstack/react-table`

Person 1 owns the dashboard app because it is part of the benchmark/demo presentation lane.

Dashboard views:

- run comparison view for raw, low, medium, high, cached, and full modes
- token waterfall for prompt, schemas, arguments, results, retries, and output
- tool trace table with exposed tools, called tools, cache status, result compression, and effort mode
- savings cards for schema savings, result savings, cache savings, and API calls avoided
- failure case view for extra tool calls, fallback expansion, raw fallback, and task quality regressions

### Local Dashboard API

Use FastAPI for a local JSON API that reads exported traces and summaries from local files.

```text
dashboard_api/
  main.py
  models.py
  readers.py
```

Required endpoints:

```text
GET /health
GET /runs
GET /runs/{run_id}
GET /runs/{run_id}/events
GET /reports/summary
```

Endpoint responsibilities:

- `GET /health`: return API status and configured data directory.
- `GET /runs`: list benchmark/demo runs with mode, timestamp, task name, total tokens, savings, cache hits, and task success.
- `GET /runs/{run_id}`: return the full run summary and trace metadata.
- `GET /runs/{run_id}/events`: return schema, cache, compression, and tool events for one run.
- `GET /reports/summary`: return aggregate savings across available runs.

The API must not compute core metrics from raw payloads. Person 2 and Person 3 provide exported summaries/events; Person 1 serves and visualizes them.

## CLI Surface

Use `typer` for local commands:

```text
aperture count-fixture fixtures/schema/github_tools.json
aperture compact-schema fixtures/schema/github_tools.json --effort medium
aperture compress-result fixtures/results/github_issues.json --tool GITHUB_LIST_ISSUES
aperture run-benchmark benchmarks/tasks/github_tasks.jsonl --mode raw
aperture run-benchmark benchmarks/tasks/github_tasks.jsonl --mode aperture_medium
aperture report runs/latest.jsonl
```

Person 1 owns benchmark commands. Person 2 owns schema/token/report commands. Person 3 owns compression/cache commands.

## Testing Strategy

### Unit Tests

Each workstream owns unit tests for its modules.

Required:

- deterministic token counts
- stable serialization
- effort mode schema preservation
- compression field preservation
- cache safety rules
- cache key determinism
- raw reference creation

### Integration Tests

Integration tests should use fake Composio adapters first.

Required:

- raw run vs medium effort run
- repeated safe read cache hit
- write action bypasses cache
- result compression produces lower token count
- low/medium schema expansion event can be recorded
- dashboard API can serve fixture-backed run summaries and events

### Benchmark Tests

Benchmark tests should not assert exact token counts across every environment. They should assert:

- counts exist
- savings are non-negative unless explicitly testing regressions
- task quality metrics are recorded
- failure cases are preserved in reports

### Dashboard Tests

Person 1 owns frontend and dashboard API tests.

Required:

- dashboard loads with fixture API data
- run comparison view renders raw, low, medium, high, cached, and full modes
- token waterfall handles missing buckets without crashing
- tool trace table supports filtering by tool, cache status, and effort mode
- `GET /runs` returns fixture-backed runs
- `GET /runs/{run_id}` returns a stable JSON shape
- missing run IDs return 404
- malformed JSONL files produce a clear API error instead of a frontend crash

## Reporting Stack

MVP reports:

- `reports/raw_token_baseline.md`
- `reports/schema_exposure_report.md`
- `reports/compression_report.md`
- `reports/cache_report.md`
- `reports/benchmark_report.md`
- `reports/demo_run_report.md`

Machine-readable outputs:

- JSONL run traces
- JSON summary per benchmark run
- dashboard-ready aggregate summary JSON

Interactive dashboard:

- Person 1 serves exported traces and summaries through FastAPI.
- Person 1 builds a Next.js dashboard over that local API.
- Person 2 owns dashboard-ready observability exports and run trace schema.
- Person 3 owns compression/cache event payloads and summaries.
- Markdown and JSONL remain source-of-truth artifacts; the dashboard is the primary review surface.

## Workstream Ownership by Module

| Module | Owner |
|---|---|
| `aperture/contracts.py` | Person 2, reviewed by all |
| `aperture/tokenization/` | Person 2 |
| `aperture/observability/` | Person 2 |
| `aperture/routing/` | Person 2 |
| `aperture/schema_optimizer/` | Person 2 |
| `aperture/compression/` | Person 3 |
| `aperture/cache/` | Person 3 |
| `benchmarks/` | Person 1 |
| `demo_agent/` | Person 1 |
| `dashboard/` | Person 1 |
| `dashboard_api/` | Person 1 |
| `fixtures/benchmark/` | Person 1 |
| `fixtures/schema/` | Person 2 |
| `fixtures/results/` | Person 3 |
| `reports/benchmark_report.md` | Person 1 |
| `reports/schema_exposure_report.md` | Person 2 |
| `reports/compression_report.md` | Person 3 |
| `reports/cache_report.md` | Person 3 |

## MVP Implementation Order

1. Create package skeleton and `pyproject.toml`.
2. Define shared contracts.
3. Implement stable serialization and token counting.
4. Build fixture-backed benchmark runner.
5. Implement schema effort modes.
6. Implement safe result compression.
7. Add run trace export.
8. Implement exact-match cache key builder.
9. Add in-memory execution cache.
10. Wire benchmark modes: raw, low, medium, high, cached.
11. Add fixture-backed dashboard API.
12. Add Next.js dashboard with run comparison, token waterfall, tool trace, savings cards, and failure cases.
13. Add Redis backend.
14. Generate final Markdown, JSON, and dashboard reports.

## Deferred Until After MVP

- Hosted dashboard deployment.
- Database service.
- Automatic production deployment.
- Learned compression policies.
- Semantic cache for execution outputs.
- Cross-user cache sharing for private data.
- Full LLM provider bill attribution.
- Perfect provider-specific tokenizer coverage.

## Open Technical Decisions

These do not block the first implementation pass:

- Whether to keep contracts as dataclasses or upgrade persisted records to Pydantic.
- Whether final run traces should move from JSONL to SQLite.
- Whether schema compaction should use Composio `schema_modifier` hooks directly or remain in an adapter layer for the prototype.
- Which exact model/provider will be used for benchmark judging.
