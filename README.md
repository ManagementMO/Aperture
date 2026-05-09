# Aperture

Aperture is a token-efficiency layer for Composio-powered agents. It measures
tool-output token cost, compresses verbose tool results before they enter model
context, caches safe repeated reads, optimizes schema descriptions, and proves
the result with deterministic benchmarks.

This repository intentionally excludes Signal Studio. It implements the core
Aperture package described in `APERTURE_PROJECT_PLAN.md` and
`APERTURE_CODING_AGENT_EXECUTION_PLAN.md`.

## Setup

```sh
uv sync --extra dev
cp .env.example .env
```

Live Composio execution is optional. Set `COMPOSIO_API_KEY` and
`COMPOSIO_USER_ID` to use the Composio adapter or live smoke tests.

## Test

```sh
uv run pytest
```

## Benchmark

```sh
uv run aperture-benchmark --tasks aperture/benchmarks/tasks --out reports
```

The benchmark uses deterministic fixture tasks by default and writes:

- `reports/benchmark_metrics.json`
- `reports/benchmark_report.md`

## Live Composio Validation

Aperture supports a live Composio validation command. It always fetches real
tool schemas and can optionally execute one approved read tool through the full
Aperture cache/compression pipeline.

Required for schema fetch:

```sh
export COMPOSIO_API_KEY="..."
export COMPOSIO_USER_ID="your-user-id"
export COMPOSIO_TOOLKIT="GITHUB"
uv run aperture-live-check --out reports/live_composio_check.json
```

Required for live execution:

```sh
export COMPOSIO_TOOL_SLUG="GITHUB_LIST_ISSUES"
export COMPOSIO_TOOL_SLUG="GITHUB_LIST_REPOSITORY_ISSUES"
export COMPOSIO_TOOL_ARGS='{"owner":"composiohq","repo":"composio","state":"open","per_page":1}'
# Optional. Omit to let Composio auto-resolve the user's active GitHub account.
export COMPOSIO_CONNECTED_ACCOUNT_ID="ca_..."
uv run aperture-live-check --execute --out reports/live_composio_check.json
```

The live execution path refuses tools that are not marked cacheable read
operations in `aperture/cache/policy.yaml`. That is intentional: writes/auth
flows are not valid live smoke tests for Aperture caching.

For GitHub, Aperture discovers the current Composio toolkit version
automatically. You can override it with `COMPOSIO_TOOL_VERSION` if needed.

To validate the SDK Tool Router path used by Claude Agents SDK-style
integrations:

```sh
export COMPOSIO_USE_TOOL_ROUTER=true
export COMPOSIO_SEARCH_QUERY="list repository issues"
uv run aperture-live-check --tool-router --out reports/live_composio_check.json
```

If live execution reports `ActionExecute_ConnectedAccountNotFound`, initiate a
Composio SDK connection request:

```sh
export COMPOSIO_API_KEY="..."
export COMPOSIO_USER_ID="your-user-id"
uv run aperture-connect github
```

Open the returned redirect URL, finish OAuth, then rerun
`uv run aperture-live-check --execute ...`.

## Core Pipeline

```text
tool request
  -> safe exact-match cache lookup
  -> Composio execution on miss/not-cacheable
  -> raw token attribution
  -> schema-aware compression
  -> raw reference preservation
  -> compressed token attribution
  -> model-facing compressed payload
```

## Safety Rules

- Writes, auth flows, and failed responses are not cached by default.
- Private data must never use public cache scope.
- Compression must be visible in the returned payload.
- Preserved fields in profiles are never removed.
- Raw sensitive payloads are not stored in observability events by default.
- Schema optimization only rewrites descriptions and must preserve behavior.
