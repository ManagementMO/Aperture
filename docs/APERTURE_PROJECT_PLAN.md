# Aperture — Lean Execution Plan

## Token Attribution, Tool Context Budgeting, Schema-Aware Compression, Safe Caching, and Effort-Based Routing for Composio Agents

**Status:** Lean implementation plan  
**Primary focus:** Token attribution, tool context budgeting, schema-aware tool output compression, safe repeated-call caching
**Supporting focus:** Schema compaction, schema description optimization, effort-based routing
**Final proof layer:** Semantic benchmark suite  
**Audience:** Coding agents, Composio engineers, QA agents, reviewers, project teammates  
**Goal:** Reduce the token and API waste caused by Composio tool usage while preserving agent task quality.

---

# 1. Project Summary

Aperture is an infrastructure layer for Composio-powered agents.

It focuses on five practical improvements:

1. **Token Attribution**
   Measure how many tokens Composio tool schemas, arguments, retries, and tool/meta-tool responses contribute before and after optimization.

2. **Tool Context Budgeting and Effort Routing**
   Let developers choose low, medium, or high effort modes that control how much tool context, result detail, caching, and fallback expansion a run can use.

3. **Schema-Aware Output Compression**
   Transform verbose raw tool outputs into compact model-facing payloads while preserving task-critical information.

4. **Safe Repeated-Call Caching**
   Cache approved read-only tool calls using exact-match keys, strict scoping, TTLs, and bypass support.

5. **Schema Compaction and Description Optimization**
   Reduce schema-context cost through toolkit selection, tool selection, field selection, example gating, enum pruning, progressive disclosure, and validated description rewrites.

The benchmark suite comes last. Its job is to prove the improvements with measured token savings and measured task-performance impact.

---

# 2. One-Sentence Pitch

Aperture makes Composio agents cheaper and faster by measuring tool-context cost, budgeting how much tool context each run can spend, compressing verbose schemas and results before they hit the model, caching safe repeated reads, and proving that task quality does not degrade.

---

# 3. What We Are Building

## 3.1 Core system

```text
Agent request
    ↓
Aperture effort router
    ↓
Schema selector / compactor
    ↓
Compact tool context sent to model
    ↓
Composio tool call
    ↓
Raw tool output
    ↓
Aperture token attribution
    ↓
Aperture cache check / cache write where safe
    ↓
Aperture schema-aware output compression
    ↓
Compressed model-facing payload
    ↓
Agent continues with fewer tokens
```

## 3.2 What Aperture improves

Aperture reduces waste across four main surfaces:

```text
Tool outputs      → schema-aware output compression
Repeated calls    → safe exact-match caching
Tool schemas      → schema compaction and description optimization
Tool exposure     → tool context budgeting and effort routing
All of the above  → token attribution / measurement
```

## 3.3 Developer-facing control plane

The product surface is a control plane for tool context cost.

Developers should be able to answer:

- which toolkits and tools were exposed to the model
- which exposed tools were actually called
- how many schema tokens were loaded
- how many argument tokens, result tokens, retry tokens, and assistant output tokens were spent
- how many tokens were saved by schema compaction, result compaction, schema/result caching, and execution caching
- which calls were repeated
- which calls were bypassed because they were writes, auth flows, stale, personalized, or unsafe
- which effort mode was used and whether the run needed fallback expansion

Better product wording:

- token cost observability
- tool context budgeting
- schema compaction
- execution caching
- result compaction
- effort-based routing

Tokenization is the measurement mechanism. The product is observability and control over the tool layer.

## 3.4 Effort modes

Developers should not need to tune dozens of settings manually. They should be able to pick an effort mode.

| Mode | Behavior | Best for |
|---|---|---|
| `low` | Narrow tool shortlist, required fields only, short descriptions, compact outputs, aggressive safe-read caching, expand only on failure | cheap common reads and production routes where cost matters |
| `medium` | Selected tool group, required fields plus common optional fields, moderate descriptions, balanced result detail, safe caching, fallback expansion on low confidence | normal agent workflows |
| `high` | Broader schema exposure, richer descriptions, more optional fields, examples included, fresh execution preferred for volatile data, more validation context | ambiguous, first-time, debugging, or high-stakes workflows |

Low effort must mean smaller and stricter, not unsafe. It must never reuse private data across users, skip writes, guess stale API results, or silently alter tool arguments.

## 3.5 What this is not

Aperture is not:

- a replacement for Composio
- a replacement for Workbench
- a new agent framework
- a total LLM-billing system
- a generic summarizer
- an unsafe semantic cache
- a system that hides raw outputs permanently

Aperture optimizes what the model sees while preserving raw access and measurement.

---

# 4. Scope

## 4.1 In scope

| Area | What we will build |
|---|---|
| Token attribution | Count schema, argument, retry, raw-result, compressed-result, and output tokens, plus bytes, savings, ratios, and per-tool/session totals |
| Run-level observability | Record tools exposed, tools called, unused schema context, cache status, effort mode, latency, and before/after estimates |
| Effort routing | Support low/medium/high modes that select schema exposure, result detail, caching aggressiveness, and fallback expansion policy |
| Schema compaction | Select relevant toolkits/tools, hide optional fields when safe, gate examples, prune enums, and progressively expand schema detail |
| Output compression | Compress selected high-value tool outputs using profiles, field pruning, flattening, compaction, deduplication, and optional summarization |
| Raw output references | Preserve access to full raw outputs when compression removes detail |
| Safe caching | Exact-match cache for approved read-only calls with TTL, scope, bypass, schema/API version awareness, and safety rules |
| Schema/result caching | Cache schema variants and compacted result variants separately from execution cache |
| Description optimization | Optimize selected tool descriptions and parameter descriptions with validation |
| Reporting and UI | Generate token/caching/compression/schema reports and a basic dashboard table/waterfall |
| Benchmarking | Run same tasks with and without Aperture to prove savings and quality |

## 4.2 Out of scope

These are intentionally not part of the core plan:

