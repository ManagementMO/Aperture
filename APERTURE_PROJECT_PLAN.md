# Aperture — Updated Execution-Ready Project Plan

## Schema-Aware Tool Output Compression for Composio Agents

**Status:** Updated after Composio engineer feedback  
**Primary project:** Compress/optimize Composio tool outputs before they hit the model  
**Proof system:** Token attribution + semantic benchmark suite  
**Secondary modules:** Safe caching, schema optimization  
**Audience:** Coding agents, research agents, QA agents, reviewer agents, Composio engineers  
**Goal:** Reduce token cost from Composio tool outputs while proving that agent task performance does not significantly degrade.

---

# 0. New Project Direction

The project has shifted from mainly:

> “Measure token cost, cache repeated calls, optimize schemas.”

To a sharper infrastructure project:

> “Measure and compress Composio tool outputs before they enter the model context, then prove token savings against task-performance impact.”

This is stronger because tool outputs are often much larger than tool schemas. They can include verbose nested JSON, repeated URLs, metadata fields, duplicated parent objects, long descriptions, raw HTML/Markdown, avatar URLs, API bookkeeping fields, pagination metadata, and fields irrelevant to the agent’s current task.

Aperture’s core job is now:

1. Observe tool outputs.
2. Measure their token cost.
3. Compress them using schema-aware and task-aware strategies.
4. Return the compressed model-facing version.
5. Preserve the full raw output somewhere safe when needed.
6. Benchmark whether agents still complete tasks correctly.

---

# 1. One-Sentence Summary

Aperture is a schema-aware compression layer for Composio that reduces the token cost of tool outputs before they reach the model, while benchmarking token savings against agent task performance.

---

# 2. Best Technical Summary

Aperture intercepts Composio tool outputs, measures their token contribution, transforms verbose raw API responses into compact model-facing payloads using deterministic rules and optional lightweight LLM summarization, and evaluates the result with a semantic benchmark comparing agents on the same tasks with and without compression.

---

# 3. Why This Is the Stronger Project

## 3.1 Tool outputs are often the biggest token sink

Tool schemas cost tokens, but tool outputs can be much worse. A single call like “list GitHub issues,” “search Gmail,” “query Notion database,” or “search Slack messages” may return dozens of objects with deeply nested fields.

Many returned fields are not useful for the model’s immediate reasoning:

- Internal IDs
- API URLs
- Repeated parent objects
- Avatar URLs
- HTML URLs repeated across objects
- Empty fields
- Raw markdown bodies
- Metadata the agent never uses
- Pagination details
- Permission objects
- Duplicated user objects
- Nested links

Aperture compresses these before the model sees them.

## 3.2 This is clearly different from Workbench

Workbench can store or process large outputs outside the model context.

Aperture is different:

> Workbench is where large outputs can live. Aperture decides what compact, task-useful representation of those outputs should be shown to the model.

Workbench reduces context by moving data out of context. Aperture reduces context by transforming the model-facing payload itself.

They can work together:

```text
Raw tool output
   ↓
Store raw output in Workbench / object store if large
   ↓
Aperture creates compact model-facing output
   ↓
Model receives only useful compressed representation
   ↓
Model can request raw/details later if needed
```

## 3.3 This gives a clean benchmark story

The benchmark is simple and compelling:

> Run the same 100 tasks with normal Composio outputs and with Aperture-compressed outputs. Compare token savings, latency, task success, tool correctness, and answer quality.

The two questions every reviewer will ask:

1. How many tokens did you save?
2. Did the agent get worse?

Aperture is designed to answer both.

---

# 4. MVP Scope

## 4.1 In scope

| Component | MVP behavior |
|---|---|
| Token attribution | Count tokens before and after compression |
| Output compression | Compress selected tool outputs before model sees them |
| Schema-aware field pruning | Remove low-value/repeated fields based on known output shape |
| Task-aware compaction | Keep fields relevant to the user’s task/tool intent |
| Optional lightweight summarization | Use cheap LLM only for fields that cannot be compressed by rules |
| Raw output preservation | Keep full raw output accessible by reference when needed |
| Benchmark suite | Run same tasks with/without compression |
| Performance validation | Measure task success and degradation |
| Reports | Token savings, compression ratios, task success deltas |

## 4.2 Secondary / optional MVP features

| Component | Status |
|---|---|
| Safe repeated-call caching | Useful but secondary |
| Schema description optimization | Useful but secondary |
| Semantic SEARCH_TOOLS caching | Follow-on |
| Session state compression | Follow-on |
| Plan quality scoring | Follow-on |

## 4.3 Out of scope for MVP

- Arbitrary semantic caching of tool execution results
- Automatic full conversation-history compression
- Total LLM provider bill attribution
- Rewriting every Composio schema
- Compressing every toolkit on day one
- Removing fields without validation or fallback
- Cross-user private data sharing

---

# 5. Core Product Thesis

Agents do not need raw API responses. They need compact, relevant representations that preserve enough information to complete the task.

