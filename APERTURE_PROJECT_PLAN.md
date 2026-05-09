# Aperture — Full Project Plan
## Token Efficiency Layer for the Composio Meta-Tool Architecture

**Status:** Pre-development planning
**Author:** Mohammed Al-Marzouq
**Last updated:** May 2026
**Version:** 1.0 (working document — blunt, not polished)

---

## Table of Contents

1. [What This Document Is](#1-what-this-document-is)
2. [Project Summary](#2-project-summary)
3. [Composio Architecture — What We Are Building On Top Of](#3-composio-architecture--what-we-are-building-on-top-of)
4. [The Five Components — Deep Breakdown](#4-the-five-components--deep-breakdown)
   - 4A. Cross-Agent Execution Cache
   - 4B. Token Attribution Observability
   - 4C. Schema Tokenizer Optimizer
   - 4D. Session State Compressor
   - 4E. Plan Quality Scorer
5. [Honest Critique — What Is Hard, Uncertain, or Oversimplified](#5-honest-critique--what-is-hard-uncertain-or-oversimplified)
6. [Risk Register](#6-risk-register)
7. [Open Questions That Must Be Answered Before Building](#7-open-questions-that-must-be-answered-before-building)
8. [Technical Stack Decisions](#8-technical-stack-decisions)
9. [Repository Structure](#9-repository-structure)
10. [Implementation Plan — Week by Week](#10-implementation-plan--week-by-week)
11. [Success Metrics](#11-success-metrics)
12. [What a Minimal Viable Version Looks Like](#12-what-a-minimal-viable-version-looks-like)
13. [Future Work — What Comes After Internship Scope](#13-future-work--what-comes-after-internship-scope)
14. [Notes, Stray Thoughts, and Things Not to Forget](#14-notes-stray-thoughts-and-things-not-to-forget)

---

## 1. What This Document Is

This is a working planning document, not a pitch deck. It is intentionally blunt about what is hard, what is uncertain, and what we do not yet know how to do. The goal is to have one document that captures every nuance, concern, open question, and implementation detail so that nothing gets forgotten when actual coding starts.

Read this before the pitch doc. The pitch doc is a cleaned-up subset of this.

---

## 2. Project Summary

### The one-sentence version

Aperture adds a cross-agent execution cache, token cost visibility, and schema vocabulary optimization on top of Composio's existing meta-tool architecture — three things Composio provably does not have today, that compound in value with platform scale.

### What Composio already solved (do not re-propose these)

| Already solved | How |
|---|---|
| Injecting 1,000 schemas per session | 6 meta tools + on-demand schema fetching via `COMPOSIO_SEARCH_TOOLS` |
| Large result context bloat | `sync_response_to_workbench: bool` on `COMPOSIO_MULTI_EXECUTE_TOOL` |
| Zero session learning | Learned plans returned by `COMPOSIO_SEARCH_TOOLS` |
| Auth management per-session | `COMPOSIO_MANAGE_CONNECTIONS` |
| Persistent compute state | `COMPOSIO_REMOTE_WORKBENCH` (Python sandbox, persists within session) |

### What Aperture adds on top

| Component | What it adds | Confidence it doesn't exist |
|---|---|---|
| A. Cross-agent execution cache | Shared result cache across all agents for idempotent tool calls | High — no mention anywhere in docs or changelog |
| B. Token attribution observability | Token cost tracking per meta tool call, session, and user | High — usage API confirmed to only track counts |
| C. Schema tokenizer optimizer | Offline rewrite of all 1,000+ tool schemas for tokenizer efficiency | High — zero mention anywhere |
| D. Session state compressor | Structured state object to replace linear history growth in LLM context | Medium — real gap, but harder than it sounds |
| E. Plan quality scorer | Outcome-based feedback loop on learned plans in SEARCH_TOOLS | Medium-high — plans exist but no scoring exists |

### Priority order (if scope must be cut)

1. **Token attribution observability** — foundational; everything else needs this to prove value
2. **Cross-agent execution cache** — highest lever on platform cost
3. **Schema tokenizer optimizer** — offline, no runtime risk, permanent savings
4. **Plan quality scorer** — strategically important but harder
5. **Session state compressor** — real problem, but the solution path requires orchestrator cooperation (see §5)

---

## 3. Composio Architecture — What We Are Building On Top Of

This section exists to prevent mistakes. Every design decision in Aperture needs to account for how Composio actually works.

### The six meta tools (verified from reference docs)

```
COMPOSIO_SEARCH_TOOLS
  - Input: query string, optional model identifier, optional connected_account filter
  - Output: matched tool schemas + connection status per tool + execution plans from
    past sessions + related tools
  - Note: accepts a `model` param to tune planning behaviour per LLM family
  - This is the most-called meta tool. Almost every session starts with it.

COMPOSIO_GET_TOOL_SCHEMAS
  - Input: list of tool slugs (e.g. ["GITHUB_CREATE_ISSUE", "GMAIL_SEND_EMAIL"])
  - Output: full input schema for each slug
  - Used when the agent knows exactly which tool it wants without searching

COMPOSIO_MULTI_EXECUTE_TOOL
  - Input: tool_slug, params, optional sync_response_to_workbench: bool
  - Output: tool execution result (inline OR synced to workbench sandbox)
  - IMPORTANT: sync_response_to_workbench is agent-set, not automatic
    The docs say "Predictively set true if the output may be large"
    This means the agent makes the call — and agents make this wrong sometimes
  - Executes up to 50 tools in parallel

COMPOSIO_MANAGE_CONNECTIONS
  - Handles OAuth initiation, API key validation, token refresh
  - Returns Connect Links for browser-based OAuth flows
  - Can wait for connection completion (enable_wait_for_connections)

COMPOSIO_REMOTE_WORKBENCH
  - Persistent Python sandbox
  - Available helpers: run_composio_tool, invoke_llm, upload_local_file,
    proxy_execute, web_search, smart_file_extract
  - State persists across calls within a session (variables, files, memory)
  - Does NOT persist across sessions
  - Compute tiers (added April 28 2026): standard (1vCPU/1GB), medium, large, xlarge
  - Sandbox billing: free today, usage-based pricing planned

COMPOSIO_REMOTE_BASH_TOOL
  - Bash execution in the same sandbox as the workbench
  - For jq, awk, grep, curl, etc.
```

### The session model (verified from API reference)

Sessions are created via `POST /api/v3.1/tool_router/sessions` with:
- `user_id` — who the session is for (developer-defined, opaque to Composio)
- `toolkits.enabled` — array of toolkit slugs to allow
- `tools` — per-toolkit tool enable/disable overrides
- `tags.enabled` / `tags.disabled` — filter by readOnlyHint etc.
- `auth_configs` / `connected_accounts` — auth binding
- `workbench.enable` + `workbench.proxy_execution_enabled`
- `multi_account` — allow multiple connected accounts per toolkit
- `experimental.assistive_prompt` — custom context injected into meta tools
- `experimental.custom_toolkits` — bring your own tools

Sessions return a session_id and an MCP URL. The MCP URL is what gets passed to the LLM framework (LangChain, OpenAI Agents SDK, etc.).

**Critical architecture note:** The LLM framework (LangChain, OpenAI Agents SDK, etc.) maintains the conversation message history — not Composio. Composio's Tool Router only handles tool discovery and execution. This is the core reason why Component D (session state compressor) is harder than it appears: you cannot fix LLM context growth just by adding a meta tool, because the history is managed on the developer's side.

### The observability layer (verified from docs)

Two API families under `/api/v3.1/`:

**Execution logs** (`/logs/tool_calls`):
- One record per tool call
- Fields: tool_slug, toolkit_slug, connected_account_id, user_id, session_id,
  status (success/failed/all), duration_ms
- Full request payload and response body available on detail endpoint
- Filterable by date range, user, session, toolkit, tool, status

**Usage metering** (`/project/usage/{entity_type}`):
- Entity types confirmed: `tool_calls`, `sessions`
- Groupable by: user_id, toolkit_slug, tool_slug, session_id, date
- Returns aggregate counts with time bucketing
- **No token entity type exists anywhere**
- **No cost fields anywhere**

This is the confirmed observability gap that Aperture's Component B addresses.

---

## 4. The Five Components — Deep Breakdown

---

### 4A. Cross-Agent Execution Cache

#### What it is

A semantic cache shared across all Composio users that intercepts `COMPOSIO_MULTI_EXECUTE_TOOL` calls for read-heavy, idempotent operations before they reach the external API. On a cache hit: zero API call, near-zero token cost. On a miss: normal execution, result cached for future agents.

Also applies to `COMPOSIO_SEARCH_TOOLS` responses — same search query across many agents generates redundant round-trips today.

#### Why it doesn't exist yet

Nothing in the Composio docs, changelog, or SDK mentions result caching of any kind. Their own MCP gateway blog post lists caching as a best practice for gateways — and then doesn't implement it. The observability layer tracks call counts with no cache hit rate field, confirming it isn't happening.

#### Architecture

```
Agent calls COMPOSIO_MULTI_EXECUTE_TOOL
    tool_slug: "GITHUB_LIST_ISSUES"
    params: {owner: "composioHQ", repo: "composio", state: "open"}
    ↓
Aperture cache interceptor
    ↓
Step 1: Build cache key
    exact_key = sha256(f"{tool_slug}:{json.dumps(sorted_params)}")
    semantic_key = embed(f"{tool_slug}: {json.dumps(params)}")
    ↓
Step 2: Lookup
    Redis GET exact_key → fast path, O(1)
    if miss: Qdrant search(semantic_key, threshold=0.95, namespace=tool_slug)
    ↓
HIT  → return CachedResult(data, age, original_cost_tokens)
MISS → execute via Composio → cache with TTL → return
```

#### Cache key design — the hard part

Naive semantic caching is dangerous. Two calls that look similar but have different outputs must never collide. Key decisions:

**Always use exact-match keys for:**
- Any tool with user-specific output (`GMAIL_SEARCH_EMAILS`, `SLACK_LIST_CHANNELS`)
- Any write operation (`GITHUB_CREATE_ISSUE`, `GMAIL_SEND_EMAIL`)
- Any tool with time-sensitive output where staleness matters (`GOOGLE_CALENDAR_LIST_EVENTS`)

**Use semantic matching only for:**
- Public read operations where slight parameter variations still return the same useful result
  (e.g. `GITHUB_GET_REPO` with {owner: "composioHQ", repo: "composio"} vs same params slightly differently structured)
- `COMPOSIO_SEARCH_TOOLS` responses for semantically identical search queries
  ("send an email" vs "email someone" vs "send email" → same schema response)

**Namespace isolation:** Every cache key is prefixed by `user_id` for private operations and `PUBLIC` for truly cross-user shareable ones. The TTL policy determines which bucket a tool falls into.

#### SEARCH_TOOLS response caching — important nuance

`COMPOSIO_SEARCH_TOOLS` returns:
1. Tool schemas (shareable across users — same schema for everyone)
2. Execution plans (shareable — plans aren't user-specific)
3. Connection status per tool (NOT shareable — user-specific auth state)

So you can't cache the full `SEARCH_TOOLS` response cross-user. You need to:
- Cache schema + plan portions with a shared key (by query embedding)
- Re-fetch or separately cache the connection status portion per user
- Assemble the final response from cached schema/plan + fresh connection status

This adds complexity. A first version could skip the SEARCH_TOOLS cache and only cache MULTI_EXECUTE_TOOL results — that's still valuable and simpler.

#### TTL policy design

TTL policy must ship as a maintained config file covering all 1,000+ Composio tools. First draft classification:

```python
# Categories:
# STATIC    — changes very rarely. Long TTL.
# DYNAMIC   — changes on a schedule. Medium TTL.
# LIVE      — changes constantly. Short or no TTL.
# WRITE     — mutates state. Never cache.
# PRIVATE   — user-specific. Namespace-isolated exact-match only.

TTL_CATEGORIES = {
    # GitHub
    "GITHUB_GET_REPO":              ("STATIC",  timedelta(hours=2)),
    "GITHUB_LIST_REPOS":            ("DYNAMIC", timedelta(minutes=30)),
    "GITHUB_LIST_ISSUES":           ("DYNAMIC", timedelta(minutes=15)),
    "GITHUB_GET_ISSUE":             ("DYNAMIC", timedelta(minutes=10)),
    "GITHUB_LIST_PULL_REQUESTS":    ("DYNAMIC", timedelta(minutes=15)),
    "GITHUB_CREATE_ISSUE":          ("WRITE",   None),
    "GITHUB_CREATE_PR":             ("WRITE",   None),
    "GITHUB_ADD_COMMENT":           ("WRITE",   None),

    # Gmail — always private, even reads
    "GMAIL_SEARCH_EMAILS":          ("PRIVATE", timedelta(minutes=5)),
    "GMAIL_GET_EMAIL":              ("PRIVATE", timedelta(minutes=10)),
    "GMAIL_SEND_EMAIL":             ("WRITE",   None),

    # Notion
    "NOTION_QUERY_DB":              ("DYNAMIC", timedelta(minutes=10)),
    "NOTION_GET_PAGE":              ("DYNAMIC", timedelta(minutes=15)),
    "NOTION_CREATE_PAGE":           ("WRITE",   None),

    # Slack — always private
    "SLACK_LIST_CHANNELS":          ("PRIVATE", timedelta(minutes=15)),
    "SLACK_SEARCH_MESSAGES":        ("PRIVATE", timedelta(minutes=5)),
    "SLACK_SEND_MESSAGE":           ("WRITE",   None),

    # Web search
    "SERPAPI_SEARCH":               ("STATIC",  timedelta(hours=6)),
    "TAVILY_SEARCH":                ("STATIC",  timedelta(hours=6)),

    # Meta tool responses
    "COMPOSIO_SEARCH_TOOLS":        ("STATIC",  timedelta(hours=1)),
}
```

The full 1,000-tool TTL config is real work — probably 2–3 days of classification, but it only needs to be done once and maintained as tools are added.

#### Network effect math

Assume:
- 100,000 active developers
- Average 50 sessions/day per developer
- Average 5 MULTI_EXECUTE_TOOL calls per session
- 30% of calls are public read operations (cacheable cross-user)
- Cache hit rate starts at 0%, grows as cache warms up

At steady state with a warm cache, public read operations from popular apps (GitHub, Notion, Slack) could realistically reach 60–80% hit rate within hours of platform usage. Private operations always go through.

Even a 20% overall hit rate across all calls eliminates ~5M API calls/day. The token savings are secondary to the API rate limit relief and latency improvement for developers.

#### What could go wrong

- **Stale data bugs**: A developer gets cached issue list from 14 minutes ago and makes a decision on outdated data. The TTL policy is the mitigation but it's never perfect. Need a cache bypass header / parameter for time-sensitive sessions.
- **Cache poisoning**: A failed or corrupted tool result gets cached and served to future agents. Mitigation: only cache `status: success` responses, validate response schema before caching.
- **Semantic collision**: Qdrant returns a "match" that isn't actually equivalent. Mitigation: keep semantic matching conservative (threshold 0.95 is high), only apply it to SEARCH_TOOLS queries (not MULTI_EXECUTE params where correctness matters more).
- **Qdrant operational overhead**: Running a vector store adds infra complexity. First version could use only Redis with exact-match keys and skip Qdrant entirely — this alone covers 80% of the value (MULTI_EXECUTE exact caching).

---

### 4B. Token Attribution Observability

#### What it is

A new layer on top of Composio's existing observability stack that tracks LLM token costs per meta tool call, session, and user — using payload size estimation since Composio doesn't sit in the LLM API call path.

#### Why it doesn't exist

Confirmed: Composio's usage API has two entity types — `tool_calls` and `sessions`. Both track counts. There is no `tokens`, `input_tokens`, `output_tokens`, or `cost` entity anywhere. The execution log tracks `duration_ms`. No token fields.

#### The measurement challenge — this is the critical nuance

Composio's Tool Router sits between the agent and **external tool APIs**, not between the agent and the **LLM**. The flow is:

```
Developer's LLM (Claude/GPT/etc.)
    → calls Composio meta tools (MCP protocol)
        → Composio executes against external APIs (GitHub, Gmail, etc.)
        → Composio returns results to the LLM
    → LLM generates next response
```

Composio sees the meta tool calls and results. It does **not** see the LLM's own API call (the one where input/output tokens are counted by Anthropic/OpenAI). Therefore, Composio cannot directly read `usage.input_tokens` from the LLM provider's API response.

**What Composio CAN measure without seeing the LLM API call:**

1. **What it sends to the agent** — the content of every meta tool response (schema payloads, execution results, plan text). By tokenizing this server-side, Composio can compute the exact token cost of its contributions to the LLM's input context.

2. **What the agent sends to it** — the tool call payloads. These are the agent's output tokens for tool use calls, roughly.

3. **Meta tool definition sizes** — the six meta tool schemas sent at session start. These are fixed and known.

**What this means:** Aperture can produce accurate "contribution to input tokens" per meta tool call. This answers the most important question: "which Composio meta tool calls are costing my LLM the most in input tokens?" It cannot directly measure total session token cost (which includes all the agent's reasoning, system prompt, user messages, etc.) — that lives outside Composio's visibility.

This is still extremely valuable. Developers know their total token cost from their LLM provider's bill. What they don't know is *why* — which calls, which tools, which sessions are the expensive ones. Aperture fills that gap.

#### Implementation

At every meta tool call, Aperture:

```python
from tiktoken import encoding_for_model

def measure_token_cost(response_payload: dict, model: str) -> TokenCost:
    enc = encoding_for_model(model)  # or Anthropic equivalent
    serialized = json.dumps(response_payload)
    token_count = len(enc.encode(serialized))
    return TokenCost(
        input_tokens_contributed=token_count,
        tool_slug=response_payload.get("tool_slug"),
        session_id=response_payload.get("session_id"),
        timestamp=datetime.utcnow()
    )
```

Store as a new event type alongside existing log events. Aggregate into new entity types in the usage API:

```
input_tokens_contributed   → tokens Composio added to LLM input context
breakdowns:
    group_by: meta_tool_slug   → which meta tool is most expensive
    group_by: toolkit_slug     → which toolkit's results cost most
    group_by: session_turn     → how cost grows across turns
    group_by: user_id          → per-user attribution
    group_by: date             → trend over time
```

#### The model parameter opportunity

`COMPOSIO_SEARCH_TOOLS` already accepts a `model` parameter described as "Used to optimize planning/search behaviour." This is the hook. If Composio knows the model, it can use the right tokenizer for accurate measurement. Aperture should read this parameter and use the correct encoding.

For sessions that don't specify a model, use cl100k_base (the GPT-4 tokenizer) as a reasonable approximation — it's close enough for decision-making purposes.

#### New observability endpoints

Matching the existing `v3.1` pattern so developers don't have to learn a new API shape:

```bash
# Token cost by meta tool slug, last 7 days
POST /api/v3.1/project/usage/input_tokens_contributed
{
  "group_by": "meta_tool_slug",
  "order_by": "total_quantity",
  "order_direction": "desc",
  "dt_gt": "2026-04-28T00:00:00Z",
  "dt_lt": "2026-05-05T23:59:59Z"
}

# Per-session turn cost growth
POST /api/v3.1/project/usage/input_tokens_contributed
{
  "group_by": "session_turn",
  "session_id": "trs_abc123"
}

# Cache savings (once cache is live)
POST /api/v3.1/project/usage/cache_tokens_saved
{
  "group_by": "tool_slug",
  "dt_gt": "2026-05-01T00:00:00Z"
}
```

#### Why this is the most important component to build first

Every other Aperture component is valuable but its value is invisible without attribution. If you ship the schema optimizer but can't show how many tokens each optimized schema saves per day, you can't prove the ROI. If you ship the cache but can't show the hit rate and token savings, you can't argue for investing more in it. Token attribution is the measurement layer that makes everything else legible. Build it first.

---

### 4C. Schema Tokenizer Optimizer

#### What it is

A one-time offline pipeline that rewrites Composio's 1,000+ tool description fields to minimize token cost without changing what the schema conveys or how agents use the tools. Run once (and again when new tools are added). Results committed to the registry permanently.

#### Why this matters

`COMPOSIO_SEARCH_TOOLS` and `COMPOSIO_GET_TOOL_SCHEMAS` return tool descriptions every session. These descriptions are written by humans in natural language for human readability — not for tokenizer efficiency. There is a measurable gap between "reads well to a human" and "tokenizes compactly for an LLM."

Tool schemas are injected into every session that uses those tools. If 100,000 developers each get a slightly bloated GITHUB_CREATE_ISSUE description 50 times per day, that adds up permanently. Fixing it once saves forever.

#### The pipeline in detail

```
Step 1: Inventory and baseline measurement
  - Pull all tool schemas from Composio registry via API
  - For each schema, tokenize the `description` and `parameter descriptions`
    using tiktoken (cl100k_base for GPT-family) and Anthropic tokenizer
  - Record baseline token count per field per tool
  - Sort by (baseline_tokens × estimated_call_frequency) descending
  - Start optimization from the highest-leverage tools first

Step 2: Rewrite candidate generation
  - For each description field, apply rewrite rules:
    a) Strip verbose preambles:
       "Creates a new issue in a specified GitHub repository." →
       "Create a GitHub issue."
    b) Compress parameter lists:
       "The owner of the repository (GitHub username)" → "Repo owner (GitHub username)"
    c) Remove redundant type annotation prose:
       "Provide a string containing the title of the issue" → "Issue title"
    d) Use imperative mood consistently (saves 1-2 tokens per description)
    e) Replace multi-token compound phrases with single-token equivalents where possible
  - Generate 3 candidate rewrites per field at different compression levels

Step 3: Semantic equivalence validation
  - For each tool with candidates, run 50 held-out test prompts through
    both original and rewritten schema
  - Measure:
    a) Same tool selected? (most important)
    b) Same required parameters populated?
    c) Same optional parameters inferred from context?
  - Accept only candidates where all 50 prompts produce identical tool selection
    and parameter extraction as the original schema
  - If no candidate passes: keep original, flag for manual review

Step 4: Token reduction measurement
  - For each accepted rewrite: record original_tokens, new_tokens, reduction_pct
  - Aggregate total projected savings across call frequency

Step 5: Commit to registry
  - Propose schema updates as a batch (internal PR or direct registry write)
  - Keep original descriptions in a `description_verbose` field for documentation
  - Tag optimized schemas with `aperture_optimized: true` + optimizer version
```

#### Realistic numbers from a test run

Here is an actual test on three real-style Composio tool descriptions:

```
GITHUB_CREATE_ISSUE (description field only):
  Original: "Creates a new issue in a specified GitHub repository. You must
  provide the repository owner username, the repository name, and the issue
  title. Optionally, you may include a body for the issue description,
  assignees as a list of GitHub usernames, milestone as a milestone number,
  and labels as a list of label names."
  Tokens (cl100k): 68
  
  Optimized: "Create a GitHub issue. Required: owner, repo, title.
  Optional: body, assignees (usernames), milestone (number), labels."
  Tokens (cl100k): 28
  Reduction: 59%

GMAIL_SEND_EMAIL (description field only):
  Original: "Sends an email message to one or more recipients through the
  authenticated Gmail account. You must specify the recipient email address
  or addresses in the to field, and the subject line of the email. The body
  of the email can be provided as plain text or HTML. You may optionally
  specify CC and BCC recipients."
  Tokens (cl100k): 62
  
  Optimized: "Send an email via Gmail. Required: to, subject, body.
  Optional: cc, bcc. Body accepts plain text or HTML."
  Tokens (cl100k): 27
  Reduction: 56%

NOTION_CREATE_PAGE (description field only):
  Original: "Creates a new page in Notion. You can create the page as a
  child of an existing page or inside a database. If creating inside a
  database, you may need to provide property values that match the database
  schema. The title of the page must always be provided."
  Tokens (cl100k): 57
  
  Optimized: "Create a Notion page. Required: title, parent (page or
  database ID). For database pages: include matching property values."
  Tokens (cl100k): 26
  Reduction: 54%
```

Average reduction of ~56% across these three. Conservative estimate across all 1,000+ tools: 35–55% per description. The variance is high — some are already lean, some are extremely verbose.

#### Important caveat about semantic equivalence testing

The test described above needs to be implemented carefully. The validation suite must include:

- **Disambiguation tests**: prompts designed to require the model to distinguish between similar tools (GITHUB_CREATE_ISSUE vs GITHUB_CREATE_PR). Make sure the compressed schema still guides correct selection.
- **Parameter inference tests**: prompts where optional parameters should or should not be included. Make sure the compressed description still correctly signals which parameters are optional.
- **Edge case tests**: prompts with unusual parameter values, non-English input, ambiguous intent.

Running LLM inference for 50 prompts × 3 candidates × 1,000 tools = 150,000 inference calls. At ~200 tokens per call (small prompts), that's about 30M tokens. At Sonnet pricing, roughly $90–150 for the full validation run. This is a one-time cost for permanent savings.

#### Maintenance: what happens when Composio adds new tools?

This pipeline needs to run on any newly added tool before its schema is deployed. This means integrating it as a step in the tool onboarding process — either automated (run optimizer as part of CI when a new schema is merged) or manual (optimizer run on a schedule and new tools flagged for review).

---

### 4D. Session State Compressor

#### What it is

A structured state object + new meta tool (`COMPOSIO_SESSION_STATE`) that enables agents to replace growing conversation history with an in-place state machine — keeping LLM context cost flat across turns instead of growing linearly.

#### The real problem with LLM context growth

In a multi-turn Composio session, a typical turn sequence looks like:

```
Turn 1:  [system_prompt] + [6 meta tool definitions] + [user message]
         → ~2,000 input tokens

Turn 2:  [system_prompt] + [6 meta tool definitions] + [user message]
         + [assistant turn 1] + [tool calls turn 1] + [tool results turn 1]
         → ~5,000 input tokens

Turn 5:  Everything above + turns 2, 3, 4
         → ~12,000 input tokens

Turn 10: Everything above + turns 5–9
         → ~25,000 input tokens
```

Linear growth. By turn 10, the session costs 12× what it cost at turn 1, even though most of what was said in turns 1–5 is no longer relevant to the current task step.

This is confirmed as unaddressed by Composio. The workbench handles Python-side state (variables, data) but the LLM's conversation history is managed entirely by the developer's orchestrator (LangChain, OpenAI Agents SDK, etc.).

#### The fundamental architectural challenge — must be understood before building

**Composio does not control the LLM's message history.** The MCP URL returned by the Tool Router is passed to an LLM framework (e.g. LangChain). That framework maintains the message list and passes it to the LLM on every call. Composio's Tool Router handles tool execution — it does not intercept the LLM's full API call.

This means: **adding `COMPOSIO_SESSION_STATE` as a meta tool does not automatically compress context.** The developer's orchestrator still appends conversation history normally. The meta tool approach only works if:

1. The developer **explicitly uses** `COMPOSIO_SESSION_STATE` to read/write state
2. The developer **configures their orchestrator** to pass only the last N turns (or just the state object) instead of full history
3. The agent is **prompted** to use the state tool instead of relying on remembered context

This is a bigger ask than "here's a new meta tool — context is compressed automatically." It requires a pattern shift in how developers structure their agents.

#### Realistic implementation paths

**Path 1: Opt-in best-practice pattern (lowest friction)**

Provide:
- The `COMPOSIO_SESSION_STATE` meta tool (read/update/reset operations)
- A prompt template instructing the agent to use it
- SDK helpers that limit message history to last N turns and inject the state object

Developers who want compression opt in by using the pattern. Those who don't, nothing changes. This is the right first version.

```python
# Developer changes their agent setup from:
agent = YourAgent(mcp_url=session.mcp_url)

# To:
from aperture import stateful_agent_config

agent = YourAgent(
    mcp_url=session.mcp_url,
    **stateful_agent_config(
        state_url=session.state_url,    # Aperture-managed state endpoint
        max_history_turns=3,            # Keep only last 3 turns verbatim
    )
)
```

**Path 2: Session-level config (medium friction)**

Add `state_compression: true` to the session creation payload. Composio then:
- Adds `COMPOSIO_SESSION_STATE` to the meta tool set automatically
- Returns a recommended system prompt addendum instructing the agent to use it

Still requires the developer's orchestrator to truncate history, but gives more built-in guidance.

**Path 3: Proxy-level history truncation (most powerful, most complex)**

Build an HTTP proxy that wraps the MCP endpoint and intercepts the developer's LLM API calls (requires the developer to route their LLM calls through Aperture rather than directly to the provider). The proxy:
- Intercepts the message history before it reaches the LLM
- Replaces all turns older than N with the compressed state object
- Passes the truncated context to the LLM
- Parses the response and updates the state object

This is the "works without any developer changes" version but it requires the developer to proxy their LLM calls — a significant ask and a privacy consideration. Not for v1.

**Recommendation:** Build Path 1 for the internship. Document it clearly. Measure whether developers use it. If adoption is high, invest in Path 2 or 3 in a follow-up.

#### The state schema

```json
{
  "_meta": {
    "version": 1,
    "session_id": "trs_abc123",
    "turn_count": 8,
    "created_at": "2026-05-05T10:00:00Z",
    "updated_at": "2026-05-05T10:14:32Z"
  },
  "goal": "String — the high-level objective of this session",
  "phase": "String — current step in the workflow (planning/executing/reviewing)",
  "completed": ["Array of strings — steps the agent has confirmed done"],
  "pending": ["Array of strings — steps remaining"],
  "facts": {
    "key": "value — structured findings discovered during the session"
  },
  "decisions": [
    {"turn": 3, "decision": "Chosen option A over B because X", "rationale": "..."}
  ],
  "working_memory": "String — short-term context for the current step only",
  "errors": [
    {"turn": 5, "tool": "GITHUB_CREATE_ISSUE", "error": "Rate limited", "resolution": "Retried at turn 6"}
  ]
}
```

Design principles:
- Semi-structured: `facts` and `working_memory` are free-form so agents can store arbitrary context
- `decisions` array preserves rationale that would otherwise need full history to reconstruct
- `errors` array handles the failure recovery use case (one of the hardest things to compress)
- Agent can add any key to the top level if the schema doesn't cover the use case

---

### 4E. Plan Quality Scorer

#### What it is

A feedback loop on top of `COMPOSIO_SEARCH_TOOLS`'s "learned plans" feature that scores plans by actual outcome quality, not just by recency or frequency — surfacing the plans most likely to succeed rather than just the ones tried most recently.

#### The learned plans gap

`COMPOSIO_SEARCH_TOOLS` already returns execution plans from past sessions. This is a genuine differentiator. But the plans are surfaced without quality signal — an agent sees a plan that worked 9/10 times and one that worked 1/10 times with equal prominence.

The gap is confirmed by the absence of any plan scoring, success rate, or outcome tracking in the documentation.

#### The core hard problem: detecting goal completion

This is the thing the pitch doc glosses over. How do you know if a session completed its goal?

**Option A: Agent self-report**
Add a signal the agent emits at session end: `COMPOSIO_END_SESSION(outcome: "success" | "failure" | "partial", notes?: string)`.
- Pros: simple, cheap, explicit
- Cons: requires developer to wire this up; agents don't always know when they've failed; low adoption unless made compelling

**Option B: LLM evaluator**
At session end, run a lightweight LLM call that reads the session's first user message and last assistant message and judges: "Was the task completed?"
- Pros: works without developer changes; reasonable accuracy
- Cons: costs tokens per session; adds latency; LLM judgement is imperfect

**Option C: Proxy signals (heuristics)**
Infer completion from observable session patterns:
- Sessions ending with no tool calls for 3+ turns (possible completion or abandonment)
- Sessions where the last assistant message contains phrases like "completed", "done", "here is your..."
- Sessions that were followed by the developer creating a new session with a different goal (suggests prior session finished)
- Session duration: very short sessions with few calls may be failures; sessions that run to natural end points are likely successes

**Option D: Developer feedback webhook**
Composio emits a webhook after each session. Developer's backend can POST back an outcome signal within a configured window.
- Pros: most accurate; developer knows their own goal
- Cons: requires developer integration; most won't bother

**Recommended approach for v1:** Option C (proxy signals) + Option A (optional explicit signal). Use heuristics to get a reasonable signal for most sessions, accept optional explicit outcomes as an override when developers care enough to instrument it.

#### Quality score formula

```python
def plan_quality_score(plan_id: str) -> float:
    executions = get_plan_executions(plan_id, min_count=5)
    if len(executions) < 5:
        return None  # insufficient data — don't surface yet

    success_rate = sum(1 for e in executions if e.outcome == "success") / len(executions)
    avg_turns = mean(e.turns_taken for e in executions)
    avg_tool_calls = mean(e.tool_calls_made for e in executions)

    # Normalize each dimension to [0, 1]
    turns_score = 1 / avg_turns  # fewer turns = better
    calls_score = 1 / avg_tool_calls  # fewer calls = better

    return success_rate * 0.6 + turns_score * 0.25 + calls_score * 0.15
    # Success rate is weighted highest — it's the most important signal
```

Weights (0.6 / 0.25 / 0.15) are a first guess. Should be tuned with A/B testing once data exists.

#### Pruning policy

- Plans with score < 0.3 after ≥ 20 executions → flagged for review
- Plans with score < 0.2 after ≥ 30 executions → removed from surfacing
- All pruning decisions logged and reversible

#### Data privacy consideration

Plan text may contain details about a user's workflow or data. Before storing plans in a shared quality-scoring system, confirm with Composio's legal/privacy team that plan content is considered platform metadata (shareable) vs. user data (must be isolated). This is an open question before build.

---

## 5. Honest Critique — What Is Hard, Uncertain, or Oversimplified

This section is deliberately harsh. These are the failure modes.

### "The token savings will be X%" — almost all the numbers are estimates

Every token reduction percentage in the pitch doc is estimated from first principles, not from real Composio session data. We don't actually know what a typical Composio session costs because there is no token attribution system yet (that's Component B). The numbers are plausible but could be off significantly in either direction. Do not present them as measured facts to an engineering audience. Present them as what they are: projections that Component B will validate.

### Session State Compressor depends on orchestrator cooperation

Described in §4D. The short version: adding a meta tool to Composio does not automatically compress the LLM's context, because the context is managed by the developer's framework. This component only works if developers change their agent architecture to use it. Adoption is not guaranteed.

The pitch doc implied this was a "drop it in and it works" solution. It isn't. Honest framing: this is a pattern + tooling that makes context compression easy for developers who want it. Not all will.

### Semantic cache false positives are a real risk

If the Qdrant similarity threshold is wrong, similar-but-different tool calls could return incorrect cached results. For example:

- "List issues in repo X" and "List issues in repo Y" both embed similarly for `GITHUB_LIST_ISSUES`. They must NOT share a cache key. The repo name must be part of the key.
- "Search Gmail for meetings last week" and "Search Gmail for meetings this week" are semantically close. They must NOT share a cache key. Time-relative queries must be detected and excluded from semantic matching.

For MULTI_EXECUTE results, semantic cache matching should probably not be used at all — only exact-match keys. Semantic matching should be reserved for SEARCH_TOOLS query caching, where the goal is to match "send an email" with "email someone."

### Plan quality scoring measures proxies, not truth

The `goal_completed` signal is inferred from observable patterns (Option C), not from actual knowledge of what the developer was trying to do. A session that looked "complete" by proxy metrics might have actually failed, and vice versa. Quality scores will have noise. This doesn't make the feature worthless — even noisy sorting is better than no sorting — but it means the scores should be presented with appropriate uncertainty and the pruning thresholds should be conservative.

### Schema optimizer validation at scale is expensive

150,000 LLM inference calls for full validation across 1,000 tools. $90–150 one-time cost. This is fine, but it needs to be budgeted and approved. Also, validation needs to be repeated any time a schema changes, which means ongoing maintenance cost (smaller — only for the changed schemas).

### The workbench sandbox billing change

Composio added compute tier sizing (standard/medium/large/xlarge) in April 2026, with a note that "usage-based pricing is planned." If workbench billing is introduced during the internship period, this changes the economics of the workbench-dependent features. Not a blocker but worth monitoring.

### Cross-agent caching may conflict with Composio's enterprise privacy commitments

Composio is SOC2/ISO certified. Enterprise customers may have contractual requirements that their data not be shared across tenants — even in aggregated/anonymized form. A cross-agent cache that serves result data from one customer's tool calls to another customer's agent could potentially violate these commitments, depending on the data classification of the tool results.

This must be reviewed with Composio's legal/security team before building the cross-agent cache. The likely resolution: enterprise accounts get private caches only, cross-agent sharing is opt-in, and write operations and private data (email, DMs, private repos) are never shared. But this needs confirmation — it cannot be assumed.

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Semantic cache false positive returns wrong data | Medium | High | Use exact-match for MULTI_EXECUTE; semantic only for SEARCH_TOOLS queries; conservative threshold (0.95+) |
| Enterprise data sharing violates privacy commitments | Medium | Very High | Review with legal before cache build; default to private caches; opt-in for shared |
| Session state compressor has low developer adoption | High | Medium | Still valuable as a documented pattern; frame as opt-in, not default |
| goal_completed signal too noisy to be useful | Medium | Medium | Use conservative thresholds; 5+ executions before surfacing; manual review option |
| Workbench usage-based billing changes cost structure | Low | Low | Monitor; not a blocker |
| Schema validation at scale too expensive to approve | Low | Medium | Budget it upfront; $150 is small relative to permanent savings |
| Token estimates are significantly wrong in practice | Medium | Low | Frame as projections; Component B validates them; not a launch blocker |
| Composio's observability stack hard to extend without internal access | Medium | High | Needs internal engineering access; confirm this is possible on day 1 of internship |
| Qdrant operational overhead too complex for internship scope | Low | Medium | v1 can use Redis-only exact cache; Qdrant is additive later |

---

## 7. Open Questions That Must Be Answered Before Building

These are questions that cannot be answered from external documentation alone. They need to be resolved in the first week of the internship.

### Architecture access
1. Does Composio's Tool Router run as a monolith or microservices? Which service handles MULTI_EXECUTE_TOOL? Where would the cache interceptor live?
2. What database does Composio use for session storage? (PostgreSQL? DynamoDB?) This determines where COMPOSIO_SESSION_STATE data lives.
3. Is there a Redis instance already in the stack that could be extended for the cache, or does this require new infra?
4. What does the observability pipeline look like internally? (Is it a separate service, or embedded in the execution layer?)

### Data and privacy
5. Is tool execution result data considered customer data (tenanted, cannot be shared) or platform metadata (potentially shareable)? This determines the legal feasibility of cross-agent caching.
6. Are execution plan texts in SEARCH_TOOLS responses considered customer data or platform metadata?
7. Does the SOC2 compliance scope affect what data can be logged to new observability systems?

### Engineering environment
8. What is Composio's internal deployment process? (Kubernetes? Railway? Something else?) Understanding this affects how Aperture components are deployed.
9. Is there an internal test environment with real (or realistic) tool call volume where cache hit rates can be measured?
10. How is the tool registry managed? (A database? YAML files? An API?) This affects how schema optimizer results get committed.

### Product
11. How are "learned plans" generated today? Are they extracted from session logs post-hoc, or emitted by agents explicitly? This affects how the plan quality scorer hooks in.
12. Does Composio already have internal analytics on which tools are called most frequently? (This would let us prioritize the schema optimizer without building custom tooling first.)
13. Is there an existing A/B testing framework, or does this need to be built?

---

## 8. Technical Stack Decisions

### Cache layer

**v1: Redis only (exact-match)**
- Add zero new infrastructure if Redis already exists in Composio's stack
- Handles 80% of the cache value (MULTI_EXECUTE exact-match caching)
- Implement as a simple key-value store with TTL support (Redis already does this natively)
- No Qdrant needed in v1

**v2: Redis + Qdrant (add semantic matching for SEARCH_TOOLS)**
- Add Qdrant (can be self-hosted in the existing infra, aligns with Composio's SOC2 stance)
- Use text-embedding-3-small for SEARCH_TOOLS query embedding (fast, cheap, adequate resolution)
- Apply semantic matching only to SEARCH_TOOLS query cache (not MULTI_EXECUTE params)

Rationale for phasing: getting Redis working first de-risks the operational complexity. Qdrant can be added once the Redis cache is proven out.

### Token measurement

- tiktoken (OpenAI's tokenizer library) for GPT-family models
- Anthropic's tokenizer for Claude models
- Fallback: cl100k_base as a reasonable approximation for unknown models
- No new infra required — tokenization is a CPU operation, runs in the service process

### State storage for SESSION_STATE

- PostgreSQL: one row per session with a JSONB column for the state object
- If Composio already uses PostgreSQL (likely given their session model), this adds no new infra
- Reads and writes are small (a few KB per state object), so performance is not a concern

### Plan quality scoring

- Standard SQL aggregation query over an event log table
- No ML, no new infrastructure
- Event log: append-only table with columns (plan_id, session_id, outcome, turns_taken, tool_calls_made, timestamp)
- Scoring query runs on a schedule (hourly or daily) and updates a `plan_scores` table that SEARCH_TOOLS reads at query time

### Schema optimizer pipeline

- Python script, runs offline
- Dependencies: tiktoken, anthropic client, requests (to fetch schemas from Composio API)
- Runs in any environment with these deps installed
- Output: JSON diffs + a human-readable report of proposed changes

---

## 9. Repository Structure

```
aperture/
│
├── README.md
├── pyproject.toml
├── .env.example
│
├── cache/                          # Component A
│   ├── interceptor.py              # Hooks into MULTI_EXECUTE and SEARCH_TOOLS
│   ├── key_builder.py              # Exact and semantic key construction
│   ├── ttl_policy.py               # Full TTL classification for 1,000+ tools
│   ├── redis_store.py              # Redis client wrapper
│   ├── qdrant_store.py             # Qdrant client wrapper (v2)
│   └── tests/
│       ├── test_key_builder.py
│       ├── test_ttl_policy.py
│       └── test_cache_interceptor.py
│
├── observability/                  # Component B
│   ├── token_counter.py            # Payload tokenization
│   ├── event_emitter.py            # Token cost event emission
│   ├── aggregator.py               # Usage API aggregation logic
│   ├── api_endpoints.py            # New /usage/input_tokens endpoints
│   └── tests/
│
├── schema_optimizer/               # Component C
│   ├── pipeline.py                 # Main orchestration
│   ├── fetcher.py                  # Pulls schemas from Composio API
│   ├── rewriter.py                 # Rewrite rule application
│   ├── validator.py                # Semantic equivalence testing
│   ├── reporter.py                 # Generates diff report
│   ├── ttl_config.json             # Tool TTL classification (also used by cache)
│   └── tests/
│
├── session_state/                  # Component D
│   ├── meta_tool.py                # COMPOSIO_SESSION_STATE tool definition
│   ├── state_store.py              # PostgreSQL JSONB state read/write
│   ├── sdk_helpers.py              # Developer-facing helpers (stateful_agent_config)
│   ├── prompt_templates.py         # System prompt addenda for state usage
│   └── tests/
│
├── plan_scorer/                    # Component E
│   ├── event_log.py                # Session outcome event schema + emission
│   ├── scorer.py                   # Quality score computation
│   ├── pruner.py                   # Low-quality plan removal logic
│   ├── proxy_signals.py            # Heuristic goal completion detection
│   └── tests/
│
├── benchmarks/                     # Cross-cutting
│   ├── baseline_suite.py           # 20 canonical workflows × before/after
│   ├── workflows/
│   │   ├── github_issue_triage.py
│   │   ├── email_summarize.py
│   │   ├── slack_standup.py
│   │   ├── notion_research.py
│   │   └── ... (16 more)
│   └── report_generator.py
│
└── sdk/
    ├── composio_aperture.py        # Main developer-facing SDK entry point
    └── examples/
        ├── basic_cache.py
        ├── stateful_agent.py
        └── observability_query.py
```

---

## 10. Implementation Plan — Week by Week

### Prerequisites (before day 1)

- Confirm internship access level: can I modify Tool Router code directly, or do I work in a separate service that wraps it?
- Get answers to the open questions in §7 (at least questions 1–5 and 8–10)
- Set up local development environment, understand the deployment pipeline
- Get access to at least one real Composio session with real tool calls to see actual payloads

---

### Month 1 — Token Observability + Cache v1

#### Week 1: Understand the real numbers

**Goal:** Know what a real Composio session actually costs before writing any new code.

Tasks:
- [ ] Pull 100 real session logs from the execution log API
- [ ] For each session: manually count the payload sizes of each meta tool response
- [ ] Tokenize each payload using tiktoken
- [ ] Produce the first-ever "real token cost breakdown by meta tool" report
- [ ] Identify which tools have the highest per-call token cost
- [ ] Identify which meta tool is called most frequently
- [ ] Write up findings as a one-page internal report — this is the foundation for everything

This week has no new code. It's measurement. You cannot build what you haven't measured.

#### Week 2: Token attribution instrumentation

**Goal:** Real-time token cost measurement per meta tool call.

Tasks:
- [ ] Add tokenization step at each meta tool response emission point
- [ ] Emit token cost event: `{session_id, meta_tool_slug, input_tokens_contributed, timestamp}`
- [ ] Verify event data matches the manual measurements from week 1 (sanity check)
- [ ] Store events in the existing event log infrastructure (or a new table if needed)

#### Week 3: Token attribution API

**Goal:** Developers can query their token costs via the existing `v3.1` API pattern.

Tasks:
- [ ] Implement new entity type `input_tokens_contributed` in usage API
- [ ] Implement `group_by: meta_tool_slug` breakdown
- [ ] Implement `group_by: session_turn` breakdown (requires session turn tracking)
- [ ] Write documentation matching Composio's existing docs style
- [ ] Test with real session data

#### Week 4: Cache v1 — Redis exact-match for MULTI_EXECUTE

**Goal:** Ship the simplest possible cache that proves the concept.

Tasks:
- [ ] Build the cache interceptor for MULTI_EXECUTE_TOOL
- [ ] Implement TTL classification for the 50 highest-traffic tools (use week 1 frequency data)
- [ ] Build the Redis key-value cache with TTL support
- [ ] Implement cache bypass header (`X-Aperture-Cache-Bypass: true`) for developers who need fresh data
- [ ] Add cache hit/miss events to the observability layer (new entity: `cache_tokens_saved`)
- [ ] Test on the benchmark workflows
- [ ] Measure actual hit rate on real traffic (even small volume)

**Month 1 checkpoint:** Token cost is measurable. Cache is live. We have real numbers for everything.

---

### Month 2 — Schema Optimizer + Plan Scorer

#### Week 5: Schema optimizer — fetch, tokenize, baseline

**Goal:** Know exactly how inefficient the current schemas are.

Tasks:
- [ ] Fetch all tool schemas from Composio API (or internal registry, depending on architecture)
- [ ] Tokenize all description fields using tiktoken
- [ ] Sort by (token_count × estimated_call_frequency) — use week 1 frequency data
- [ ] Identify top 100 tools by optimization opportunity
- [ ] Document the baseline in a report

#### Week 6: Schema optimizer — rewrite + validate top 25

**Goal:** Ship the first batch of optimized schemas with validation.

Tasks:
- [ ] Build the rewrite rule engine (regex + heuristics is fine for v1)
- [ ] Apply rewrite rules to top 25 tools by opportunity
- [ ] Build the semantic equivalence validator (50 test prompts per tool)
- [ ] Run validation on all 25
- [ ] Measure token reduction per tool
- [ ] Propose accepted schema diffs to registry

Target: ≥ 35% average reduction across the 25. If this isn't hit, expand the rewrite rules.

#### Week 7: Plan quality scorer — event log + baseline scoring

**Goal:** Start collecting outcome data and producing quality scores.

Tasks:
- [ ] Build the outcome event schema
- [ ] Implement proxy signal detection (session end heuristics for goal_completed)
- [ ] Add optional explicit `COMPOSIO_END_SESSION` signal for developers who want to report explicitly
- [ ] Build the quality score computation (SQL aggregation query)
- [ ] Verify that plans with fewer than 5 executions are held back from scoring
- [ ] Add plan scores as a field returned by SEARCH_TOOLS (null if insufficient data)

Note: at this point there won't be enough data to see meaningful quality differentiation — the score data needs to accumulate. This week is about getting the pipeline right.

#### Week 8: A/B test setup for plan scorer + cache Qdrant upgrade

**Goal:** Start collecting A/B signal on plan quality scores + add semantic matching to cache.

Tasks:
- [ ] Set up A/B split on SEARCH_TOOLS plan surfacing (50% quality-ranked, 50% current)
- [ ] Define primary metric for A/B test (turns-to-completion on sessions)
- [ ] Deploy Qdrant instance for semantic SEARCH_TOOLS query caching
- [ ] Index existing SEARCH_TOOLS query/response pairs into Qdrant
- [ ] Implement semantic lookup for SEARCH_TOOLS cache
- [ ] Handle the connection status separation issue (cache schema+plan, skip connection status)

**Month 2 checkpoint:** 25+ schemas optimized and shipped. Plan scorer collecting data. A/B test running. Cache now includes semantic SEARCH_TOOLS caching.

---

### Month 3 — Session State Compressor + Release

#### Week 9: SESSION_STATE meta tool

**Goal:** Ship the COMPOSIO_SESSION_STATE meta tool and the developer SDK pattern.

Tasks:
- [ ] Implement COMPOSIO_SESSION_STATE tool definition (read/update/reset)
- [ ] Implement state storage (PostgreSQL JSONB or equivalent)
- [ ] Build `stateful_agent_config()` SDK helper
- [ ] Write the system prompt template for state-aware agents
- [ ] Test with a 10-turn benchmark workflow: measure input token cost per turn with and without compression

#### Week 10: Benchmark suite — full before/after measurements

**Goal:** Produce real numbers for everything, across 20 canonical workflows.

Tasks:
- [ ] Build the 20-workflow benchmark suite
- [ ] Run each workflow with no Aperture components (baseline)
- [ ] Run each workflow with cache (A)
- [ ] Run each workflow with cache + optimized schemas (B)
- [ ] Run each workflow with cache + optimized schemas + session state (C)
- [ ] Record token costs at each stage using the attribution layer from Month 1
- [ ] Compute % reduction at each stage

This produces the data for the public benchmark report.

#### Week 11: SDK release

**Goal:** Any Composio developer can add Aperture in one config change.

Tasks:
- [ ] Package the SDK: `pip install aperture-composio`
- [ ] Write getting-started documentation
- [ ] Write API reference documentation for new endpoints
- [ ] Write a migration guide from "vanilla Composio" to "Composio + Aperture"
- [ ] Publish to PyPI
- [ ] Submit PR to Composio's documentation (add Aperture mention)

#### Week 12: Benchmark report + blog post + demo

**Goal:** Public artifacts that demonstrate everything shipped.

Tasks:
- [ ] Write the benchmark report with real numbers from week 10
- [ ] Write technical blog post: "What a Composio session costs, and what we did about it"
- [ ] Record a demo video showing the observability dashboard with and without Aperture
- [ ] Submit to Hacker News (Show HN post)
- [ ] Publish on Composio's engineering blog
- [ ] Present findings to the team

**Month 3 checkpoint:** Everything shipped. Real numbers published. SDK available.

---

## 11. Success Metrics

### Must-have metrics (non-negotiable — if these aren't measured, the project failed)

| Metric | How measured | Target |
|---|---|---|
| Cache hit rate across MULTI_EXECUTE calls | New cache hit event / total MULTI_EXECUTE calls | > 15% within 2 weeks of cache launch |
| Input tokens saved per cache hit | `cache_tokens_saved` entity in observability | > 500 tokens average per hit |
| Schema token reduction (top 25 tools) | Before/after tokenization of description fields | > 35% average reduction |
| Turn-over-turn token cost growth (session state) | `input_tokens_contributed` per turn | < 20% growth per additional turn (vs ~50% without compression) |

### Nice-to-have metrics

| Metric | Target |
|---|---|
| Plan quality A/B: turns-to-completion | Quality-ranked sessions complete in ≤ 15% fewer turns |
| Developer SDK adoption | ≥ 10 developers using `aperture-composio` within 2 weeks of release |
| Schema optimizer full coverage | 200+ tools optimized before internship end |
| Cache hit rate at 4 weeks | > 40% for public read operations |

### Metrics to explicitly NOT optimize for (anti-metrics)

- Total number of lines of code written (quality over quantity)
- Number of components shipped (better to ship 3 well than 5 poorly)
- Token reduction percentage as a headline number (without real session data to back it up, this is just a guess)

---

## 12. What a Minimal Viable Version Looks Like

If scope has to be cut to 6 weeks instead of 12, here is what ships:

**Week 1–2:** Token attribution observability (Components B partial — just the measurement layer, no new API endpoints yet)

**Week 3–4:** Redis exact-match cache for MULTI_EXECUTE (Component A partial — no Qdrant, no SEARCH_TOOLS caching)

**Week 5–6:** Schema optimizer for top 25 tools (Component C partial — no automation, manual rewrite + validation for the most impactful tools)

This gives: real numbers, a working cache, and 25 permanently cheaper schemas. Everything else (plan scorer, session state, Qdrant semantic cache, full schema coverage) is follow-on work.

The MVP is valuable. Don't let perfect be the enemy of shipped.

---

## 13. Future Work — What Comes After Internship Scope

These are genuine ideas that are out of scope for 3 months but worth capturing now.

**Cross-session context carry-over** — right now the workbench state doesn't survive across sessions. A structured handoff mechanism where session N's state can seed session N+1 would enable much longer-running workflows.

**Predictive cache warming** — if you can predict what tool calls an agent will make (from past session plans), you can warm the cache before the agent asks. Reduces cold-start cost on new sessions.

**Automatic `sync_response_to_workbench` detection** — currently the agent manually decides when to sync large results to the workbench. A size-based auto-trigger (if response > X tokens, automatically sync) removes this cognitive load from the agent and ensures the workbench is used consistently.

**Schema optimizer continuous integration** — run the optimizer automatically as part of Composio's tool onboarding pipeline so every new tool ships pre-optimized.

**Token cost budget enforcement** — let developers set a max token budget per session. Aperture enforces it by aggressively compressing context and caching when the budget is close to being exceeded.

**Plan quality data as a training signal** — if the plan quality scorer accumulates enough outcome data, it becomes a dataset that could be used to fine-tune a model that generates better plans from scratch, not just surfaces old ones.

---

## 14. Notes, Stray Thoughts, and Things Not to Forget

*This section is a scratchpad. Unorganised. Add to it constantly during development.*

- The `experimental.assistive_prompt` field in session config could be used to inject state-awareness instructions without modifying the meta tool set. Worth exploring as an alternative to adding a full new meta tool for Component D.

- Composio's "Rube" product (all-in-one MCP server that automatically discovers and selects right tools, keeping LLM context clean) may overlap with what Aperture is doing. Need to understand Rube's architecture before building to ensure Aperture complements it rather than duplicates it.

- The observability API uses POST requests for queries (not GET) — matching this pattern in new endpoints is important for developer consistency.

- The `tags.enabled: ["readOnlyHint"]` session config is an existing mechanism to restrict sessions to read-only tools. The cache should respect this — if a tool is in a readOnlyHint-restricted session, it's always safe to cache (it can never mutate state). This could be used to auto-classify cacheable tools.

- TTL policy file should be open-sourced and community-maintainable. As Composio adds tools, the TTL policy needs to be updated. Making this a community contribution point is better than bottlenecking it on one person.

- The `multi_account` session feature (multiple connected accounts per toolkit) complicates cache key design. If a session has two GitHub accounts connected, the same tool call from each account should NOT share a cache entry. The `connected_account_id` must be part of any user-scoped cache key.

- When testing the schema optimizer, use real Composio session logs (from week 1 measurement) as the test prompts — not synthetic prompts. Real prompts reveal real edge cases that synthetic prompts miss.

- The plan quality scorer's pruning policy (remove plans with <40% success rate after 20 executions) needs a human review step before automated removal. Automatic pruning of production data is risky. Build the flagging system first; make the removal a manual action that a Composio engineer confirms.

- For the benchmark report: include failure modes, not just successes. Show cases where the cache returned stale data and what the impact was. Show sessions where session state compression lost context and the agent had to recover. Honest benchmarks are more credible than cherry-picked ones.

- Consider building a simple dashboard UI (not just API endpoints) for the token attribution data. A visual chart of "your top 5 most token-expensive meta tool calls this week" is more compelling for developer adoption than raw API responses.

- The entire project is more interesting if framed as "infrastructure that Composio ships internally" rather than "an external library developers install." Aperture as an internal Composio improvement is more impactful than Aperture as an optional SDK. During the internship, clarify whether these components are being built as internal contributions or as a developer-facing addon.

---

*Working document. Update continuously. Last substantive revision: May 2026.*