- session state compression
- plan quality scoring
- arbitrary semantic caching of tool execution outputs
- cross-user private cache sharing
- full LLM-provider bill attribution
- rewriting every Composio schema
- compressing every toolkit immediately
- automatic deletion of raw outputs
- aggressive compression without validation
- productionizing learned compression policies before benchmarks
- small-model decisions that skip writes, reuse private data across accounts, decide freshness alone, or silently change tool arguments

---

# 5. Architecture

## 5.1 Normal Composio flow

```text
Agent calls Composio tool
    ↓
Composio executes external API/tool
    ↓
Raw tool result returns to agent/model
    ↓
Raw result enters future model context
```

## 5.2 Full Aperture request lifecycle

The efficiency layer starts before tool execution. It controls which schemas and fields enter the model context, then controls execution reuse and result detail.

```text
Incoming agent request
    ↓
Request normalizer
    ↓
Intent / tool relevance classifier
    ↓
Effort router
    ↓
Token budgeter
    ↓
Schema selector and compactor
    ↓
Prompt / tool context builder
    ↓
Model requests tool call
    ↓
Cache eligibility check
    ↓
Composio execution if cache misses or tool is not cacheable
    ↓
Result compaction
    ↓
Telemetry logger
    ↓
Compact result returns to model
```

## 5.3 Aperture-enhanced tool-result flow

```text
Agent calls Composio tool
    ↓
Composio executes external API/tool
    ↓
Aperture intercepts result
    ↓
Count raw tokens
    ↓
If cacheable, read/write cache safely
    ↓
Load output compression profile
    ↓
Compress raw output
    ↓
Store raw output reference if needed
    ↓
Count compressed tokens
    ↓
Emit attribution/compression/cache events
    ↓
Return compact model-facing result
```

## 5.4 Workbench boundary

Workbench can store or process large results outside normal model context.

Aperture is different:

> Workbench stores large data. Aperture decides what compact version of that data the model should see.

They can work together:

```text
Large raw output
    ↓
Store full raw output in Workbench/object store
    ↓
Aperture returns compact result:
      - summary
      - key fields
      - item count
      - omitted fields
      - raw_reference_id
```

---

# 6. Component A — Token Attribution

## 6.1 Purpose

Token attribution is the measurement layer for the whole project.

It tells us:

- which tool outputs are expensive
- which sessions are expensive
- how much compression saved
- how much caching avoided
- how much schema optimization saved
- whether our improvements are real or just theoretical

## 6.2 What we measure

Aperture measures:

- run_id and effort_mode
- toolkits loaded
- tools exposed
- tools called
- full schema tokens
- exposed schema tokens
- estimated unused schema tokens
- tool argument tokens
- retry-context tokens
- raw output tokens
- compressed output tokens
- tokens saved
- compression ratio
- raw payload bytes
- compressed payload bytes
- meta-tool response tokens
- schema response tokens
- schema compaction savings
- cache-hit token savings estimate
- latency before/after where available
- token cost by tool
- token cost by toolkit
- token cost by session
- token cost by user/project where available

## 6.3 What we do not claim

Aperture does **not** automatically measure the full LLM bill unless it sits in the LLM provider request path.

Correct claim:

> Aperture measures Composio-contributed input tokens and Aperture savings.

Not:

> Aperture measures the entire OpenAI/Anthropic bill.

## 6.4 Token counting pipeline

```text
Payload produced
    ↓
Stable JSON serialization
    ↓
Tokenizer selection by model
    ↓
Token count
    ↓
Event creation
    ↓
Aggregation/reporting
```

## 6.5 Stable serialization

Use deterministic JSON so repeated counts are stable.

```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False
)
```

Requirements:

- same payload = same string
- nested keys sorted
- no payload mutation
- compact separators
- Unicode preserved
- unknown objects handled safely

## 6.6 Tokenizer strategy

Priority:

1. Use model-specific tokenizer if known.
2. Use provider-family tokenizer if known.
3. Use fallback tokenizer if unknown.
4. Mark approximate counts when fallback is used.

Example mapping:

```yaml
gpt-4.1: cl100k_base
gpt-4o: o200k_base
claude-sonnet-4: anthropic_count_tokens
unknown: cl100k_base
```

## 6.7 Main event schema

```python
@dataclass(frozen=True)
class TokenAttributionEvent:
    event_type: str                  # input_tokens_contributed / tool_output_compression
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    run_id: str | None
    effort_mode: str | None
    payload_kind: str                # schema/search/result/workbench/cache/compressed
    model: str | None
    tokenizer: str
    tokenizer_is_approximate: bool
    raw_payload_bytes: int | None
    compressed_payload_bytes: int | None
    raw_tokens: int | None
    compressed_tokens: int | None
    input_tokens_contributed: int
    tokens_saved: int
    schema_tokens_full: int | None
    schema_tokens_exposed: int | None
    argument_tokens: int | None
    retry_tokens: int | None
    compression_ratio: float | None
    cache_status: str | None         # hit/miss/bypass/not_cacheable
    aperture_version: str
```

## 6.8 Reports to generate

### Tool-output cost report

```text
Top expensive tool outputs:
1. GITHUB_LIST_ISSUES — 182,000 raw tokens
2. GMAIL_SEARCH_EMAILS — 144,000 raw tokens
3. SLACK_SEARCH_MESSAGES — 98,000 raw tokens
```

### Tool-context report

```text
Run: support-agent-prod / medium effort
Toolkits loaded: 3
Tools exposed: 41
Tools called: 2
Schema tokens exposed: 22,410
Estimated unused schema tokens: 19,900
Tool argument tokens: 420
Retry-context tokens: 700
Result tokens returned: 4,812
```

### Token waterfall

```text
User prompt:       900
Tool schemas:    8,700
Tool arguments:    420
Tool results:    3,100
Retries:           700
Assistant output: 1,200
```

### Compression savings report

```text
GITHUB_LIST_ISSUES
Raw: 182,000 tokens
Compressed: 41,000 tokens
Saved: 141,000 tokens
Reduction: 77.5%
```

### Cache savings report

```text
GITHUB_GET_REPO
Calls: 500
Cache hits: 220
API calls avoided: 220
Estimated output tokens avoided: 88,000
```

## 6.9 Run data model sketch

