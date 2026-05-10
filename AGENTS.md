# Repository Guidelines

## Project Structure & Module Organization

`aperture/` contains the Python package. Key modules include `proxy/` for the MCP proxy, `cache/` for safe execution caching, `compression/`, `tokenization/`, `observability/`, `schema_optimizer/`, `benchmarks/`, and `integration/`. Tests live in `tests/` and mirror those package areas, for example `tests/cache/test_policy.py` and `tests/schema_optimizer/test_validator.py`.

Fixtures and sample tool data are under `aperture/fixtures/`. Benchmark task sets are in `aperture/benchmarks/tasks/`. Generated or checked-in report artifacts are in `reports/`. Project documentation is in `docs/`. The React/Vite dashboard is separate in `aperture-v1-dashboard/`, with source files in `aperture-v1-dashboard/src/`.

## Build, Test, and Development Commands

- `uv sync --extra dev` installs the Python package with development tools.
- `make test` or `uv run pytest` runs the Python test suite.
- `uv run ruff check aperture/` runs lint checks used by the project README.
- `make benchmark` runs `aperture-benchmark --tasks aperture/benchmarks/tasks --out reports`.
- `python -m aperture.proxy` starts the MCP proxy when required environment variables are set.
- `uvicorn aperture.observability.api_endpoints:create_api_app --factory --host 0.0.0.0 --port 8002` runs the observability API.
- `cd aperture-v1-dashboard && npm install` installs dashboard dependencies.
- `cd aperture-v1-dashboard && npm run dev` starts the dashboard on Vite.
- `cd aperture-v1-dashboard && npm run build` type-checks and builds the dashboard.

## Coding Style & Naming Conventions

Use Python 3.10+ with 4-space indentation and explicit, descriptive module names. Keep tests named `test_*.py` and functions named `test_*`. Prefer typed dataclasses or existing project models for structured data rather than ad hoc dictionaries when a local type already exists. Dashboard code uses TypeScript React components with `PascalCase` page/component files such as `SchemaOverlay.tsx`.

## Testing Guidelines

Default tests must not require live external services. Live tests are marked with `live_composio`, `live_anthropic`, `live_redis`, or legacy `live`; keep them gated by environment configuration. Add focused tests next to the relevant package area, and update fixtures when behavior depends on schema or tool-output shape.

## Commit & Pull Request Guidelines

Git history uses concise, scoped summaries such as `Phase 6: benchmarks at v1 scale + new aperture-v1-dashboard` and `Live verification fixes - proxy URL, OpenAI envelope, full-scale policy.yaml`. Follow that pattern: start with the phase or scope, then state the user-visible change.

Pull requests should include a short description, test results, linked issue or task when available, and screenshots for dashboard changes. Do not commit real secrets; copy `.env.example` to `.env` locally and keep credentials out of diffs.
