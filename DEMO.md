# Aperture Demo

> Composio agents leak context. A 10K-row Google Sheet read returns ~547K
> tokens — 4× a GPT-4o context window. Aperture brings that down to ~5.7K
> with representative samples + statistics. The agent still answers
> "what's the average follower count?" perfectly.

---

## Run it

```bash
# Backend (FastAPI on :8000)
uv sync
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000

# Frontend (Vite + React on :5173)
cd frontend && npm install && npm run dev -- --port 5173
```

Open `http://localhost:5173/`.

Health check: `curl http://localhost:8000/api/health` → `{"status":"ok","version":"2.0.0"}`.

---

## Dashboard tour

| Section | Page | What it shows |
|---------|------|---------------|
| Measurement | Overview | Real raw token counts per dataset |
|             | Token Waterfall | Multi-tool run with schema / argument / result breakdown |
|             | Compression | Per-dataset, per-tool compression results |
|             | Schema Compaction | Effort modes and a before/after example |
|             | Cache Stats | Live cache events from `CachedExecutor` |
|             | Benchmarks | Compression matrix across datasets × modes |
| Optimizations | Phase 1 — Task-Aware | Protect fields the current task needs |
|              | Phase 2 — Placeholders | Send a tiny ref, hydrate on demand |
|              | Phase 3 — Prompt Cache | Reorder so stable content gets cached |
|              | Phase 4 — Field Select | Request only the fields you actually use |

Every number on the dashboard is measured by `tiktoken`. Nothing is hardcoded.

---

## Recorded asciicasts

The repo ships four `.cast` recordings:

```bash
asciinema play demo.cast            # vanilla Composio vs Aperture
asciinema play demo_agent.cast      # 4-step agent workflow
asciinema play demo_dynamic.cast    # semantic routing + auto profiles
asciinema play demo_benchmark.cast  # benchmark suite
```

---

## CLI

```bash
uv run python scripts/honest_comparison.py
uv run python scripts/demo.py --scenario research_project --mode auto --cache
uv run python scripts/dynamic_agent_demo.py --intent "Find all open bugs in composio"
uv run python scripts/benchmark.py --all
```

---

## Architecture

```
WITHOUT Aperture
    Agent → Composio API → Raw Result (547K tokens) → LLM ❌ context overflow

WITH Aperture
    Agent → ApertureRunner → Composio API → Raw Result (547K)
                                ↓
                        Tabular Compression (sample + stats)
                                ↓
                        Redis Cache → 5,728 tokens → LLM ✅
```

Aperture does **not** change which tools the agent calls. It only optimizes
how results are delivered to the LLM.

---

## What's real vs. simulated

| Capability | State |
|------------|-------|
| Token counting (tiktoken) | Real |
| Compression engine | Real, all five modes |
| Tool-specific normalizers (Gmail / Slack) | Real |
| Cache (Redis or in-memory fallback) | Real |
| Field selection (Phase 4) | Simulated client-side until a Composio hook is wired up |
| Prompt caching (Phase 3) | Builder + estimator only — provider cache markers not yet sent |
| Hydration cache (Phase 2) | In-memory only; Redis backend is wired but not enabled |

See `TRANSFER.md` for the latest handoff notes and known issues.