The MVP dashboard and reports need a simple product-level data model in addition to low-level event objects.

### `runs`

```text
id
created_at
tenant_id
agent_id
model
effort_mode
input_tokens
output_tokens
total_schema_tokens_full
total_schema_tokens_exposed
total_tool_result_tokens_raw
total_tool_result_tokens_compacted
estimated_cost_before
estimated_cost_after
latency_ms
```

### `tool_context_events`

```text
id
run_id
toolkit_slug
tool_slug
schema_version
schema_tokens_full
schema_tokens_exposed
schema_tokens_saved
was_exposed
was_called
effort_mode
```

### `tool_execution_events`

```text
id
run_id
toolkit_slug
tool_slug
normalized_args_hash
execution_type
cache_status
cache_key_hash
raw_result_tokens
compacted_result_tokens
result_tokens_saved
latency_ms
safety_class
```

### `schema_variants`

```text
id
toolkit_slug
tool_slug
schema_version
effort_mode
full_schema_hash
compacted_schema_hash
full_tokens
compacted_tokens
created_at
```

### `cache_entries`

```text
cache_key_hash
tenant_id
connected_account_id
toolkit_slug
tool_slug
args_hash
schema_version
api_version
auth_scope_hash
freshness_policy
result_hash
created_at
expires_at
safety_class
```

## 6.10 Coding tasks

| Task | Output |
|---|---|
| Build stable serializer | `tokenization/serializers.py` |
| Build tokenizer registry | `tokenization/tokenizer_registry.py` |
| Build token counter | `tokenization/token_counter.py` |
| Build event schema | `observability/event_schema.py` |
| Build event emitter | `observability/event_emitter.py` |
| Build aggregation/reporting | `observability/aggregations.py`, `observability/reports.py` |
| Build run trace store/export | `observability/run_trace.py`, `observability/dashboard_export.py` |

## 6.11 Tests

- same payload counts the same every time
- different key order gives same count
- unknown model uses fallback
- payload is not mutated
- large payload does not crash
- compression event includes raw/compressed tokens
- cache-hit event includes estimated savings
- no raw sensitive payload is stored in token events by default
- run trace records tools exposed vs tools called
- dashboard export separates schema, result, argument, retry, and cache savings

## 6.12 Definition of done

Token attribution is complete when:

- raw and compressed token counts are captured
- meta-tool/schema/result payloads can be measured
- cache and compression savings are measured
- reports can group by tool, toolkit, session, and strategy
- measured results are separated from estimates

---

# 7. Component B — Schema-Aware Output Compression

## 7.1 Purpose

Output compression is the main technical contribution.

It turns verbose raw tool outputs into compact model-facing payloads.

The goal is not maximum compression. The goal is:

> maximum useful compression without losing task-critical information.

## 7.2 Why this matters

Many tool outputs contain:

- repeated API URLs
- nested user objects
- avatar URLs
- empty/null fields
- internal IDs
- verbose metadata
- duplicate parent objects
- long text bodies
- raw HTML/Markdown
- large lists with repeated structure

The model usually does not need all of that.

## 7.3 Example transformation

### Raw output

```json
{
  "id": 123456,
  "node_id": "I_kwDOExample",
  "url": "https://api.github.com/repos/acme/app/issues/42",
  "repository_url": "https://api.github.com/repos/acme/app",
  "labels_url": "https://api.github.com/repos/acme/app/issues/42/labels{/name}",
  "comments_url": "https://api.github.com/repos/acme/app/issues/42/comments",
  "events_url": "https://api.github.com/repos/acme/app/issues/42/events",
  "html_url": "https://github.com/acme/app/issues/42",
  "number": 42,
  "state": "open",
  "title": "Login fails after OAuth redirect",
  "body": "Very long markdown body...",
  "user": {
    "login": "nikos",
    "id": 999,
    "avatar_url": "https://avatars.githubusercontent.com/u/999",
    "followers_url": "...",
    "repos_url": "..."
  },
  "labels": [
    {
      "id": 1,
      "url": "...",
      "name": "bug",
      "color": "d73a4a"
    }
  ]
}
```

### Compressed output

```json
{
  "aperture_compressed": true,
  "tool_slug": "GITHUB_LIST_ISSUES",
  "number": 42,
  "state": "open",
  "title": "Login fails after OAuth redirect",
  "author": "nikos",
  "labels": ["bug"],
  "summary": "OAuth login redirects but user remains unauthenticated.",
  "url": "https://github.com/acme/app/issues/42",
  "raw_reference_id": "raw_abc123",
  "compression": {
    "raw_tokens": 3200,
    "compressed_tokens": 420,
    "tokens_saved": 2780,
    "compression_ratio": 0.131
  }
}
```

## 7.4 Compression principles

1. Preserve task-critical fields.
2. Drop redundant API bookkeeping.
3. Flatten repeated nested objects.
4. Compact lists into useful values.
5. Summarize long text only when needed.
6. Preserve raw access through references.
7. Prefer deterministic rules before LLM summarization.
8. Make compression visible to the model.
9. Support bypass.
10. Validate compression with benchmarks.

## 7.5 Compression modes

| Mode | Behavior | Use |
|---|---|---|
| `off` | Return raw output | Debugging/bypass |
| `shadow` | Compress and measure, but return raw | Safe evaluation |
| `safe` | Remove nulls, empty fields, obvious API metadata | Default early mode |
| `balanced` | Safe + flattening + list compaction + dedupe | MVP target mode |
| `aggressive` | Balanced + summarization/projection | Only after benchmark approval |

MVP should implement:

- `off`
- `shadow`
- `safe`
- `balanced`

Aggressive mode is not required for MVP.

## 7.6 Compression strategies

### 7.6.1 Field pruning

Remove low-value fields:

```text
node_id
avatar_url
gravatar_id
followers_url
following_url
gists_url
starred_url
subscriptions_url
organizations_url
repos_url
events_url
received_events_url
labels_url
comments_url
repository_url
empty/null fields
internal API URLs when html_url exists
```

### 7.6.2 Nested object flattening

```json
{
  "user": {
    "login": "nikos",
    "id": 123,
    "avatar_url": "..."
  }
}
```