Aperture should transform this:

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
    "gravatar_id": "",
    "url": "https://api.github.com/users/nikos",
    "html_url": "https://github.com/nikos",
    "followers_url": "...",
    "following_url": "...",
    "gists_url": "...",
    "starred_url": "...",
    "subscriptions_url": "...",
    "organizations_url": "...",
    "repos_url": "...",
    "events_url": "...",
    "received_events_url": "...",
    "type": "User",
    "site_admin": false
  },
  "labels": [
    {
      "id": 1,
      "node_id": "LA_kwDOExample",
      "url": "https://api.github.com/repos/acme/app/labels/bug",
      "name": "bug",
      "color": "d73a4a",
      "default": true,
      "description": "Something is not working"
    }
  ],
  "comments": 4,
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-03T12:00:00Z",
  "closed_at": null
}
```

Into this:

```json
{
  "number": 42,
  "state": "open",
  "title": "Login fails after OAuth redirect",
  "author": "nikos",
  "labels": ["bug"],
  "comments": 4,
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-03T12:00:00Z",
  "summary": "OAuth login redirects but user remains unauthenticated.",
  "url": "https://github.com/acme/app/issues/42"
}
```

The compressed payload is smaller, easier for the model to reason over, and usually more useful.

---

# 6. Main System Architecture

## 6.1 Normal Composio flow

```text
Agent calls Composio tool
        ↓
Composio executes external API/tool
        ↓
Raw tool output returned to model
        ↓
Raw output enters LLM context
```

## 6.2 Aperture-enhanced flow

```text
Agent calls Composio tool
        ↓
Composio executes external API/tool
        ↓
Aperture intercepts raw output
        ↓
Token count raw output
        ↓
Classify output/tool/task
        ↓
Apply compression strategy
        ↓
Token count compressed output
        ↓
Store raw output reference if needed
        ↓
Return compressed output to model
        ↓
Emit token savings + quality metadata
```

## 6.3 Workbench-compatible flow

```text
Large raw output
        ↓
Store raw output in Workbench/object store
        ↓
Return compact model-facing representation:
  - summary
  - key fields
  - row/object count
  - raw_reference_id
  - instruction for retrieving details if needed
```

Example compressed return:

```json
{
  "aperture_compressed": true,
  "raw_reference_id": "wrk_abc123/issues_raw.json",
  "item_count": 50,
  "items": [
    {
      "number": 42,
      "title": "Login fails after OAuth redirect",
      "state": "open",
      "labels": ["bug"],
      "summary": "OAuth redirect does not persist auth session."
    }
  ],
  "compression": {
    "raw_tokens": 18420,
    "compressed_tokens": 3120,
    "tokens_saved": 15300,
    "compression_ratio": 0.169
  }
}
```

---

# 7. Core Components

## Component A — Token Attribution

Measures raw and compressed token counts.

## Component B — Schema-Aware Output Compression

The main project contribution. Transforms raw tool outputs into compact model-facing payloads.

## Component C — Semantic Benchmark Suite

Runs the same tasks with and without compression and measures savings/performance.

## Component D — Safe Repeated-Call Caching

Optional/secondary. Caches approved safe read-only calls.

## Component E — Schema Description Optimization

Optional/secondary. Optimizes tool input schemas/descriptions.

---

# 8. Component A — Token Attribution

## 8.1 Purpose

Measure the cost of tool outputs before and after compression.

## 8.2 What it measures

- Raw output tokens
- Compressed output tokens
- Tokens saved
- Compression ratio
- Payload byte size before/after
- Tool-level and session-level savings
- Savings by compression strategy

## 8.3 Event schema

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class OutputCompressionEvent:
    event_type: str                 # "tool_output_compression"
    timestamp: str
    project_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    connected_account_id: Optional[str]
    toolkit_slug: Optional[str]
    tool_slug: str
    model: Optional[str]
    raw_payload_bytes: int
    compressed_payload_bytes: int
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    compression_strategy: str       # rule_based/schema_aware/llm_summary/hybrid/none
    quality_mode: str               # benchmark/live/shadow
    raw_reference_id: Optional[str]
    compression_applied: bool
    bypassed: bool
    bypass_reason: Optional[str]
    aperture_version: str
```

## 8.4 Token counting rules

- Count the exact raw payload that would have gone to the model.
- Count the exact compressed payload that actually goes to the model.
- If raw output is stored elsewhere, still count the original raw output for savings comparison.
- Unknown tokenizer must use safe fallback and mark approximation.

## 8.5 Public functions

```python
def count_tokens_for_payload(payload: object, model: str | None = None) -> TokenCount:
    """Return token count, tokenizer name, byte size, and approximation flag."""


def emit_output_compression_event(event: OutputCompressionEvent) -> None:
    """Write compression/savings event to configured event sink."""
```

## 8.6 Definition of done

