# Repository Guidelines

## Project Structure & Module Organization

`../aperture/` is the primary Python package for token attribution, safe caching, schema optimization, observability, and the MCP proxy. Important package areas include `proxy/`, `cache/`, `compression/`, `tokenization/`, `observability/`, `schema_optimizer/`, `benchmarks/`, and `integration/`.

Tests live in this `tests/` tree and mirror package areas, for example `cache/test_policy.py`, `proxy/test_router.py`, and `schema_optimizer/test_validator.py`. Fixtures and sample tool data are in `../aperture/fixtures/`; benchmark task definitions are in `../aperture/benchmarks/tasks/`; generated reports are in `../reports/`. The active React/Vite dashboard is `../aperture-v1-dashboard/`; `../frontend/` is legacy/demo UI.

## Build, Test, and Development Commands

- `cd .. && uv sync --extra dev` installs the Python package and dev tools.
- `cd .. && make test` or `cd .. && uv run pytest` runs the full Python test suite.
- `cd .. && uv run pytest tests/proxy` runs one focused test area.
- `cd .. && uv run ruff check aperture/ tests/ scripts/` runs lint checks.
- `cd .. && make benchmark` runs `aperture-benchmark --tasks aperture/benchmarks/tasks --out reports`.
- `cd ../aperture-v1-dashboard && npm install` installs dashboard dependencies.
- `cd ../aperture-v1-dashboard && npm run build` type-checks and builds the dashboard.

## Coding Style & Naming Conventions

Use Python 3.10+, 4-space indentation, and explicit module names. Keep test files named `test_*.py` and test functions named `test_*`. Prefer existing dataclasses, typed models, and project helpers over ad hoc dictionaries when structured data is already modeled. Dashboard components use TypeScript React and `PascalCase` filenames such as `SchemaOverlay.tsx`.

## Testing Guidelines

Pytest is the default framework, with `pytest-asyncio` configured in `pyproject.toml`. Default tests must not require live services. Live tests are marked `live`, `live_composio`, `live_anthropic`, or `live_redis`; keep them gated by environment variables such as `APERTURE_ENABLE_LIVE_TESTS=true` and required credentials. Add tests next to the relevant package area and update fixtures when schema or tool-output shape changes.

## Commit & Pull Request Guidelines

Recent history uses concise scoped subjects such as `fix: harden meta-tool attribution and policy coverage`, `docs: rewrite README to reflect actual v1-fixes state`, and phase-style summaries. Start with the scope or phase, then state the user-visible change.

Pull requests should include a short description, test results, linked issue or task when available, and screenshots for dashboard changes. Do not commit secrets; use local `.env` files and keep credentials out of diffs.