becomes:

```json
{
  "author": "nikos"
}
```

### 7.6.3 List compaction

```json
"labels": [
  {"id": 1, "name": "bug", "url": "..."},
  {"id": 2, "name": "urgent", "url": "..."}
]
```

becomes:

```json
"labels": ["bug", "urgent"]
```

### 7.6.4 Deduplication

Repeated repo/user/channel/team objects should be lifted out or replaced with compact names/IDs.

### 7.6.5 Table/row projection

For list/database outputs, keep only relevant columns.

Example:

```text
30 fields per row → 6 key fields per row
```

### 7.6.6 Long-text compression

For long bodies/content:

1. preserve raw reference
2. extract key snippets if possible
3. summarize only if allowed
4. mark summarization clearly

Example:

```json
{
  "body_summary": "User reports redirect succeeds but session cookie is not set.",
  "raw_body_reference": "raw_abc123.items[0].body"
}
```

## 7.7 Compression profiles

Each supported tool gets a profile.

### Profile format

```yaml
version: 1

default:
  mode: safe
  drop_nulls: true
  drop_empty_strings: true
  drop_empty_arrays: true
  drop_obvious_api_urls: true
  raw_reference: true
  max_string_tokens_without_summary: 300

tools:
  TOOL_SLUG:
    mode: balanced
    preserve_fields: []
    drop_fields: []
    flatten: {}
    compact_lists: {}
    summarize_fields: {}
    deduplicate: []
    raw_reference: true
```

### GitHub issue profile

```yaml
GITHUB_LIST_ISSUES:
  mode: balanced
  preserve_fields:
    - number
    - title
    - state
    - html_url
    - created_at
    - updated_at
    - comments
  flatten:
    user.login: author
  compact_lists:
    labels: name
    assignees: login
  summarize_fields:
    body:
      max_tokens: 80
      strategy: extractive
  drop_fields:
    - id
    - node_id
    - url
    - repository_url
    - labels_url
    - comments_url
    - events_url
    - locked
    - active_lock_reason
    - performed_via_github_app
  raw_reference: true
```

### Gmail search profile

```yaml
GMAIL_SEARCH_EMAILS:
  mode: balanced
  preserve_fields:
    - id
    - thread_id
    - subject
    - from
    - to
    - date
    - snippet
  summarize_fields:
    body:
      max_tokens: 120
      strategy: extractive
  drop_fields:
    - raw_headers
    - internal_date
    - size_estimate
    - history_id
  raw_reference: true
```

### Slack search profile

```yaml
SLACK_SEARCH_MESSAGES:
  mode: balanced
  preserve_fields:
    - channel_name
    - user_name
    - text
    - timestamp
    - thread_ts
    - permalink
  flatten:
    user.profile.real_name: user_name
  summarize_fields:
    text:
      max_tokens: 120
      strategy: none_unless_long
  drop_fields:
    - user.profile.image_24
    - user.profile.image_32
    - user.profile.image_48
    - user.profile.avatar_hash
    - team
  raw_reference: true
```

## 7.8 Main compression interface

```python
@dataclass(frozen=True)
class CompressionContext:
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str
    user_goal: str | None
    model: str | None
    mode: str


@dataclass(frozen=True)
class CompressionResult:
    compressed_payload: object
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    raw_reference_id: str | None
    strategy: str
    omitted_fields: list[str]
    warnings: list[str]


def compress_tool_output(
    raw_payload: object,
    context: CompressionContext,
) -> CompressionResult:
    ...
```

## 7.9 Raw output storage

When compression omits detail, preserve raw access.

Requirements:

- raw reference IDs must be opaque
- private outputs must not be stored publicly
- references should expire or follow retention policy
- model can see `raw_reference_id`
- future retrieval can fetch specific raw fields if needed

Example:

```json
{
  "raw_reference_id": "raw_7f31a9",
  "raw_available": true,
  "raw_retrieval_hint": "Use raw_reference_id if exact omitted fields are needed."
}
```

## 7.10 Compacted result cache

Result compaction can be cached separately from execution caching.

Execution caching avoids calling the external tool. Result compaction caching avoids recomputing the compacted representation for the same raw result.

Safe key:

```text
result_compaction:v1:{tool_slug}:{raw_result_hash}:{profile_version}:{mode}:{schema_version}
```

Requirements:

- cache by raw result hash, not by a fuzzy semantic match
- include compression profile version and effort mode
- never allow compacted private results to escape their tenant/account boundary
- invalidate when compression profiles change
- emit separate savings for execution cache hits and result-compaction cache hits

## 7.11 Coding tasks

| Task | Output |
|---|---|
| Profile loader | `compression/profile_loader.py` |
| Field pruning | `compression/field_pruning.py` |
| Flattening | `compression/flattening.py` |
| List compaction | `compression/list_compaction.py` |
| Deduplication | `compression/deduplication.py` |
| Long-text compression | `compression/text_summarization.py` |
| Raw output store | `compression/raw_store.py` |
| Result compaction cache | `compression/result_cache.py` |
| Envelope builder | `compression/envelope.py` |
| Main compressor | `compression/compressor.py` |
| Compression reports | `compression/reports.py` |

## 7.12 Tests

- unknown tools use safe mode
- preserved fields are never removed
- configured drop fields are removed
- null/empty fields are removed when enabled
- nested fields flatten correctly
- lists compact correctly
- raw reference is created when enabled
- long text is summarized only when allowed
- compressed tokens are lower for fixtures
- no private raw output is placed in public store
- compacted result cache key changes when raw result/profile/mode changes
- compacted private results remain scoped to tenant/account boundaries

## 7.13 Definition of done

Output compression is complete when:

- at least 5 high-value tools have profiles
- generic safe fallback exists
- compression supports safe and balanced modes
- raw references are preserved
- compression events are emitted
- tests pass for GitHub, Gmail, Slack, Notion, and one mixed/unknown fixture

---

# 8. Component C — Safe Repeated-Call Caching

## 8.1 Purpose

Caching avoids repeated safe tool execution.

Compression helps even on first call. Caching helps when the same call repeats.