- Raw and compressed token counts are captured for every compressed output.
- Savings are queryable by tool, toolkit, session, user, and strategy.
- Token counts are deterministic for same payload/tokenizer.
- Reports separate measured savings from estimates.

---

# 9. Component B — Schema-Aware Output Compression

## 9.1 Purpose

Compress tool outputs before they reach the model while preserving the information needed for task success.

## 9.2 Compression principles

1. Preserve task-critical information.
2. Drop redundant API bookkeeping.
3. Collapse repeated nested objects.
4. Summarize long text only when needed.
5. Keep references to raw output.
6. Make compression reversible or inspectable.
7. Prefer deterministic rules before LLM summarization.
8. Use cheap LLM calls only when rules cannot preserve meaning.
9. Never hide that compression occurred.
10. Always benchmark performance impact.

## 9.3 Compression strategies

### Strategy 1 — Field pruning

Remove low-value fields.

Common removable fields:

- `node_id`
- `avatar_url`
- `gravatar_id`
- `followers_url`
- `following_url`
- `gists_url`
- `starred_url`
- `subscriptions_url`
- `organizations_url`
- `repos_url`
- `events_url`
- `received_events_url`
- `labels_url`
- `comments_url`
- `events_url`
- Empty/null fields
- Internal API URLs if `html_url` exists

### Strategy 2 — Nested object flattening

Before:

```json
{
  "user": {
    "login": "nikos",
    "id": 123,
    "avatar_url": "...",
    "html_url": "...",
    "type": "User"
  }
}
```

After:

```json
{
  "author": "nikos"
}
```

### Strategy 3 — List compaction

Before:

```json
"labels": [
  {"id": 1, "name": "bug", "color": "red", "url": "..."},
  {"id": 2, "name": "urgent", "color": "orange", "url": "..."}
]
```

After:

```json
"labels": ["bug", "urgent"]
```

### Strategy 4 — Long text summarization

For long fields like:

- GitHub issue body
- Slack thread body
- Gmail email body
- Notion page content
- Raw webpage content

Aperture can summarize with:

- deterministic truncation first
- extractive compression second
- cheap LLM summarization third

Example:

```json
{
  "body_summary": "User reports OAuth redirect succeeds but session cookie is not set.",
  "body_truncated": false,
  "raw_body_reference": "wrk_abc123/body_42.md"
}
```

### Strategy 5 — Table/row projection

For database/list outputs, keep only relevant columns.

Before: 30 fields per row.

After: 5–8 task-relevant fields per row.

### Strategy 6 — Deduplication

If the same user/repo/channel object appears 50 times, replace repeated objects with compact IDs or names.

Before:

```json
{
  "items": [
    {"repo": {"name": "app", "owner": {...many fields...}}, "title": "A"},
    {"repo": {"name": "app", "owner": {...many fields...}}, "title": "B"}
  ]
}
```

After:

```json
{
  "repo": "acme/app",
  "items": [
    {"title": "A"},
    {"title": "B"}
  ]
}
```

### Strategy 7 — Result envelope compression

Add a standardized envelope so the model knows what happened.

```json
{
  "aperture_compressed": true,
  "tool_slug": "GITHUB_LIST_ISSUES",
  "summary": "Returned 50 open issues for acme/app.",
  "items": [...],
  "omitted_fields": ["node_id", "avatar_url", "api_urls", "empty_fields"],
  "raw_reference_id": "wrk_abc123/raw.json"
}
```

## 9.4 Compression mode levels

| Mode | Description | Risk |
|---|---|---:|
| `off` | Return raw output | None |
| `safe` | Drop obvious metadata/nulls/API URLs only | Low |
| `balanced` | Safe + flatten nested objects + compact lists | Medium-low |
| `aggressive` | Balanced + summarize long text + project rows | Medium |
| `benchmark_only` | Run compression in shadow, but return raw | None to user |

MVP should start with:

- `benchmark_only`
- `safe`
- `balanced`

Do not use `aggressive` in production until benchmarked.

## 9.5 Tool-specific compression profiles

Each tool/toolkit can define an output compression profile.

Example:

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
      strategy: cheap_llm_or_extractive
  drop_fields:
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

Another example:

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
    - label_ids_verbose
  raw_reference: true
```

## 9.6 Generic fallback compression profile

For unknown tools:

```yaml
UNKNOWN_DEFAULT:
  mode: safe
  drop_nulls: true
  drop_empty_strings: true
  drop_empty_arrays: true
  drop_obvious_api_urls: true
  max_string_tokens_without_summary: 300
  raw_reference: true
```

Unknown tools should not use aggressive compression.

## 9.7 Compression pipeline

```text
Input: raw tool output, tool_slug, toolkit_slug, user task context

1. Load compression profile.
2. If mode is off: return raw.
3. Count raw tokens.
4. Store raw output if profile requires reference.
5. Apply deterministic compression:
   a. remove null/empty fields
   b. drop configured fields
   c. flatten configured nested objects
   d. compact configured lists
   e. project row fields
   f. deduplicate repeated objects
