# Aperture Project Plan Status

This document summarizes what is complete against the current
`docs/APERTURE_PROJECT_PLAN.md` and what remains for later phases.

## Completed In This Branch

The implemented and validated scope is the Aperture Core layer:

- Token attribution with stable serialization, tokenizer selection, fallback
  counting, byte counts, structured events, and Markdown reports.
- Schema-aware tool output compression with YAML profiles, field pruning,
  flattening, list compaction, deduplication, deterministic long-text
  compression, raw references, and visible compressed envelopes.
- Safe exact-match execution caching with deny-by-default policy, scoped keys,
  bypass support, in-memory and Redis-compatible stores, and cache events.
- Schema description optimization with fixture/live schema fetching,
  description extraction, token ranking, deterministic rewrites, structural
  validation, and reports.
- Composio SDK integration for live schema fetch, direct tool execution, Tool
  Router sessions/search/execution, connection requests, and account discovery.
- Deterministic fixture benchmarks across `raw`, `aperture_compressed`,
  `aperture_cached`, `aperture_full`, and `shadow` modes.
- Docs, generated reports, fixtures, and tests for the implemented core.

Latest validation:

```text
uv run pytest
59 passed, 1 skipped

uv run aperture-benchmark --tasks aperture/benchmarks/tasks --out reports
passed, deterministic across repeated runs

uv run aperture-schema-report --out reports/schema_optimization_report.md
passed
```

## Not Yet Complete From The Expanded Plan

The current project plan now includes a broader product/control-plane layer
that is not implemented in this branch:

- Low/medium/high effort routing.
- Tool context budgeting.
- Schema compaction beyond description-only optimization.
- Toolkit/tool/field selection before model exposure.
- Progressive schema expansion and fallback expansion events.
- Separate schema/result cache variants.
- Full run trace store and dashboard-ready export format.
- Dashboard API.
- Next.js dashboard with tables, waterfall, metrics cards, and traces.
- Full token attribution for arguments, retries, assistant output, and unused
  schema context.
- Broader benchmark/demo agent modes around effort routing and dashboard runs.

## Signal Studio Fit

This branch is a strong Phase 1 foundation for `docs/APERTURE_SIGNAL_STUDIO.md`.
It provides the core layer Signal Studio needs: Composio execution, compression,
caching, raw references, token measurement, and benchmark reporting.

Signal Studio itself still needs a separate implementation pass for:

- Signal Collector Agent.
- Signal Pack generator.
- clustering and theme detection.
- engineering linker.
- product strategist.
- report writer.
- evidence graph and dashboard UI.
- Composio-only vs Aperture demo toggle.

## Summary

Aperture Core is complete and validated. The expanded project plan is not fully
complete yet; the remaining work is the product/control-plane, effort-routing,
dashboard, and Signal Studio application layer.