Caching is primary enough to build, but must stay conservative.

## 8.2 Cache principle

> A cache miss is better than a wrong or private cache hit.

## 8.3 What can be cached

Good candidates:

- schema variants by toolkit, tool, schema version, and effort mode
- compacted result variants by raw result hash, compression profile version, and effort mode
- public repo metadata
- GitHub issue lists
- GitHub PR lists
- Notion page/database reads
- Slack channel lists/searches, scoped to account/user
- Gmail search/read results, scoped to account/user
- company profile lookups
- repeated web/document searches, with TTL

## 8.4 What must not be cached

Never cache:

- send email
- create issue
- update PR
- delete file
- create calendar event
- OAuth/auth flows
- token refresh
- writes/mutations
- private data under public scope
- failed or partial responses by default

## 8.5 Cache classes

Keep these caches separate in implementation and reporting.

| Cache class | Purpose | Safe default |
|---|---|---|
| Schema cache | Reuse compacted schema variants by toolkit/tool/version/effort mode | Yes |
| Read execution cache | Avoid re-running approved read-only external calls | Yes, with exact key and TTL |
| Search cache | Reuse repeated searches with identical args/account/freshness policy | Sometimes |
| Result compaction cache | Reuse compacted form of the same raw result | Yes, by raw result hash |
| Tool relevance cache | Reuse likely tool shortlist for similar route/intent metadata | Yes, as recommendation only |
| Write dedupe | Prevent accidental duplicate writes through idempotency keys | Separate from cache; no silent reuse |

## 8.6 Cache flow

```text
Tool call requested
    ↓
Check cache bypass
    ↓
Load cache policy
    ↓
If not cacheable: execute normally
    ↓
Normalize params
    ↓
Build scoped exact key
    ↓
Redis/in-memory GET
    ↓
Hit: return cached result + emit hit event
    ↓
Miss: execute normally
    ↓
If success: store result with TTL
    ↓
Emit miss/store event
```

## 8.7 Exact-match only

MVP caching should use exact-match keys only.

Do not use semantic matching for execution outputs.

Safe cache key:

```text
aperture:v1:{tenant_id}:{scope}:{toolkit_slug}:{tool_slug}:{schema_version}:{api_version}:{auth_scope_hash}:{freshness_policy}:{sha256(normalized_params)}
```

Example:

```text
aperture:v1:t_123:account:github:GITHUB_LIST_ISSUES:github@2026-05-09:rest-v3:authhash_abc:ttl_900:sha256(...)
```

The key must include enough context to prevent cross-user, cross-account, cross-schema, or cross-freshness reuse.

## 8.8 Cache scopes

| Scope | Required ID | Use |
|---|---|---|
| public | none | truly public data only |
| project | project_id | project-level shared reads |
| user | user_id | user-specific reads |
| account | connected_account_id | private connected-account reads |
| session | session_id | session-local results |
| none | none | not cacheable |

If the required scope ID is missing, do not cache.

## 8.9 Cache policy format

```yaml
version: 1

default:
  cacheable: false
  operation_type: unknown
  privacy_scope: none
  ttl_seconds: null
  matching: none
  reason: deny_by_default

tools:
  GITHUB_GET_REPO:
    cacheable: true
    operation_type: read
    privacy_scope: public
    ttl_seconds: 7200
    matching: exact
    freshness_policy: static_public_metadata

  GITHUB_LIST_ISSUES:
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 900
    matching: exact
    freshness_policy: short_live_repo_state

  GMAIL_SEARCH_EMAILS:
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 300
    matching: exact
    freshness_policy: private_short_live_search

  GMAIL_SEND_EMAIL:
    cacheable: false
    operation_type: write
    privacy_scope: account
    ttl_seconds: null
    matching: none
    reason: write_operation
```

## 8.10 Cache event schema

```python
@dataclass(frozen=True)
class CacheEvent:
    event_type: str              # cache_lookup
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    tool_slug: str
    toolkit_slug: str | None
    cache_status: str            # hit/miss/bypass/not_cacheable/error
    cache_scope: str
    cache_key_hash: str | None
    schema_version: str | None
    api_version: str | None
    auth_scope_hash: str | None
    freshness_policy: str | None
    ttl_seconds: int | None
    cached_age_seconds: int | None
    api_call_avoided: bool
    tokens_saved_estimate: int
    reason: str | None
```

## 8.11 Bypass support

Supported:

```text
X-Aperture-Cache-Bypass: true
```

Optional tool metadata:

```json
{
  "aperture_cache_bypass": true
}
```

## 8.12 Coding tasks

| Task | Output |
|---|---|
| Cache policy loader | `cache/policy.py`, `cache/policy.yaml` |
| Param normalizer | `cache/normalizer.py` |
| Key builder | `cache/key_builder.py` |
| Redis/in-memory store | `cache/redis_store.py` |
| Cache interceptor | `cache/interceptor.py` |
| Schema cache | `cache/schema_cache.py` |
| Result compaction cache interface | `cache/result_cache.py` |
| Bypass handling | `cache/bypass.py` |
| Cache reports | `cache/reports.py` |

## 8.13 Tests

- unknown tools are not cacheable
- write tools are never cached
- auth tools are never cached
- param order does not change key
- account-scoped keys include account ID
- cache key changes when schema version, API version, auth scope, or freshness policy changes
- missing required scope prevents caching
- failed responses are not cached
- cache hit avoids execution
- cache bypass forces execution
- cache event emitted on hit/miss/bypass/not-cacheable

## 8.14 Definition of done

Caching is complete when:

- safe read calls can be cached
- writes/auth tools cannot be cached
- exact-match keys are scoped correctly
- cache hits avoid execution
- bypass works
- cache events measure API calls avoided and token savings estimate

---

# 9. Component D — Schema Compaction and Description Optimization

## 9.1 Purpose

Schema compaction reduces the token cost of tool discovery and tool schemas.

Output compression reduces result cost. Caching reduces repeated work. Schema optimization reduces tool-definition cost.

This component covers more than rewriting descriptions. It controls which toolkits, tools, fields, examples, enum values, and description detail are exposed to the model for a given run and effort mode.