6. Detect long text fields.
7. Apply summarization if allowed.
8. Build compressed envelope.
9. Count compressed tokens.
10. Emit compression event.
11. Return compressed payload.
```

## 9.8 Public interfaces

```python
@dataclass(frozen=True)
class CompressionContext:
    project_id: str
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
    raw_payload: object
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
    """Compress a tool output according to tool-specific or generic policy."""
```

## 9.9 Required tests

### Unit tests

- Null fields are removed in safe mode.
- Configured drop fields are removed.
- Preserve fields remain present.
- Nested user object is flattened correctly.
- Label list is compacted correctly.
- Raw reference is included when enabled.
- Compressed payload token count is lower than raw for known fixtures.

### Safety tests

- Required preserved fields are not dropped.
- Unknown tools use safe mode only.
- Private payload is not stored in public location.
- Raw reference ID does not expose sensitive content.
- Summarization can be disabled.

### Regression tests

- GitHub issue fixture compresses as expected.
- Gmail search fixture compresses as expected.
- Slack thread fixture compresses as expected.
- Notion database fixture compresses as expected.

## 9.10 Definition of done

This component is done when:

- At least 5 high-value tools have compression profiles.
- Generic safe fallback exists for unknown tools.
- Raw and compressed token counts are emitted.
- Raw output can be referenced when compression omits details.
- Unit and safety tests pass.
- Benchmark suite proves acceptable performance impact.

---

# 10. Component C — Semantic Benchmark Suite

## 10.1 Purpose

Prove that compression saves tokens without meaningfully hurting agent performance.

This is the centerpiece of the evaluation.

## 10.2 Benchmark question

For the same task set:

```text
Does the agent still complete the task correctly when tool outputs are compressed?
```

And:

```text
How many tokens are saved?
```

## 10.3 Benchmark design

Run N tasks in two or more modes:

| Mode | Description |
|---|---|
| `raw` | Normal Composio output |
| `safe_compressed` | Safe metadata/null/API URL pruning |
| `balanced_compressed` | Safe + flattening + list compaction + limited summarization |
| `shadow` | Compress and measure, but return raw to model |

## 10.4 Benchmark task categories

At least 100 tasks total across:

### GitHub

- List repo issues and identify top bugs
- Find issue by title/label
- Summarize recent PRs
- Compare issue comments
- Create a short triage report

### Gmail

- Find emails from a person
- Summarize recent thread
- Identify action items
- Extract dates/deadlines
- Draft reply based on retrieved emails

### Slack

- Search for discussion around topic
- Summarize thread
- Identify owner/decision
- Extract blockers

### Notion

- Query database rows
- Summarize page content
- Extract project status
- Find matching tasks

### Calendar

- Find next available time
- Summarize events this week
- Identify conflicts

### Mixed workflows

- Search email, then create GitHub issue
- Search Slack, then summarize in Notion
- Query GitHub issues, then draft email update

## 10.5 Benchmark metrics

### Token metrics

- Raw output tokens
- Compressed output tokens
- Tokens saved
- Compression ratio
- Tokens saved per task
- Tokens saved per tool

### Performance metrics

- Task success rate
- Tool selection accuracy
- Parameter extraction accuracy
- Final answer quality
- Missing critical information rate
- Number of follow-up tool calls caused by compression
- Latency
- LLM calls per task

### Degradation metrics

- Success delta vs raw baseline
- Extra turns caused by compression
- Incorrect answer count
- User-critical omission count
- Need-to-fetch-raw count

## 10.6 Evaluation methods

Use multiple evaluation types:

1. **Exact checks**  
   For tasks with known expected outputs.

2. **LLM judge**  
   For summaries and qualitative answers.

3. **Human spot check**  
   For a small subset of tasks.

4. **Tool trace comparison**  
   Compare tool calls and final artifacts.

5. **Raw fallback count**  
   How often the agent needed the full raw output after compression.

## 10.7 Benchmark result target

Initial success target:

| Metric | Target |
|---|---:|
| Average output token reduction | 40%+ on selected tools |
| Task success degradation | Less than 5% absolute drop |
| Critical omission rate | Less than 3% |
| Extra tool calls due to compression | Less than 10% increase |
| Raw fallback needed | Less than 15% of tasks |

These targets are hypotheses. The final report must show measured values.

## 10.8 Benchmark report format

```md
# Aperture Benchmark Report

## Summary
- Tasks run: 100
- Toolkits tested: GitHub, Gmail, Slack, Notion, Calendar
- Modes: raw, safe_compressed, balanced_compressed

## Token Savings
| Mode | Raw tokens | Output tokens | Tokens saved | Reduction |
|---|---:|---:|---:|---:|

## Task Performance
| Mode | Success rate | Δ vs raw | Extra turns | Raw fallback rate |
|---|---:|---:|---:|---:|

## Tool-Level Results
| Tool | Avg raw tokens | Avg compressed tokens | Reduction | Success delta |
|---|---:|---:|---:|---:|

