# Repository Guidelines

## Project Structure & Module Organization

`aperture/` is the primary Python package. Key areas include `proxy/` for the MCP proxy, `cache/`, `compression/`, `tokenization/`, `observability/`, `schema_optimizer/`, `benchmarks/`, and `integration/`. Tests live at the repository root in `tests/` and mirror package areas, for example `tests/cache/test_policy.py`.

Fixtures and sample tool data are in `aperture/fixtures/`. Benchmark task sets are in `aperture/benchmarks/tasks/`. Reports are in `reports/`, and documentation is in `docs/`. The active React/Vite dashboard is separate in `aperture-v1-dashboard/`; treat `frontend/` as legacy or demo UI unless explicitly targeted.

## Build, Test, and Development Commands

Run these commands from the Git root:

- `uv sync --extra dev` installs the package with development tools.
- `make test` or `uv run pytest` runs the Python test suite.
- `uv run ruff check aperture/ tests/ scripts/` runs lint checks.
- `make benchmark` runs `aperture-benchmark --tasks aperture/benchmarks/tasks --out reports`.
- `python -m aperture.proxy` starts the MCP proxy when required environment variables are set.
- `uvicorn aperture.observability.api_endpoints:create_api_app --factory --host 0.0.0.0 --port 8002` runs the observability API.
- `cd aperture-v1-dashboard && npm install` installs dashboard dependencies.
- `cd aperture-v1-dashboard && npm run dev` starts the dashboard on Vite.
- `cd aperture-v1-dashboard && npm run build` type-checks and builds the dashboard.

## Coding Style & Naming Conventions

Use Python 3.10+ with 4-space indentation and explicit, descriptive module names. Keep tests named `test_*.py` and test functions named `test_*`. Prefer typed dataclasses or existing project models for structured data instead of ad hoc dictionaries when a local type already exists. Dashboard code uses TypeScript React components with `PascalCase` page and component files such as `SchemaOverlay.tsx`.

## Testing Guidelines

Default tests must not require live external services. Live tests are marked with `live_composio`, `live_anthropic`, `live_redis`, or legacy `live`; gate them with environment configuration. Add focused tests next to the relevant package area, and update fixtures when behavior depends on schema or tool-output shape.

## Commit & Pull Request Guidelines

Git history uses concise, scoped summaries such as `Phase 6: benchmarks at v1 scale + new aperture-v1-dashboard` and `Live verification fixes - proxy URL, OpenAI envelope, full-scale policy.yaml`. Follow that pattern: start with the phase or scope, then state the user-visible change.

Pull requests should include a short description, test results, linked issue or task when available, and screenshots for dashboard changes. Do not commit real secrets; copy `.env.example` to `.env` locally and keep credentials out of diffs.