## 9.2 Correct framing

Composio already has some schema simplification and schema modifier capabilities.

Aperture’s role is:

> measured tokenizer-aware schema compaction and description optimization with behavior validation.

## 9.3 What we optimize

Allowed:

- toolkit selection
- tool selection inside a toolkit
- optional field hiding
- example gating
- enum pruning
- progressive disclosure / schema expansion
- tool description text
- parameter description text
- enum description text
- repeated verbose phrasing
- redundant type explanations
- long prose that can become structured required/optional lists

Not allowed without explicit review:

- tool slugs
- parameter names
- required fields
- parameter types
- auth behavior
- execution behavior
- return schemas
- safety-critical warnings
- decision-critical enum values

## 9.4 Effort-mode schema behavior

| Mode | Schema behavior |
|---|---|
| `low` | expose only top-ranked tools, required fields, short descriptions, few/no examples |
| `medium` | expose selected tools, required fields, common optional fields, moderate descriptions |
| `high` | expose broader tool set, detailed fields, examples, edge cases, and richer optional fields |

If low or medium mode lacks required detail, Aperture should support fallback expansion and log the expansion event.

## 9.5 Description rewrite example

Before:

```text
Creates a new issue in a specified GitHub repository. You must provide the repository owner username, repository name, and issue title. Optionally, you may include a body, assignees, labels, and milestone.
```

After:

```text
Create a GitHub issue. Required: owner, repo, title. Optional: body, assignees, labels, milestone.
```

## 9.6 Optimization pipeline

```text
Fetch tool schemas
    ↓
Extract description fields
    ↓
Count tokens
    ↓
Rank by token cost × usage frequency × exposure frequency
    ↓
Generate toolkit/tool shortlist candidates
    ↓
Generate field/example/enum compaction candidates
    ↓
Generate rewrite candidates
    ↓
Validate tool selection and params
    ↓
Accept safe rewrites
    ↓
Generate before/after report
```

## 9.7 Validation

A rewrite is accepted only if:

- same tool is selected
- required parameters remain clear
- optional parameters remain clear
- similar tools are not confused
- safety/auth meaning is preserved
- low/medium compaction can expand when the prompt requires hidden fields

Validation case:

```json
{
  "case_id": "github_create_issue_001",
  "user_prompt": "Create a GitHub issue in composioHQ/composio titled 'Fix login bug' and label it bug.",
  "expected_tool": "GITHUB_CREATE_ISSUE",
  "expected_required_params": ["owner", "repo", "title"],
  "expected_optional_params": ["labels"],
  "forbidden_tools": ["GITHUB_CREATE_PULL_REQUEST"]
}
```

## 9.8 Coding tasks

| Task | Output |
|---|---|
| Schema fetcher | `schema_optimizer/fetch_schemas.py` |
| Field extractor | `schema_optimizer/extract_fields.py` |
| Schema tokenizer | `schema_optimizer/tokenize_schemas.py` |
| Candidate ranker | `schema_optimizer/rank_candidates.py` |
| Tool relevance selector | `schema_optimizer/tool_selector.py` |
| Field/example/enum compactor | `schema_optimizer/schema_compactor.py` |
| Progressive disclosure policy | `schema_optimizer/expansion_policy.py` |
| Rewrite rules | `schema_optimizer/rewrite_rules.py` |
| Validator | `schema_optimizer/validator.py` |
| Report generator | `schema_optimizer/reports.py` |

## 9.9 Tests

- description fields extracted correctly
- token counts deterministic
- low mode exposes required fields
- medium mode exposes common optional fields
- high mode can expose full schema
- hidden optional fields can trigger expansion
- rewrites do not change parameter names
- rewrites do not change required fields
- unsafe rewrite is rejected
- accepted rewrite has before/after token savings
- report includes validation status

## 9.10 Definition of done

Schema compaction and optimization are complete when:

- top candidate schemas are measured
- low/medium/high schema modes work for supported toolkits
- schema variants are cached by schema version and effort mode
- fallback expansion is logged
- top rewrites are generated
- accepted rewrites pass validation
- before/after report exists
- no execution behavior is changed

---

# 10. Repository Structure

```text
aperture/
  README.md
  pyproject.toml
  .env.example
  Makefile

  aperture/
    __init__.py
    config.py
    types.py

    tokenization/
      serializers.py
      tokenizer_registry.py
      token_counter.py

    observability/
      event_schema.py
      event_emitter.py
      run_trace.py
      aggregations.py
      reports.py
      dashboard_export.py

    routing/
      effort_modes.py
      request_normalizer.py
      tool_relevance.py
      token_budgeter.py

    compression/
      profiles.yaml
      profile_loader.py
      context.py
      compressor.py
      field_pruning.py
      flattening.py
      list_compaction.py
      deduplication.py
      text_summarization.py
      raw_store.py
      result_cache.py
      envelope.py
      reports.py

    cache/
      policy.yaml
      policy.py
      normalizer.py
      key_builder.py
      redis_store.py
      interceptor.py
      schema_cache.py
      result_cache.py
      bypass.py
      reports.py

    schema_optimizer/
      fetch_schemas.py
      extract_fields.py
      tokenize_schemas.py
      rank_candidates.py
      tool_selector.py
      schema_compactor.py
      expansion_policy.py
      rewrite_rules.py
      validator.py
      reports.py

    benchmarks/
      task_set.py
      runner.py
      evaluators.py
      metrics.py
      report.py
      tasks/
        github_tasks.jsonl
        gmail_tasks.jsonl
        slack_tasks.jsonl
        notion_tasks.jsonl
        mixed_tasks.jsonl

  tests/
    tokenization/
    observability/
    compression/
    cache/
    schema_optimizer/
    benchmarks/
    integration/

  docs/
    architecture.md
    token_attribution.md
    effort_modes.md
    tool_context_budgeting.md
    output_compression.md
    caching.md
    schema_compaction.md
    schema_optimization.md
    dashboard.md
    benchmark_methodology.md
    security_privacy.md
    workbench_boundary.md

  reports/
    raw_token_baseline.md
    compression_report.md
    cache_report.md
    schema_optimization_report.md
    benchmark_report.md
```

