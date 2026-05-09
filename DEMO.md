# 🎬 Aperture Hackathon Demo

**Quick links:**
- [Live Google Sheet (10K rows)](https://docs.google.com/spreadsheets/d/1eyr5XV1pGyJTbRWpFVIp_fcrLK-oEp4tlVg3l1VsqR0/edit)
- [GitHub repo (demo branch)](https://github.com/ManagementMO/Aperture/tree/demo)
- [Dashboard (run locally)](#dashboard)

---

## 🎯 The Pitch (30 seconds)

> Composio returns **100× more tokens than competitors**. Aperture fixes this.
> 
> A 10,000-row Google Sheet read via Composio returns **547,522 tokens** — that's **4.3× your entire GPT-4o context window**. Without Aperture, your agent crashes.
>
> With Aperture: **5,728 tokens** — a **99% reduction** — with representative samples + statistics. The LLM still answers "what's the average follower count?" perfectly.

---

## 📹 Recorded Demos

### 1. Honest Comparison — Vanilla vs Aperture
```bash
# Play the recording
asciinema play demo.cast

# Or view in browser
asciinema upload demo.cast  # gives you a shareable URL
```

**What it shows:**
- Vanilla Composio: 547,522 tokens, $1.37, no cache
- Aperture 1st call: 548K raw → 5,728 compressed, $0.014, cache miss
- Aperture 2nd call: cache hit, $0, 489ms (Redis only)

### 2. Agent Workflow — Multi-Step Demo
```bash
asciinema play demo_agent.cast
```

**What it shows:**
- 4-step agent workflow (GitHub repo → issues → PRs → commits)
- 25,349 raw tokens → 4,995 compressed = **80.7% savings**
- Context window: 19.8% → 3.9%
- Cache hits on second run

### 3. Dynamic Agent — Semantic Routing
```bash
asciinema play demo_dynamic.cast
```

**What it shows:**
- Agent receives natural language intent: "Find all open bugs"
- Aperture semantically matches to 23 tools across 9 domains
- Auto-generates compression profiles
- Executes with intelligent effort selection

### 4. Benchmarks — Mode Comparison
```bash
asciinema play demo_benchmark.cast
```

**What it shows:**
- Per-tool breakdown: raw vs compressed, latency, cost, quality
- Scenario summary across all modes (off/low/medium/high/auto)

---

## 🖥️ Dashboard

```bash
uv run streamlit run dashboard/app.py
```

**5 tabs:**
1. **Overview** — Architecture diagram + key metrics
2. **Google Sheets** — Side-by-side raw vs compressed with context bars
3. **Agent Workflows** — Scenario selector + per-step breakdown + token waterfall
4. **Dynamic Agent** — Intent matching + auto-profile generation
5. **Benchmarks** — Full suite runner + comparison matrix

---

## 🚀 Live Demo Commands

```bash
# 1. Honest comparison (vanilla vs Aperture)
uv run python scripts/honest_comparison.py

# 2. Agent workflow
uv run python scripts/demo.py --scenario research_project --mode auto --cache

# 3. Dynamic agent
uv run python scripts/dynamic_agent_demo.py --intent "Find all open bugs in composio"

# 4. Benchmarks
uv run python scripts/benchmark.py --all

# 5. Dashboard
uv run streamlit run dashboard/app.py
```

---

## 📊 The Numbers

| Metric | Vanilla Composio | Aperture |
|---|---|---|
| **10K rows** | 547,522 tokens | 5,728 tokens (99%) |
| **4-step workflow** | 25,349 tokens | 4,995 tokens (80%) |
| **Cost (GPT-4o)** | ~$1.37 | ~$0.014 |
| **Context window** | 428% overflow | 4.5% ✅ |
| **2nd call** | 3,500ms + API call | 489ms, no API call |
| **Cache scoping** | None | Per-user, per-tenant |

---

## 🏗️ Architecture

```
WITHOUT Aperture:
    Agent → Composio API → Raw Result (547K tokens) → LLM ❌ CRASH

WITH Aperture:
    Agent → ApertureRunner → Composio API → Raw Result (547K)
                                ↓
                        Tabular Compression (sample + stats)
                                ↓
                        Redis Cache → 5,728 tokens → LLM ✅
```

**Key insight:** Aperture does NOT change what tools the agent calls. It only optimizes HOW results are delivered to the LLM.

---

## 🔑 What Makes This Scalable

1. **Semantic routing** — Works with ANY Composio toolkit, no hardcoding
2. **Auto-profiles** — New tools get compression rules automatically
3. **Cache scoping** — `aperture:cache:u:user-A:TOOL:hash` — no data leaks
4. **Effort modes** — `auto` mode intelligently picks compression per call
5. **Context budget** — Tracks cumulative usage, warns before overflow

---

## ⚡ Quick Start for Judges

```bash
git clone https://github.com/ManagementMO/Aperture.git
cd Aperture
git checkout demo
uv sync

# Run the demo
uv run python scripts/honest_comparison.py

# Or open the dashboard
uv run streamlit run dashboard/app.py
```

---

*Built for the May 15-16, 2026 hackathon. Demo branch: `demo`*