## Failure Cases
- ...

## Example Transformations
- Raw GitHub issue output → compressed output
- Raw Gmail thread output → compressed output

## Conclusion
- Where compression works
- Where it fails
- Recommended production mode
```

## 10.9 Definition of done

Benchmarking is done when:

- At least 100 tasks are run or a smaller number is clearly justified.
- Raw and compressed modes are compared.
- Token savings are measured.
- Performance degradation is measured.
- Example compressed outputs are shown.
- Failure cases are included honestly.

---

# 11. Secondary Component D — Safe Repeated-Call Caching

## 11.1 Role in new plan

Caching is still useful, but it is no longer the main technical story.

It supports Aperture by avoiding duplicate execution of approved safe reads.

## 11.2 MVP caching scope

- Exact-match only
- Redis or in-memory test store
- Approved read-only tools only
- No writes
- No auth operations
- User/account scoped for private data
- TTL-based
- Bypassable

## 11.3 When caching helps

Caching helps when the same tool call repeats across benchmark tasks or sessions.

Compression helps even on first call. That is why compression is primary.

## 11.4 Definition of done

- Cache hit avoids tool execution.
- Cache events show API calls avoided.
- Writes/auth tools are impossible to cache.
- Private reads are scoped.

---

# 12. Secondary Component E — Schema Description Optimization

## 12.1 Role in new plan

Schema optimization is now a secondary win, not the main project.

It reduces the cost of tool discovery/schema exposure, while output compression reduces the cost of tool results.

## 12.2 MVP schema optimization scope

- Measure token cost of tool descriptions.
- Optimize top 25 descriptions if time allows.
- Validate tool selection and parameter behavior.
- Produce before/after report.

## 12.3 Correct framing

Composio already has some schema simplification and schema modifier capabilities. Aperture’s contribution is measured tokenizer-aware optimization with validation.

---

# 13. Repository Structure

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
      __init__.py
      serializers.py
      token_counter.py
      tokenizer_registry.py

    compression/
      __init__.py
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
      envelope.py
      reports.py

    observability/
      __init__.py
      event_schema.py
      event_emitter.py
      aggregations.py
      reports.py

    benchmarks/
      __init__.py
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
        calendar_tasks.jsonl
        mixed_tasks.jsonl

    cache/
      __init__.py
      policy.yaml
      policy.py
      normalizer.py
      key_builder.py
      redis_store.py
      interceptor.py

    schema_optimizer/
      __init__.py
      fetch_schemas.py
      extract_fields.py
      tokenize_schemas.py
      rewrite_rules.py
      validator.py
      reports.py

  tests/
    tokenization/
    compression/
    observability/
    benchmarks/
    cache/
    schema_optimizer/
    integration/

  docs/
    architecture.md
    output_compression.md
    compression_profiles.md
    benchmark_methodology.md
    token_attribution.md
    workbench_boundary.md
    security_privacy.md
    follow_on_roadmap.md

  reports/
    .gitkeep
```

---

# 14. Compression Profiles

## 14.1 Profile format

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

## 14.2 GitHub issue list profile

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
      strategy: extractive_or_cheap_llm
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
    - milestone.url
    - milestone.node_id
  raw_reference: true
```

## 14.3 Gmail search profile

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

## 14.4 Slack search profile

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

## 14.5 Notion database profile

```yaml
NOTION_QUERY_DATABASE:
  mode: balanced
  preserve_fields:
    - id
    - url
    - created_time
    - last_edited_time
    - title
    - status
    - owner
    - due_date
  drop_fields:
    - object
    - parent
    - archived
    - icon
    - cover
    - created_by
    - last_edited_by
  raw_reference: true