---

# 11. Implementation Plan

## Week 1 — Prove the waste and build measurement foundations

Goals:

- wrap a representative Composio tool-loading and tool-execution path
- count schema tokens, result tokens, argument tokens, and retry-context tokens
- log tools exposed vs tools called
- collect sample schemas and outputs
- identify top token-heavy schemas and tools
- build tokenizer/serializer
- create baseline report and basic dashboard table

Deliverables:

- tokenization primitives
- raw output fixtures
- schema fixtures
- run trace schema
- baseline token report
- tools exposed vs tools called report
- basic dashboard export
- integration map

Gate:

> We must show that tool schemas and tool outputs are a measurable part of total context cost.

---

## Week 2 — Schema compaction and effort modes MVP

Goals:

- implement low/medium/high effort mode config
- expose selected tools instead of entire toolkits
- support required-field-only low mode
- support selected-tools-plus-common-fields medium mode
- keep high mode as broad/full-schema baseline
- measure before/after schema token savings

Deliverables:

- effort mode config
- request normalizer
- tool relevance selector
- schema compactor
- schema variant cache
- schema before/after report
- tests for required field preservation and fallback expansion

Gate:

> Schema tokens must drop materially without breaking tool selection or required parameter extraction.

---

## Week 3 — Output compression engine v1

Goals:

- implement result compression profiles
- implement safe/balanced output compression
- add raw references
- preserve IDs, URLs, timestamps, and fields needed for follow-up tool calls
- cache compacted result variants by raw result hash

Deliverables:

- profile loader
- field pruning
- flattening
- list compaction
- raw output store
- result compaction cache
- compression envelope
- tests for GitHub/Gmail/Slack/Notion

Gate:

> Preserved fields must never be removed, and compressed outputs must remain actionable.

---

## Week 4 — Token events, dashboard, and recommendations

Goals:

- integrate token measurement with schema compaction and output compression
- emit savings events
- generate reports
- add token waterfall and top-waste views
- generate recommendation cards for bloated/unused schemas and repeated calls

Deliverables:

- token/compression/schema event schema
- event emitter
- aggregation/reporting
- dashboard export
- compression savings report
- schema savings report
- recommendation report

Gate:

> Every optimized run must report full tokens, exposed tokens, result tokens, and tokens saved by strategy.

---

## Week 5 — Safe repeated-call caching

Goals:

- implement exact-match caching
- add cache policy
- add scoped keys with tenant/account/auth/schema/API/freshness context
- emit cache events
- separate execution cache, schema cache, and result compaction cache metrics

Deliverables:

- cache policy
- key builder
- cache store
- cache interceptor
- bypass support
- cache report

Gate:

> Write/auth tools must be impossible to cache.

---

## Week 6 — Smart routing and schema description optimization

Goals:

- measure schema token costs
- rank tools by relevance, token cost, and usage frequency
- recommend effort mode by route/request type
- optimize top descriptions
- validate behavior
- use small models only for tool ranking, rewrite suggestions, summaries, or expansion suggestions

Deliverables:

- schema tokenizer
- tool relevance ranker
- effort recommendation policy
- rewrite candidate generator
- validator
- schema optimization report

Gate:

> Small-model assistance must never be the sole authority for skipping writes, reusing private data, deciding freshness, or changing tool arguments.

---

## Week 7 — Integration, hardening, and benchmark suite

Goals:

- connect token attribution, effort routing, schema compaction, output compression, caching, and schema optimization
- add end-to-end tests
- prepare demo agent integration
- run raw vs Aperture tasks
- measure savings/performance
- capture failure cases

Deliverables:

- integrated Aperture pipeline
- end-to-end test
- security/privacy checks
- docs
- benchmark tasks
- runner
- evaluators
- metrics

Gate:

> Aperture must work as a coherent layer, and the benchmark must measure both token savings and task quality.

---

## Week 8 — Final report and demo

Goals:

- produce final proof
- polish demo
- write final handoff

Deliverables:

- final benchmark report
- demo script
- final project summary
- follow-up recommendations

Gate:

> Final claims must be measured, not guessed.

---

# 12. Security and Privacy Rules

## 12.1 Token attribution

- Do not store raw sensitive payloads in token events.
- Store token counts, payload sizes, tool IDs, and metadata.
- Respect project/user/session access boundaries.
- Mark approximate token counts when fallback tokenizer is used.

## 12.2 Output compression

- Never remove critical fields.
- Always disclose compression.
- Preserve raw references when omitting significant detail.
- Do not store private raw outputs publicly.
- Support bypass.
- Keep compression auditable.

## 12.3 Caching

- Never cache writes.
- Never cache auth flows.
- Never cache failed responses by default.
- Never use public scope for private data.
- Include account/user scope for private reads.
- Include tenant, account, auth scope, schema version, API version, and freshness policy in execution cache keys.
- Log cache key hashes, not raw keys.
- Report schema cache, result compaction cache, and execution cache separately.

## 12.4 Schema compaction and optimization

- Do not change parameter names/types.
- Do not change required fields.
- Do not remove safety-critical wording without review.
- Keep before/after diffs.
- Low and medium effort modes must support fallback expansion when hidden detail is required.
- Tool relevance recommendations cannot be treated as permission to skip a required tool.

## 12.5 Small-model assistance

- Small models may suggest tool ranking, description rewrites, result summaries, and expansion candidates.
- Small models must not be the sole authority for skipping writes, reusing private data, deciding freshness, or changing tool arguments.

---

# 13. Success Metrics

## 13.1 Token attribution

| Metric | Target |
|---|---:|
| Token count determinism | 100% for same payload/tokenizer |
| Event coverage for compressed outputs | 95%+ |
| Reports by tool/session/toolkit | Yes |
| Raw vs compressed savings visibility | Yes |
| Tools exposed vs tools called visibility | Yes |
| Schema/result/argument/retry token breakdown | Yes |

## 13.2 Effort routing and schema compaction

