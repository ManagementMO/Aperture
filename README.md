# Aperture

Token-efficiency layer for Composio-powered agents.

Aperture sits between Composio and your LLM. It measures how much of your
context window tool schemas, arguments, and results actually consume, then
trims that cost with five compounding strategies:

1. **Token attribution** — exact tiktoken counts per schema, argument, raw
   result, and compressed result, attributable per tool / toolkit / run.
2. **Effort routing** — `low | medium | high | auto` modes that decide how
   much schema and result detail a single call is allowed to spend.
3. **Output compression** — schema-aware pruning, flattening, list compaction,
   and tool-specific normalizers (Gmail headers → top-level fields, Slack
   block scaffolding → out) with raw-result references for hydration.
4. **Safe caching** — exact-match, scoped (tenant / user / connected account)
   cache for read-only tools. Writes and auth flows are never cached.
5. **Schema compaction** — selective tool exposure and rewritten descriptions
   so an unused tool doesn't burn context every turn.

## Repository layout

```
aperture/        — Python package (engine, cache, routing, observability)
api/             — FastAPI dashboard backend
frontend/        — React + Vite + Tailwind dashboard (10 demo pages)
data/            — real mock datasets (Notion 500, Linear 200, Supabase 1000, GitHub CSV 10k)
scripts/         — CLI demo scripts (benchmark, dynamic agent, recorded casts)
tests/           — pytest suite
docs/            — project plan, technical stack, roadmap
```

## Run it

```bash
# 1. Install
uv sync

# 2. Backend
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000

# 3. Frontend
cd frontend && npm install && npm run dev -- --port 5173
```

Open `http://localhost:5173/`.

## Tests

```bash
uv run pytest
```

## Demo phases

The dashboard exposes the four optimization phases described in
`TRANSFER.md`:

| Phase | What it does |
|------:|--------------|
| 1     | Task-aware compression — protect the fields the current task needs |
| 2     | Lazy hydration — send a placeholder, hydrate fields on demand |
| 3     | Prompt caching — reorder so stable content lands in the provider cache |
| 4     | Upstream field selection — request only what you need from the API |

## Status

Demo branch — the backend returns real measured numbers, the four phase
endpoints work, and the React dashboard visualizes results. See
`docs/APERTURE_PROJECT_PLAN.md` for the canonical plan and `TRANSFER.md` for
the most recent handoff notes.