```

---

# 15. Coding Agent Task Cards

## Task A1 — Tokenization primitives

### Goal

Build stable serialization and token counting for raw/compressed payloads.

### Files

- `aperture/tokenization/serializers.py`
- `aperture/tokenization/token_counter.py`
- `aperture/tokenization/tokenizer_registry.py`
- `tests/tokenization/*`

### Requirements

- Deterministic serialization
- Tokenizer selection by model
- Safe fallback
- Byte-size measurement
- No payload mutation

### Definition of done

Same payload always gives same token count and byte size.

---

## Task B1 — Compression profile loader

### Goal

Load and validate tool-specific compression profiles.

### Files

- `aperture/compression/profiles.yaml`
- `aperture/compression/profile_loader.py`
- `tests/compression/test_profile_loader.py`

### Requirements

- Unknown tools use default safe profile.
- Invalid profile fails clearly.
- Preserve/drop/summarize config is parsed.
- Mode is one of off/safe/balanced/aggressive/benchmark_only.

### Definition of done

Profiles load correctly and unknown tools are safe by default.

---

## Task B2 — Field pruning and null cleanup

### Goal

Implement safe removal of nulls, empty values, configured drop fields, and obvious API metadata.

### Files

- `aperture/compression/field_pruning.py`
- `tests/compression/test_field_pruning.py`

### Requirements

- Remove configured fields by path.
- Remove nulls if enabled.
- Remove empty strings/arrays if enabled.
- Preserve configured fields.
- Never remove preserved fields.

### Definition of done

Safe compression reduces fixture payload size without removing preserve fields.

---

## Task B3 — Flattening and list compaction

### Goal

Compress nested objects and lists using profile rules.

### Files

- `aperture/compression/flattening.py`
- `aperture/compression/list_compaction.py`
- `tests/compression/test_flattening.py`
- `tests/compression/test_list_compaction.py`

### Requirements

- `user.login -> author`
- `labels[].name -> labels: [names]`
- Preserve fallback if path missing.
- Handle list/dict outputs.

### Definition of done

GitHub/Gmail/Slack fixtures compact correctly.

---

## Task B4 — Raw output store

### Goal

Store raw outputs and return safe reference IDs.

### Files

- `aperture/compression/raw_store.py`
- `tests/compression/test_raw_store.py`

### Requirements

- Store raw payload in configurable backend.
- Test backend can be in-memory/file-based.
- Return opaque reference ID.
- Do not expose sensitive content in reference ID.

### Definition of done

Compressed payload can include reference to raw output.

---

## Task B5 — Text summarization module

### Goal

Compress long text fields safely.

### Files

- `aperture/compression/text_summarization.py`
- `tests/compression/test_text_summarization.py`

### Requirements

- Support no-summary mode.
- Support truncation/extractive strategy.
- Optional cheap LLM strategy behind config.
- Include summary metadata.
- Preserve raw reference.

### Definition of done

Long text fields are shortened only when allowed by profile.

---

## Task B6 — Main compressor

### Goal

Combine all compression steps into `compress_tool_output`.

### Files

- `aperture/compression/context.py`
- `aperture/compression/compressor.py`
- `aperture/compression/envelope.py`
- `tests/compression/test_compressor.py`

### Requirements

- Load profile.
- Count raw tokens.
- Store raw if needed.
- Apply pruning/flattening/list compaction/summarization.
- Build envelope.
- Count compressed tokens.
- Emit result object.

### Definition of done

End-to-end compression works on selected fixtures.

---

## Task C1 — Compression event emitter

### Goal

Emit raw/compressed token savings events.

### Files

- `aperture/observability/event_schema.py`
- `aperture/observability/event_emitter.py`
- `tests/observability/test_compression_events.py`

### Requirements

- Event includes raw/compressed tokens.
- Event includes strategy and tool slug.
- Event includes bypass/compression status.
- No raw payload stored.

### Definition of done

Compression emits queryable savings events.

---

## Task D1 — Benchmark task set

### Goal

Create benchmark tasks for raw vs compressed comparison.

### Files

- `aperture/benchmarks/tasks/*.jsonl`
- `aperture/benchmarks/task_set.py`

### Requirements

Each task includes:

```json
{
  "task_id": "github_001",
  "category": "github",
  "user_prompt": "Summarize the top open bugs in this repo.",
  "tools_allowed": ["GITHUB_LIST_ISSUES"],
  "expected_behavior": "Agent identifies open bug issues and summarizes them.",
  "evaluation_type": "llm_judge_or_exact",
  "critical_fields": ["title", "state", "labels", "body"]
}
```

### Definition of done

At least 100 benchmark tasks exist or a smaller validated set is justified.

---

## Task D2 — Benchmark runner

### Goal

Run tasks with raw and compressed outputs and collect metrics.

### Files

- `aperture/benchmarks/runner.py`
- `aperture/benchmarks/metrics.py`
- `tests/benchmarks/test_runner.py`

### Requirements

- Modes: raw, safe_compressed, balanced_compressed, shadow.
- Capture token metrics.
- Capture success metrics.
- Capture extra turns/tool calls.
- Produce JSON output.

### Definition of done

Runner compares raw vs compressed modes on test workflows.

---

## Task D3 — Benchmark evaluators

### Goal

Evaluate task success.

### Files

- `aperture/benchmarks/evaluators.py`
- `tests/benchmarks/test_evaluators.py`

### Requirements

- Exact evaluator
- Field-presence evaluator
- LLM-judge evaluator stub/config
- Human-review export format

### Definition of done

Benchmark can measure correctness beyond token savings.

---

## Task D4 — Final benchmark report

### Goal

Generate final report showing token savings and performance impact.

### Files

- `aperture/benchmarks/report.py`
- `reports/aperture_output_compression_benchmark.md`

### Requirements

- Include measured savings.
- Include performance deltas.
- Include example transformations.
- Include failure cases.
- Include recommendation for production mode.

### Definition of done

Report answers: “How many tokens saved?” and “Did performance degrade?”

---

# 16. Multi-Agent Work Breakdown

## 16.1 Recommended agents

| Agent | Mission | Primary output |
|---|---|---|
| Architecture Agent | Find Composio hook points and Workbench boundary | `docs/integration_map.md` |
| Tokenization Agent | Build serializer/token counter | `tokenization/*` |
| Compression Agent | Build compression engine/profiles | `compression/*` |
| Observability Agent | Build events/aggregations/reports | `observability/*` |
| Benchmark Agent | Build task set/runner/evaluators | `benchmarks/*` |
| QA Agent | Build safety/regression tests | `tests/*` |
| Docs Agent | Write technical docs and final report | `docs/*`, `reports/*` |
| Review Agent | Check privacy/security/performance claims | Review notes |

## 16.2 Parallel plan

### Can start immediately

- Tokenization primitives
- Compression profile format
- Fixture creation from example outputs
- Benchmark task design
- Docs around Workbench boundary

### Needs Composio internals

- Runtime hook into tool outputs
- Raw output storage decision
- Live event sink
- Real benchmark execution on Composio sessions

### Can be simulated if internal access is limited

- Use captured/sample tool outputs
- Run compression offline
- Build benchmark harness with mocked tool outputs
- Produce proof-of-concept report

---

# 17. Implementation Timeline

## Week 1 — Ground truth and output fixtures

### Goals

- Collect real or realistic tool outputs.
- Identify verbose fields.
- Build token-counting baseline.

### Deliverables

- `docs/integration_map.md`
- Raw output fixtures for GitHub/Gmail/Slack/Notion/Calendar
- Tokenization primitives
- Baseline raw token report

### Gate

Must identify top output types by token cost before building aggressive compression.

---

## Week 2 — Compression engine v1

### Goals

- Implement safe and balanced compression.
- Create tool-specific profiles for top outputs.

### Deliverables

- Profile loader
- Field pruning
- Flattening
- List compaction
- Raw store
- Compression envelope
- Unit tests

### Gate

Compression must preserve critical fields in fixtures.

---

## Week 3 — Observability and integration

### Goals

- Emit raw/compressed token events.
- Hook compressor into tool output path or simulated wrapper.

### Deliverables

- Compression event schema
- Event emitter
- Aggregation/reporting
- Integration test with simulated tool call

### Gate

Every compressed output must produce raw/compressed token counts.

---

## Week 4 — Benchmark suite v1

### Goals

- Build task set and runner.
- Run raw vs compressed comparisons.

### Deliverables

- 50–100 benchmark tasks
- Raw/safe/balanced run modes
- Evaluators
- First benchmark report

### Gate

Benchmark must measure both savings and task success.

---

## Week 5 — Compression refinement

### Goals

- Use benchmark failures to improve compression profiles.
- Add optional long-text summarization.

### Deliverables

- Improved profiles
- Text summarization module
- Failure-case fixes
- Updated benchmark report

### Gate

Performance degradation must be within acceptable range or compression mode must be downgraded.

---

## Week 6 — Secondary modules

### Goals

- Add safe repeated-call caching if time allows.
- Add schema description optimization if time allows.

### Deliverables

- Cache MVP or schema optimizer MVP
- Separate measured report

### Gate

Secondary modules must not distract from output compression benchmark.

---

## Week 7 — Hardening and docs

### Goals

- Make project production-readable.
- Finish safety/privacy docs.

### Deliverables

- Security/privacy checklist
- Workbench boundary doc
- Compression profiles doc
- Test coverage improvements

---

## Week 8 — Final demo and report

### Goals

- Show clear before/after demo.
- Present quantified savings and performance impact.

### Deliverables

- Final benchmark report
- Final demo
- Final project handoff
- Follow-on roadmap

---

# 18. Success Metrics

## 18.1 Primary metrics

| Metric | Target |
|---|---:|
| Average output token reduction on selected tools | 40%+ |
| Task success degradation vs raw | < 5% absolute drop |
| Critical information omission rate | < 3% |
| Compression event coverage | 95%+ of compressed outputs |
| Raw reference availability | 100% when fields are omitted |
| Benchmark tasks completed | 100 or justified smaller set |

## 18.2 Secondary metrics

| Metric | Target |
|---|---:|
| Latency overhead from rule compression | Minimal / measured |
| Extra tool calls caused by compression | < 10% increase |
| Raw fallback rate | < 15% |
| Average compression ratio by toolkit | Measured |
| Token savings by strategy | Measured |

## 18.3 Anti-metrics

Do not optimize for:

- Maximum compression ratio regardless of correctness
- Flashy demos with cherry-picked tasks
- Removing fields without fallback
- LLM summarization everywhere
- Unmeasured savings claims

---

# 19. Security and Privacy Rules

## 19.1 Compression safety

1. Never remove fields marked critical by profile.
2. Never hide that output was compressed.
3. Always include raw reference when significant content is omitted.
4. Do not store raw private data in public/shared storage.
5. Do not expose raw reference IDs that reveal content.
6. Do not use LLM summarization on sensitive private data unless allowed by config.
7. Allow compression bypass.
8. Preserve enough provenance for audit.

## 19.2 Event safety

1. Store token counts and sizes, not raw payloads.
2. Store omitted field names only if safe.
3. Hash IDs where appropriate.
4. Respect user/project/session boundaries.

## 19.3 Benchmark safety

1. Use synthetic or approved fixtures if real data is sensitive.
2. Redact private data from reports.
3. Do not publish raw private outputs.

---

# 20. Quality Gates

## Gate 1 — Token measurement

Pass if:

- Raw and compressed token counts are deterministic.
- Same payload produces same count.
- Events include required metadata.

## Gate 2 — Compression correctness

Pass if:

- Preserve fields remain.
- Critical fields remain.
- Unknown tools use safe mode.
- Raw reference exists when needed.

## Gate 3 — Benchmark performance

Pass if:

- Success degradation is measured.
- Failure cases are documented.
- Compression mode recommendation is justified.

## Gate 4 — Workbench distinction

Pass if:

- Docs clearly explain difference from Workbench.
- Raw output storage/retrieval path is defined.
- Model-facing payload optimization is demonstrated.

---

# 21. Perfect Coding-Agent Prompt

Use this when assigning tasks:

```md
You are working on Aperture, a schema-aware tool output compression layer for Composio agents.

Core goal:
Compress verbose Composio tool outputs before they reach the model, measure token savings, and prove through benchmarks that task performance does not significantly degrade.

Rules:
- Be conservative and safety-first.
- Never remove profile-preserved critical fields.
- Never hide that compression occurred.
- Always support raw output reference when content is omitted.
- Do not store raw sensitive payloads in observability events.
- Prefer deterministic compression before LLM summarization.
- Use cheap/optional LLM summarization only when configured.
- Add tests for every module.
- End with a handoff: completed, files changed, tests run, assumptions, unknowns, next task.

Your task:
[INSERT TASK CARD]

Relevant contracts:
[INSERT INTERFACES]

Definition of done:
[INSERT DEFINITION OF DONE]
```

---

# 22. Final Deliverables

## Code deliverables

- Tokenization primitives
- Compression profile loader
- Field pruning engine
- Flattening engine
- List compaction engine
- Deduplication engine
- Long-text summarization module
- Raw output store
- Compression envelope builder
- Compression event emitter
- Benchmark task set
- Benchmark runner
- Benchmark evaluators
- Benchmark report generator
- Optional cache MVP
- Optional schema optimizer MVP

## Docs deliverables

```text
docs/architecture.md
docs/integration_map.md
docs/output_compression.md
docs/compression_profiles.md
docs/workbench_boundary.md
docs/token_attribution.md
docs/benchmark_methodology.md
docs/security_privacy.md
docs/follow_on_roadmap.md
```

## Reports deliverables

```text
reports/raw_output_token_baseline.md
reports/compression_profile_examples.md
reports/aperture_output_compression_benchmark.md
reports/failure_cases.md
reports/final_handoff.md
```

---

# 23. Final Demo Structure

## Demo 1 — Raw vs compressed output

Show a verbose GitHub/Gmail/Slack output and the compressed Aperture version.

## Demo 2 — Token savings

Show raw tokens, compressed tokens, and tokens saved.

## Demo 3 — Agent task benchmark

Show the same task completed with raw output and compressed output.

## Demo 4 — Failure case honesty

Show a case where aggressive compression removed too much, then show how the benchmark caught it and the profile was fixed.

## Demo 5 — Workbench distinction

Show raw output stored in Workbench/object store while model receives compact representation.

---

# 24. Follow-On Roadmap

## Phase 2 — Adaptive task-aware compression

Use the user’s task intent to decide which fields matter.

Example:

- For “summarize bugs,” keep title/body/labels/comments.
- For “count issues by state,” keep state only.
- For “find who owns this,” keep author/assignee/team fields.

## Phase 3 — Retrieval from raw reference

Allow model to request omitted details:

```json
{
  "tool": "APERTURE_GET_RAW_FIELD",
  "raw_reference_id": "wrk_abc123/raw.json",
  "field_path": "items[4].body"
}
```

## Phase 4 — Continuous learned compression profiles

Learn which fields agents actually use and update profiles over time.

## Phase 5 — Safe caching

Add or expand exact-match caching for safe repeated read calls.

## Phase 6 — Schema description optimization

Optimize input/tool schemas after output compression is proven.

---

# 25. Final Reviewer Summary

Aperture is now best understood as:

> A schema-aware output compression and benchmarking system for Composio agents.

It solves a concrete problem: tool outputs can be huge, verbose, and full of fields the model does not need. Aperture compresses those outputs before they hit the model, tracks token savings, preserves raw output access, and benchmarks whether the agent still performs well.

The strongest proof is not a claim. It is the benchmark:

> Same 100 tasks, raw outputs vs compressed outputs, measured token savings and measured task-performance delta.

This is the project’s main story.

