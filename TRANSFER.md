# Aperture Demo — Transfer Document

> **What this is:** A tool-context compression and cost-control system for LLM agents (specifically Composio). This demo shows real token measurements and 4 optimization strategies.
> 
> **Why it exists:** Agents call tools (GitHub, Notion, Gmail, etc.) and the responses are HUGE. Sending 170K tokens of raw GitHub issues to the LLM on every turn is expensive and slow. Aperture compresses those responses before they reach the LLM.
> 
> **Current state:** Backend works. Frontend builds. 4 new optimization phases are implemented but the UI needs polish. Some compression math is still wonky (see Known Issues).

---

## The Big Picture

### What Aperture Actually Does

When an agent calls a tool like `GITHUB_LIST_ISSUES`, Composio returns a massive JSON blob with every field the API provides — URLs, metadata, null values, nested objects, etc. Most of that is useless to the LLM.

Aperture sits between Composio and the LLM and **shrinks that blob** while keeping the parts the LLM actually needs.

### The Dashboard

The frontend is a dashboard that lets you see real compression results. Open `http://localhost:5173/` to see it.

**Pages:**
- **Overview** — summary of all datasets and their raw token counts
- **Token Waterfall** — how tokens flow through a multi-tool agent run
- **Compression** — run compression on individual datasets/tools manually
- **Schema Compaction** — show how tool schemas can be shrunk
- **Cache Stats** — show cache hit/miss behavior
- **Benchmarks** — run all modes across all datasets
- **Phase 1–4 pages** — the new optimization strategies (see below)

---

## The 4 Phases (What They Mean in Plain English)

### Phase 1: Task-Aware Compression (`/task-aware`)

**The problem:** The engine used to compress everything the same way no matter what the agent was trying to do. If the agent asked "who's assigned to what?" it would still flatten the `assignee` object to just a name string, making the task impossible.

**The solution:** Each tool+task combination gets a "profile" that says which fields MUST be kept. The engine checks the profile before compressing and preserves those fields.

**Example:**
- Task: "find_issues_by_assignee" on GitHub Issues
- Protected fields: `assignee.login`, `assignee.email`, `title`, `state`, `labels.name`
- Result: The assignee object stays intact. Other non-essential fields get flattened.

**Files:**
- `aperture/compression/task_profiles.py` — defines all the profiles
- `aperture/compression/engine.py` — modified to accept `task` and `required_fields` params
- `frontend/src/pages/TaskAware.tsx` — UI to compare baseline vs task-aware

**API endpoint:** `POST /api/compress/task-aware`

---

### Phase 2: Lazy Hydration / Placeholders (`/placeholder`)

**The problem:** Even after compression, tool results are big. If the agent calls GitHub Issues and gets 8,000 tokens, that all goes into the LLM's context window even if the agent only needs one specific field later.

**The solution:** Don't send the full result to the LLM. Send a tiny "placeholder" with a reference ID. The full result is cached server-side. If the LLM later asks for a specific field (e.g. "what's the title of issue #3?"), the agent framework "hydrates" just that field.

**Example:**
- Raw result: 8,639 tokens
- Placeholder: 1,253 tokens (85% smaller)
- If needed later: hydrate `title[0]` = 10 tokens

**Files:**
- `aperture/compression/hydration.py` — server-side cache, placeholder builder, hydrate function
- `frontend/src/pages/Placeholder.tsx` — UI to create placeholders and hydrate fields live

**API endpoints:**
- `POST /api/compress/placeholder` — create a placeholder
- `GET /api/hydrate/{ref_id}?field_path=...&index=...` — hydrate a specific field

---

### Phase 3: Prompt Caching (`/prompt-cache`)

**The problem:** LLM providers (Anthropic, OpenAI) can cache repeated parts of your prompt and give you a huge discount. But most agents put dynamic content (tool results, timestamps) at the BEGINNING of the prompt, which "breaks the cache" for everything after it.

**The solution:** Reorder the prompt so stable stuff (system prompt, tool schemas, project context) comes FIRST. Dynamic stuff (tool results, user messages) comes LAST. The provider caches the stable prefix.

**Example:**
- Without optimization: 48,050 tokens billed every turn
- With caching: ~6,060 tokens billed (after the first turn)
- Estimated savings: 45–80% depending on provider

**Files:**
- `aperture/compression/prompt_cache.py` — prompt builder, block ordering, savings estimator
- `frontend/src/pages/PromptCache.tsx` — UI to see block ordering and estimated savings

**API endpoint:** `POST /api/prompt-cache/optimize`

---

### Phase 4: Upstream Field Selection (`/field-select`)

**The problem:** We fetch EVERYTHING from the API and then compress. Why not just ask the API for fewer fields in the first place?

**The solution:** Define "field profiles" that say which fields to request from each tool. The API only returns those fields. Nothing to compress because the irrelevant data never enters the system.