| Metric | Target |
|---|---:|
| Low/medium/high modes implemented | Yes |
| Required fields preserved | 100% |
| Tool selection preserved on validation tasks | 100% |
| Schema token reduction on common workflows | 50%+ target |
| Fallback expansion logged | Yes |
| Private/cross-account schema cache leakage | 0 |

## 13.3 Output compression

| Metric | Target |
|---|---:|
| High-value tools profiled | 5+ |
| Average token reduction on profiled outputs | 40%+ target |
| Critical field preservation | 100% |
| Raw reference availability when omitting detail | 100% |
| Unknown-tool safe fallback | Yes |
| Result compaction cache scoped correctly | 100% |

## 13.4 Caching

| Metric | Target |
|---|---:|
| Writes cached | 0 |
| Auth flows cached | 0 |
| Cache bypass works | Yes |
| Private cache scope leakage | 0 |
| API calls avoided | Measured |
| Cache hit rate | Measured, no fake target until real traffic |

## 13.5 Schema optimization

| Metric | Target |
|---|---:|
| Top schemas measured | Yes |
| Accepted rewrites validated | 100% |
| Required fields changed | 0 |
| Parameter names changed | 0 |
| Token savings | Measured |

---

# 14. Component E — Semantic Benchmark Suite

## 14.1 Purpose

The benchmark is the final proof layer.

It answers:

1. Did Aperture reduce tokens?
2. Did Aperture avoid repeated API calls?
3. Did Aperture preserve task quality?
4. Did compression cause missing information or extra tool calls?

## 14.2 Benchmark modes

| Mode | Description |
|---|---|
| `raw` | Normal Composio behavior |
| `aperture_low` | Low effort: narrow schema exposure, compact outputs, safe-read cache where allowed |
| `aperture_medium` | Medium effort: selected schemas, balanced result detail, safe cache |
| `aperture_high` | High effort: broader schemas, richer detail, fresh execution preferred for volatile data |
| `aperture_compressed` | Compression enabled |
| `aperture_cached` | Compression + safe cache |
| `aperture_full` | Compression + cache + schema optimization |
| `shadow` | Compress/measure but return raw |

## 14.3 Task categories

Use tasks that naturally create large outputs:

- GitHub issue/PR triage
- Gmail/email thread summarization
- Slack discussion search
- Notion database/page analysis
- mixed workflows across GitHub + Slack + Gmail/Notion

Example tasks:

```text
Find all auth-related GitHub issues and summarize top blockers.
Search Slack for OAuth release decisions and identify owners.
Summarize customer emails about login failures and link them to GitHub issues.
Read a Notion release doc and compare it to open PRs.
Create a release readiness report from GitHub + Slack + docs.
```

## 14.4 Metrics

| Metric | Meaning |
|---|---|
| Raw output tokens | Tokens before compression |
| Compressed output tokens | Tokens after compression |
| Full schema tokens | Tokens in unoptimized loaded schemas |
| Exposed schema tokens | Tokens actually exposed after effort routing/schema compaction |
| Unused schema tokens estimate | Tokens for exposed tools that were not called |
| Argument tokens | Tokens spent on tool arguments |
| Retry-context tokens | Tokens spent on retries/tool errors |
| Tokens saved | Raw minus compressed |
| Compression ratio | Compressed / raw |
| Cache hits | Repeated calls served from cache |
| API calls avoided | External calls skipped |
| Task success rate | Did the agent complete the task? |
| Success delta | Difference from raw baseline |
| Critical omission rate | Did compression remove needed info? |
| Extra tool calls | Did compression cause more retrieval? |
| Raw fallback rate | How often the agent needed raw details? |
| Schema expansion rate | How often low/medium needed more schema detail? |
| Latency | End-to-end task time |

## 14.5 Evaluation methods

Use:

- exact checks for known answers
- field-presence checks for required facts
- trace comparison for tool calls
- LLM judge for qualitative summaries
- human spot checks for final reports
- failure-case review

## 14.6 Benchmark targets

Targets are hypotheses until measured:

| Metric | Target |
|---|---:|
| Output token reduction | 40%+ on profiled tools |
| Schema token reduction | 50%+ on common workflows |
| Task success degradation | <5% absolute drop |
| Critical omission rate | <3% |
| Extra tool-call increase | <10% |
| Raw fallback rate | <15% |
| Schema expansion rate | Measured, no fake target until real traffic |

## 14.7 Final benchmark report

The final report must include:

- tasks run
- tools/toolkits tested
- modes compared
- token savings
- cache savings
- schema savings
- task success comparison
- failure cases
- example raw vs compressed outputs
- recommendation for production mode

## 14.8 Definition of done

Benchmarking is complete when:

- raw and Aperture modes are compared
- savings are measured
- task quality is measured
- failure cases are documented
- final claims are evidence-backed

---

# 15. Final Deliverables

## Code

- token serializer
- tokenizer registry
- token counter
- event schema/emitter
- run trace exporter
- effort mode router
- request normalizer
- tool relevance selector
- token budgeter
- schema compactor
- schema variant cache
- compression profile loader
- output compressor
- result compaction cache
- raw output store
- cache policy loader
- cache key builder
- cache interceptor
- schema optimizer
- benchmark runner/evaluator

## Docs

- architecture
- token attribution
- effort modes
- tool context budgeting
- output compression
- caching
- schema compaction
- schema optimization
- dashboard
- benchmark methodology
- security/privacy
- Workbench boundary

## Reports

- raw token baseline
- schema exposure report
- compression savings
- cache savings
- schema optimization
- final benchmark report

---

# 16. Final Reviewer Summary

Aperture is a token-efficiency layer for Composio agents.

It focuses on:

1. measuring token cost,
2. budgeting tool context through low/medium/high effort modes,
3. compacting schemas before they reach the model,
4. compressing verbose tool outputs,
5. caching safe repeated calls and reusable schema/result variants,
6. optimizing schema descriptions,
7. proving everything with benchmarks.

The main product contribution is developer control over how much tool context a run is allowed to spend. The main technical contributions are schema compaction, schema-aware output compression, and safe repeated-call caching. The main measurement layer is token attribution.

The final proof is the benchmark:

> Same tasks, raw Composio vs Aperture, measured token savings, measured cache savings, measured task quality.