**Example:**
- Baseline (all Supabase user fields): 206,168 tokens → compressed to 36,526
- Field-selected (id, email, role, status, created_at only): 206,168 tokens → compressed to 6,257
- Extra 30,269 tokens saved — and it's lossless because you never fetched the extra data

**Files:**
- `aperture/compression/field_profiles.py` — defines field profiles per tool
- `frontend/src/pages/FieldSelect.tsx` — UI to compare baseline vs field-selected

**API endpoint:** `POST /api/compress/field-select`

---

## How to Run Everything

### Backend
```bash
cd /Users/khai/Desktop/Aperture
source ~/miniconda3/etc/profile.d/conda.sh
conda activate composio
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Test: `curl http://localhost:8000/api/health` should return `{"status":"ok","version":"2.0.0"}`

### Frontend
```bash
cd /Users/khai/Desktop/Aperture/frontend
npm run dev -- --port 5173
```

Open: `http://localhost:5173/`

---

## File Inventory

### New Backend Files (created for Phases 1–4)

| File | Purpose |
|------|---------|
| `aperture/compression/task_profiles.py` | Task-aware compression profiles. Defines which fields to keep for each tool+task combo. |
| `aperture/compression/hydration.py` | Lazy hydration system. Caches full results, creates placeholders, hydrates on demand. |
| `aperture/compression/prompt_cache.py` | Prompt caching optimizer. Reorders prompt blocks, estimates provider-specific savings. |
| `aperture/compression/field_profiles.py` | Upstream field selection profiles. Defines which API fields to request per tool. |

### Modified Backend Files

| File | What Changed |
|------|-------------|
| `aperture/compression/engine.py` | Added `task`, `required_fields`, `apply_field_filter` params. Fixed list recursion bug. Added `skip_wrapper` for small datasets. Added Gmail/Slack fields to `_OBVIOUS_API_FIELDS`. |
| `api/main.py` | Added 7 new API endpoints for Phases 1–4. Updated version to 2.0.0. |
| `aperture/contracts.py` | No changes in this session (was already correct). |

### New Frontend Files

| File | Purpose |
|------|---------|
| `frontend/src/pages/TaskAware.tsx` | Phase 1 demo page. Pick dataset, mode, task profile. Compare baseline vs task-aware. |
| `frontend/src/pages/Placeholder.tsx` | Phase 2 demo page. Create placeholder, see 85% savings, hydrate specific fields. |
| `frontend/src/pages/PromptCache.tsx` | Phase 3 demo page. Build optimized prompt, see block ordering and savings estimate. |
| `frontend/src/pages/FieldSelect.tsx` | Phase 4 demo page. Pick field profile, compare baseline vs field-selected compression. |

### Modified Frontend Files

| File | What Changed |
|------|-------------|
| `frontend/src/App.tsx` | Added routes for 4 new pages. |
| `frontend/src/components/Layout.tsx` | Added nav links for 4 new pages in sidebar. |
| `frontend/vite.config.ts` | Added API proxy to forward `/api` to `localhost:8000`. |
| `frontend/src/lib/api.ts` | Changed from hardcoded `http://localhost:8000` to relative URLs (uses Vite proxy). |

---

## Known Issues (READ THIS)

### 1. Gmail Compression Was Broken — Now Fixed But Needs Validation

**What happened:** The Gmail mock data has deeply nested structures (`messages` → `payload` → `headers` → `parts` → `body`). The original engine wasn't recursively compressing lists, so nothing inside `messages` was being compressed. I fixed the list recursion, but then it compressed TOO aggressively and dropped `payload` entirely (which contains the email Subject, From, To inside `headers`).

**Current state:** The engine now recursively compresses dicts inside lists. Gmail goes from 1,703 → 65 tokens (96% saved). But the compressed output is JUST `id` and `messages[].id` — the email content is gone.

**What's needed:** Decide if 96% compression with zero content is useful for the demo, or if we need to keep some email fields (Subject, From, snippet). If the latter, we need to either:
- Add a Gmail-specific extraction rule that pulls `Subject`, `From`, `To`, `Date` out of `payload.headers` before dropping `payload`
- Or add a task profile for Gmail that protects `payload.headers` and `snippet`

### 2. Task-Aware Sometimes Saves FEWER Tokens Than Baseline

**Example:** Notion pages, `search_and_list` task: baseline saves 120K tokens, task-aware saves 114K tokens. The task-aware version keeps more fields (titles, URLs, parent info) so it's slightly larger — but higher quality.

**This is by design** — task-aware trades some compression for quality. But the UI should make this tradeoff crystal clear to the user.

### 3. Frontend UI Is Functional But Not Polished

- The 4 new pages use native HTML `<select>` instead of Shadcn Select (component wasn't installed)
- No charts or visualizations on the new pages — just numbers and cards
- The sidebar is getting crowded with 10 nav items
- No loading skeletons — pages just show blank until data loads

### 4. Placeholder Hydration Is In-Memory Only

The hydration cache (`hydration.py`) uses a Python dict. If the backend restarts, all cached results are lost. For a real deployment this needs Redis or disk persistence.

### 5. Field Selection Is Simulated, Not Real

The `/api/compress/field-select` endpoint applies field filtering AFTER fetching the full dataset from the mock JSON files. In a real Composio integration, this would need to push the field list to the actual API call (e.g., GitHub's GraphQL or Supabase's `SELECT`).

### 6. Prompt Cache Is Theoretical

The prompt cache optimizer (`prompt_cache.py`) builds an optimal prompt structure and estimates savings, but it doesn't actually integrate with Anthropic's `cache_control` or OpenAI's automatic caching. It's a blueprint, not a live integration.

---

## What the Next Developer Should Do

### Immediate (Demo Polish)

1. **Fix Gmail compression** — decide what email content to keep and implement it
2. **Add charts** to the 4 new pages (use the existing `recharts` setup from the Benchmarks page)
3. **Install Shadcn Select** component: `npx shadcn add select`
4. **Add loading states** — skeletons or spinners while API calls are in flight
5. **Collapsible sidebar** — 10 nav items is too many; group them or use accordions

### Short Term (Make It Real)

1. **Wire task-aware compression into the actual agent loop** — when the agent simulator runs, pass the current task name to `compress_tool_output()`
2. **Implement real hydration** — when the LLM's response references a placeholder ref_id, automatically call `hydrate()` and inject the result
3. **Add provider-specific prompt caching** — actually send `cache_control` breakpoints for Anthropic, structure prompts for OpenAI automatic caching
4. **Connect field selection to Composio** — instead of filtering mock JSON, pass field lists to actual API calls

### Long Term (Product)

1. **Benchmark quality** — measure whether task-aware compression actually improves agent task completion rates vs. blind compression
2. **Auto-detect tasks** — instead of hardcoded profiles, use embeddings or heuristics to detect what the agent is trying to do
3. **Persistent hydration cache** — Redis backend for cross-session caching
4. **Model routing** — like RelayPlane, route simple tasks to cheaper models

---

## Quick Reference: API Endpoints

| Method | Endpoint | What It Returns |
|--------|----------|-----------------|
| GET | `/api/health` | `{status: "ok", version: "2.0.0"}` |
| GET | `/api/datasets` | List of datasets with item counts and raw token counts |
| GET | `/api/benchmarks` | Compression results for all datasets × all modes |
| GET | `/api/waterfall` | Multi-tool token flow with per-step attribution |
| GET | `/api/cache/stats` | Cache hit/miss stats |
| POST | `/api/compress/dataset` | Compress a single dataset |
| POST | `/api/execute` | Execute a mock tool and compress the result |
| GET | `/api/task-profiles?tool_slug=...` | **Phase 1** — list task profiles |
| POST | `/api/compress/task-aware` | **Phase 1** — run task-aware compression |
| POST | `/api/compress/placeholder` | **Phase 2** — create a placeholder |
| GET | `/api/hydrate/{ref_id}` | **Phase 2** — hydrate a field from cache |
| GET | `/api/hydration/stats` | **Phase 2** — hydration cache stats |
| POST | `/api/prompt-cache/optimize` | **Phase 3** — build cache-optimized prompt |
| GET | `/api/field-profiles?tool_slug=...` | **Phase 4** — list field profiles |
| POST | `/api/compress/field-select` | **Phase 4** — run field-selected compression |

---

## Data Files (Real Mock Data)

All in `/Users/khai/Desktop/Aperture/data/`:

| File | Size | Tokens | Description |
|------|------|--------|-------------|
| `notion_pages_500.json` | 500 items | 170,081 | Notion pages with titles, URLs, properties |
| `linear_issues_200.json` | 200 items | 66,467 | Linear issues with states, assignees, priorities |
| `supabase_users_1000.json` | 1000 items | 206,168 | Supabase user records |
| `github_users_10k.csv` | 10,001 rows | 617,955 | CSV of GitHub user data |

Token counts are measured with tiktoken (cl100k_base) — real counts, not estimates.

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, tiktoken
- **Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS v3, Shadcn/ui (base-nova)
- **Conda env:** `composio` at `/Users/khai/miniconda3/envs/composio`
- **Backend port:** 8000
- **Frontend port:** 5173
- **CORS:** Configured for localhost:5173

---

## Contact / Context

- This is the `demo` branch of `ManagementMO/Aperture` on GitHub
- The previous developer (before me) had a "Live Agent" WebSocket demo that was entirely fake — hardcoded numbers, simulated delays
- Everything in the current backend returns REAL measured data from actual Aperture module execution
- The frontend fetches live data via HTTP — zero hardcoded numbers
