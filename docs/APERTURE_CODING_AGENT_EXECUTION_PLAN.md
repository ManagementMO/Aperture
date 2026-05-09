# APERTURE_CODING_AGENT_EXECUTION_PLAN.md

# Aperture — Coding Agent Execution Plan

## Token Attribution, Schema-Aware Output Compression, Safe Caching, and Schema Optimization for Composio Agents

---

## 0. Purpose of This Document

This document is the **execution spec** for coding agents building Aperture.

It is intentionally more practical than a normal project plan. It tells agents:

- what to build
- where to put files
- what interfaces to implement
- what tests to write
- what safety rules cannot be violated
- what order to build in
- what counts as done
- how to hand off work to the next agent

The project focus is:

1. **Token Attribution**
2. **Schema-Aware Output Compression**
3. **Safe Repeated-Call Caching**
4. **Schema Description Optimization**
5. **Semantic Benchmark Suite** as the final proof layer

---

## 1. Project Summary

Aperture is a token-efficiency layer for Composio-powered agents.

It reduces waste from:

```text
Tool outputs      → schema-aware output compression
Repeated calls    → safe exact-match caching
Tool schemas      → schema description optimization
Everything above  → token attribution and reports
```

The main technical contribution is **schema-aware output compression**.

The main measurement layer is **token attribution**.

The main operational efficiency layer is **safe repeated-call caching**.

The final proof is a **benchmark suite** comparing raw Composio behavior against Composio + Aperture.

---

## 2. Agent Operating Rules

Every coding agent must follow these rules.

## 2.1 Safety-first rules

1. **Never cache write operations.**
2. **Never cache auth/OAuth/token-refresh operations.**
3. **Never use public cache scope for private data.**
4. **Never remove fields marked as preserved or critical in a compression profile.**
5. **Never store raw sensitive payloads in token/caching/compression events by default.**
6. **Never silently hide compression.** The model-facing payload must indicate compression occurred.
7. **Always preserve raw output access when compression omits meaningful detail.**
8. **Prefer deterministic compression before LLM summarization.**
9. **Do not change tool behavior during schema optimization.**
10. **If unsure whether something is safe, default to no compression/no caching/no rewrite.**

## 2.2 Coding rules

1. Every module needs unit tests.
2. Every integration point needs at least one integration-style test or mock test.
3. All public functions must have docstrings.
4. Use typed dataclasses or Pydantic models for core contracts.
5. Avoid hidden global state.
6. Do not mutate input payloads unless explicitly documented.
7. Emit structured events; do not print metrics as the only output.
8. Build with test fakes first, then swap in real Composio/Redis/event sinks.
9. Keep modules small and composable.
10. End every task with a handoff block.

## 2.3 Handoff format

Every coding agent must finish with:

```md
## Handoff

### Completed
- ...

### Files changed
- `path/to/file.py` — what changed

### Tests run
- `pytest tests/...` — pass/fail

### Assumptions
- ...

### Unknowns / blockers
- ...

### Next recommended task
- ...
```

---

## 3. Build Order

Build in this order:

```text
1. Tokenization primitives
2. Token attribution events
3. Compression profiles
4. Compression engine
5. Raw output store
6. Compression reports
7. Safe cache policy/key/store/interceptor
8. Schema optimizer
9. Benchmark suite
10. End-to-end integration/demo
```

Why this order:

- Token attribution is needed to prove compression/caching/schema savings.
- Compression is the main project contribution.
- Caching is primary but must be built after basic measurement exists.
- Schema optimization is useful but safer as a later module.
- Benchmarking comes last because it validates the full system.

---

## 4. Target Repository Structure

Coding agents should create or follow this structure:

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
      tokenizer_registry.py
      token_counter.py

    observability/
      __init__.py
      event_schema.py
      event_emitter.py
      aggregations.py
      reports.py

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

    cache/
      __init__.py
      policy.yaml
      policy.py
      normalizer.py
      key_builder.py
      redis_store.py
      interceptor.py
      bypass.py
      reports.py

    schema_optimizer/
      __init__.py
      fetch_schemas.py
      extract_fields.py
      tokenize_schemas.py
      rank_candidates.py
      rewrite_rules.py
      validator.py
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
    output_compression.md
    caching.md
    schema_optimization.md
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

# 5. Core Data Contracts

Use these contracts across modules. Agents should not invent incompatible shapes.

---

## 5.1 `TokenCount`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TokenCount:
    tokens: int
    tokenizer: str
    tokenizer_is_approximate: bool
    payload_bytes: int
```

---

## 5.2 `ExecutionContext`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionContext:
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    model: str | None
    cache_bypass: bool = False
    compression_bypass: bool = False
```

---

## 5.3 `TokenAttributionEvent`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TokenAttributionEvent:
    event_type: str
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    payload_kind: str
    model: str | None
    tokenizer: str
    tokenizer_is_approximate: bool
    raw_payload_bytes: int | None
    compressed_payload_bytes: int | None
    raw_tokens: int | None
    compressed_tokens: int | None
    input_tokens_contributed: int
    tokens_saved: int
    compression_ratio: float | None
    cache_status: str | None
    aperture_version: str
```

---

## 5.4 `CompressionContext`

```python
from dataclasses import dataclass

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
```

---

## 5.5 `CompressionResult`

```python
from dataclasses import dataclass

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
```

---

## 5.6 `CachePolicy`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CachePolicy:
    tool_slug: str
    cacheable: bool
    operation_type: str       # read/write/auth/unknown
    privacy_scope: str        # public/project/user/account/session/none
    ttl_seconds: int | None
    matching: str             # exact/none
    reason: str | None = None
```

---

## 5.7 `CacheEvent`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CacheEvent:
    event_type: str
    timestamp: str
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    tool_slug: str
    toolkit_slug: str | None
    cache_status: str
    cache_scope: str
    cache_key_hash: str | None
    ttl_seconds: int | None
    cached_age_seconds: int | None
    api_call_avoided: bool
    tokens_saved_estimate: int
    reason: str | None
```

---

## 5.8 `SchemaOptimizationResult`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SchemaOptimizationResult:
    tool_slug: str
    field_path: str
    original_text: str
    optimized_text: str
    original_tokens: int
    optimized_tokens: int
    reduction_tokens: int
    reduction_pct: float
    validation_cases_run: int
    validation_passed: bool
    accepted: bool
    rejection_reason: str | None
```

---

# 6. Component A — Token Attribution

## 6.1 Goal

Build the measurement layer that counts and reports token cost for:

- raw tool outputs
- compressed tool outputs
- meta-tool responses
- schema responses
- cache-hit savings estimates
- schema optimization savings

This component is required before meaningful claims can be made.

---

## 6.2 Required behavior

Token attribution must:

1. Serialize payloads deterministically.
2. Select tokenizer by model when possible.
3. Fall back safely when model is unknown.
4. Count tokens and payload bytes.
5. Emit structured events.
6. Aggregate results by tool/session/toolkit/strategy.
7. Never store raw sensitive payloads by default.

---

## 6.3 Public functions to implement

### `stable_serialize_payload`

File:

```text
aperture/tokenization/serializers.py
```

Signature:

```python
def stable_serialize_payload(payload: object) -> str:
    """Serialize payload deterministically for token counting."""
```

Requirements:

- sort dict keys recursively
- compact JSON separators
- preserve Unicode
- handle lists/dicts/scalars
- do not mutate input
- fail clearly for unsupported values

---

### `count_tokens_for_payload`

File:

```text
aperture/tokenization/token_counter.py
```

Signature:

```python
def count_tokens_for_payload(
    payload: object,
    model: str | None = None,
    tokenizer_hint: str | None = None,
) -> TokenCount:
    """Return token count, tokenizer name, approximation flag, and byte size."""
```

Requirements:

- use stable serializer
- use tokenizer registry
- unknown model uses fallback
- return `TokenCount`
- handle large payloads

---

### `emit_token_event`

File:

```text
aperture/observability/event_emitter.py
```

Signature:

```python
def emit_token_event(event: TokenAttributionEvent) -> None:
    """Emit a token attribution event to the configured sink."""
```

Requirements:

- support in-memory sink for tests
- support file/DB/log sink later
- validate required fields
- do not store raw payload

---

## 6.4 Tokenizer registry

File:

```text
aperture/tokenization/tokenizer_registry.py
```

Example mapping:

```python
TOKENIZER_BY_MODEL = {
    "gpt-4.1": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "claude-sonnet-4": "anthropic_count_tokens",
    "unknown": "cl100k_base",
}
```

If a provider tokenizer is unavailable, implement a fallback and mark `tokenizer_is_approximate=True`.

---

## 6.5 Reports

File:

```text
aperture/observability/reports.py
```

Reports to implement:

1. `top_expensive_tools_report`
2. `compression_savings_report`
3. `cache_savings_report`
4. `session_cost_report`
5. `schema_savings_report`

Report format can be Markdown and JSON.

---

## 6.6 Tests

Files:

```text
tests/tokenization/test_serializers.py
tests/tokenization/test_token_counter.py
tests/observability/test_event_emitter.py
tests/observability/test_reports.py
```

Required tests:

- same payload gives same serialized string
- different key order gives same serialized string
- token count deterministic
- unknown model uses fallback
- large payload works
- event contains no raw payload
- reports group correctly
- compressed event calculates savings correctly

---

## 6.7 Definition of done

Token attribution is done when:

- payloads can be counted deterministically
- raw/compressed counts are emitted
- cache-hit savings can be estimated
- schema before/after savings can be reported
- reports group by tool, toolkit, session, and strategy
- all tokenization/observability tests pass

---

# 7. Component B — Schema-Aware Output Compression

## 7.1 Goal

Compress raw Composio tool outputs into compact, useful, model-facing payloads.

This is the main technical contribution.

---

## 7.2 Required behavior

The compressor must:

1. Load a tool-specific or default profile.
2. Count raw tokens.
3. Store raw output if needed.
4. Apply safe deterministic compression.
5. Optionally summarize long fields when allowed.
6. Build a clear compressed envelope.
7. Count compressed tokens.
8. Emit savings event.
9. Return compressed payload.
10. Preserve critical information.

---

## 7.3 Compression modes

Supported modes:

```text
off       → return raw output
shadow    → compress and measure, but return raw
safe      → remove nulls/empty fields/API metadata
balanced  → safe + flattening + list compaction + deduplication
```

Do not implement `aggressive` as a production mode unless benchmarks prove it safe.

---

## 7.4 Compression profile format

File:

```text
aperture/compression/profiles.yaml
```

Required structure:

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
    raw_reference: true
```

---

## 7.5 Initial supported tool profiles

MVP should support at least these:

1. `GITHUB_LIST_ISSUES`
2. `GITHUB_LIST_PULL_REQUESTS`
3. `GMAIL_SEARCH_EMAILS`
4. `SLACK_SEARCH_MESSAGES`
5. `NOTION_QUERY_DATABASE`

If exact Composio slugs differ, use the real slugs after integration discovery.

---

## 7.6 Compression steps

### Step 1 — Profile loading

File:

```text
aperture/compression/profile_loader.py
```

Function:

```python
def load_compression_profile(tool_slug: str) -> CompressionProfile:
    """Return tool-specific profile or default safe profile."""
```

Requirements:

- unknown tools use default safe profile
- invalid profile raises clear error
- preserve/drop/flatten/compact/summarize rules are parsed

---

### Step 2 — Field pruning

File:

```text
aperture/compression/field_pruning.py
```

Function:

```python
def prune_fields(payload: object, profile: CompressionProfile) -> tuple[object, list[str]]:
    """Remove configured low-value fields while preserving critical fields."""
```

Rules:

- remove configured drop fields
- remove nulls if enabled
- remove empty strings/arrays if enabled
- remove obvious API URL fields if enabled
- never remove preserve fields
- return omitted field list

---

### Step 3 — Flattening

File:

```text
aperture/compression/flattening.py
```

Function:

```python
def flatten_fields(payload: object, profile: CompressionProfile) -> object:
    """Flatten configured nested fields such as user.login -> author."""
```

Example:

```json
{"user": {"login": "nikos", "avatar_url": "..."}}
```

becomes:

```json
{"author": "nikos"}
```

---

### Step 4 — List compaction

File:

```text
aperture/compression/list_compaction.py
```

Function:

```python
def compact_lists(payload: object, profile: CompressionProfile) -> object:
    """Compact lists of objects into useful scalar arrays when configured."""
```

Example:

```json
"labels": [{"name": "bug"}, {"name": "urgent"}]
```

becomes:

```json
"labels": ["bug", "urgent"]
```

---

### Step 5 — Deduplication

File:

```text
aperture/compression/deduplication.py
```

Function:

```python
def deduplicate_repeated_objects(payload: object, profile: CompressionProfile) -> object:
    """Remove or lift repeated nested objects when safe."""
```

MVP can implement simple repeated-object dedupe only for obvious configured paths.

---

### Step 6 — Long-text compression

File:

```text
aperture/compression/text_summarization.py
```

Function:

```python
def compress_long_text_fields(payload: object, profile: CompressionProfile) -> object:
    """Truncate or extractively summarize long text fields when allowed."""
```

MVP strategies:

```text
none
truncate
extractive
```

Optional later:

```text
cheap_llm
```

Rules:

- preserve raw reference for omitted long text
- include metadata that text was shortened
- do not summarize private sensitive content with LLM unless allowed by config

---

### Step 7 — Raw output store

File:

```text
aperture/compression/raw_store.py
```

Functions:

```python
def store_raw_output(raw_payload: object, context: CompressionContext) -> str:
    """Store raw payload and return opaque raw_reference_id."""

def get_raw_output(raw_reference_id: str) -> object:
    """Retrieve raw payload by reference, if allowed."""
```

MVP can use:

- in-memory store for tests
- file-based store for local demo

Requirements:

- opaque IDs
- no sensitive content in ID
- project/user/session scoping
- configurable retention later

---

### Step 8 — Envelope builder

File:

```text
aperture/compression/envelope.py
```

Function:

```python
def build_compression_envelope(
    compressed_payload: object,
    result: CompressionResult,
    context: CompressionContext,
) -> object:
    """Wrap compressed result with metadata visible to the model."""
```

Envelope should include:

```json
{
  "aperture_compressed": true,
  "tool_slug": "GITHUB_LIST_ISSUES",
  "data": {},
  "omitted_fields": [],
  "raw_reference_id": "raw_abc123",
  "compression": {
    "raw_tokens": 3200,
    "compressed_tokens": 420,
    "tokens_saved": 2780,
    "compression_ratio": 0.131
  }
}
```

---

### Step 9 — Main compressor

File:

```text
aperture/compression/compressor.py
```

Function:

```python
def compress_tool_output(
    raw_payload: object,
    context: CompressionContext,
) -> CompressionResult:
    """Run the full compression pipeline for a tool output."""
```

Pipeline:

```text
load profile
count raw tokens
store raw if needed
prune fields
flatten fields
compact lists
deduplicate repeated objects
compress long text
build envelope
count compressed tokens
emit event
return result
```

---

## 7.7 Tests

Files:

```text
tests/compression/test_profile_loader.py
tests/compression/test_field_pruning.py
tests/compression/test_flattening.py
tests/compression/test_list_compaction.py
tests/compression/test_deduplication.py
tests/compression/test_text_summarization.py
tests/compression/test_raw_store.py
tests/compression/test_envelope.py
tests/compression/test_compressor.py
```

Required tests:

- unknown tool uses default safe profile
- preserve fields remain
- configured drop fields are removed
- nulls/empty values removed when enabled
- API URL fields removed when enabled
- `user.login` can become `author`
- labels compact into list of names
- raw reference is created
- compressed output marks `aperture_compressed: true`
- token savings are positive on fixtures
- input payload is not mutated
- private raw output is not stored in public scope

---

## 7.8 Definition of done

Output compression is done when:

- 5 initial tool profiles exist
- safe and balanced modes work
- raw references work
- compression envelope exists
- compression event is emitted
- all compression tests pass
- fixture outputs are smaller and still useful

---

# 8. Component C — Safe Repeated-Call Caching

## 8.1 Goal

Cache approved safe read-only tool calls to avoid repeated API calls and repeated output cost.

Caching is a primary Aperture feature, but must be conservative.

---

## 8.2 Caching rules

Cache only when:

- tool is explicitly marked cacheable
- operation is read-only/idempotent
- scope is known
- TTL exists
- params normalize safely
- response succeeded

Never cache:

- writes
- creates
- updates
- deletes
- sends
- auth flows
- failed responses by default
- private data in public scope

---

## 8.3 Cache policy file

File:

```text
aperture/cache/policy.yaml
```

Required format:

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

  GITHUB_LIST_ISSUES:
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 900
    matching: exact

  GMAIL_SEARCH_EMAILS:
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 300
    matching: exact

  GMAIL_SEND_EMAIL:
    cacheable: false
    operation_type: write
    privacy_scope: account
    ttl_seconds: null
    matching: none
    reason: write_operation
```

---

## 8.4 Cache key

Exact-match only.

Format:

```text
aperture:v1:{scope}:{scope_id}:{tool_slug}:{sha256(normalized_params)}
```

Examples:

```text
aperture:v1:public:none:GITHUB_GET_REPO:sha256(...)
aperture:v1:account:ca_123:GMAIL_SEARCH_EMAILS:sha256(...)
```

If scope ID is required but missing, do not cache.

---

## 8.5 Required modules

### Policy loader

File:

```text
aperture/cache/policy.py
```

Function:

```python
def load_cache_policy(tool_slug: str) -> CachePolicy:
    """Return cache policy, defaulting to non-cacheable."""
```

---

### Param normalizer

File:

```text
aperture/cache/normalizer.py
```

Function:

```python
def normalize_params(tool_slug: str, params: dict) -> dict:
    """Normalize params for exact-match keying."""
```

Rules:

- sort dict keys recursively
- preserve list order
- remove Aperture-only metadata
- do not lowercase arbitrary strings unless tool-specific
- do not modify semantic values

---

### Key builder

File:

```text
aperture/cache/key_builder.py
```

Function:

```python
def build_cache_key(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    policy: CachePolicy,
) -> str | None:
    """Build scoped exact-match cache key or return None if unsafe."""
```

---

### Cache store

File:

```text
aperture/cache/redis_store.py
```

Interface:

```python
class CacheStore:
    def get(self, key: str) -> object | None: ...
    def set(self, key: str, value: object, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...
```

MVP should include:

- in-memory fake store for tests
- Redis-compatible wrapper if available

---

### Cache interceptor

File:

```text
aperture/cache/interceptor.py
```

Function:

```python
async def maybe_execute_with_cache(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    execute_fn,
) -> object:
    """Return cached response on hit, otherwise execute and store if safe."""
```

Flow:

```text
check bypass
load policy
if not cacheable → execute
normalize params
build key
lookup cache
hit → return cached response
miss → execute
if success → store with TTL
emit event
```

---

## 8.6 Bypass support

File:

```text
aperture/cache/bypass.py
```

Support:

```text
X-Aperture-Cache-Bypass: true
```

and/or metadata:

```json
{
  "aperture_cache_bypass": true
}
```

---

## 8.7 Tests

Files:

```text
tests/cache/test_policy.py
tests/cache/test_normalizer.py
tests/cache/test_key_builder.py
tests/cache/test_redis_store.py
tests/cache/test_interceptor.py
tests/cache/test_bypass.py
```

Required tests:

- unknown tools are not cacheable
- write tools are never cacheable
- auth tools are never cacheable
- same params in different order produce same key
- different accounts produce different keys
- missing account ID prevents account-scoped caching
- cache hit avoids execution
- cache miss executes once
- failed response is not cached
- bypass forces execution
- event emitted for hit/miss/bypass/not-cacheable

---

## 8.8 Definition of done

Caching is done when:

- exact-match cache works
- scope-safe keys work
- write/auth tools cannot be cached
- bypass works
- events report hit/miss/bypass/not-cacheable
- cache hit avoids execution
- all cache tests pass

---

# 9. Component D — Schema Description Optimization

## 9.1 Goal

Reduce token cost of tool descriptions and parameter descriptions while preserving agent behavior.

---

## 9.2 What can be changed

Allowed:

- tool description text
- parameter description text
- enum description text
- verbose repeated phrasing
- redundant type explanations

Not allowed:

- tool slug
- parameter names
- required fields
- parameter types
- auth behavior
- execution behavior
- return schemas
- safety-critical warnings without review

---

## 9.3 Required modules

### Schema fetcher

File:

```text
aperture/schema_optimizer/fetch_schemas.py
```

Function:

```python
def fetch_tool_schemas() -> list[dict]:
    """Fetch current tool schemas from source/API/fixtures."""
```

MVP can use fixture schemas if live registry access is unavailable.

---

### Field extractor

File:

```text
aperture/schema_optimizer/extract_fields.py
```

Function:

```python
def extract_description_fields(schema: dict) -> list[SchemaField]:
    """Extract tool and parameter description fields with paths."""
```

---

### Schema tokenizer

File:

```text
aperture/schema_optimizer/tokenize_schemas.py
```

Function:

```python
def tokenize_schema_fields(fields: list[SchemaField]) -> list[SchemaFieldTokenCount]:
    """Count tokens for schema description fields."""
```

---

### Candidate ranker

File:

```text
aperture/schema_optimizer/rank_candidates.py
```

Function:

```python
def rank_schema_candidates(fields: list[SchemaFieldTokenCount]) -> list[SchemaFieldTokenCount]:
    """Rank fields by token cost and usage impact if available."""
```

---

### Rewrite rules

File:

```text
aperture/schema_optimizer/rewrite_rules.py
```

Function:

```python
def generate_schema_rewrite_candidates(field: SchemaField) -> list[str]:
    """Generate compact description rewrite candidates."""
```

Example:

```text
Before:
Creates a new issue in a specified GitHub repository. You must provide the repository owner username, repository name, and issue title.

After:
Create a GitHub issue. Required: owner, repo, title.
```

---

### Validator

File:

```text
aperture/schema_optimizer/validator.py
```

Function:

```python
def validate_schema_rewrite(
    original_schema: dict,
    candidate_schema: dict,
    validation_cases: list[dict],
) -> ValidationResult:
    """Validate that rewrite preserves tool selection and parameter behavior."""
```

Validation must check:

- same tool selected
- required params still clear
- optional params still clear
- similar tools not confused
- safety/auth meaning preserved

---

### Reports

File:

```text
aperture/schema_optimizer/reports.py
```

Report includes:

- original tokens
- optimized tokens
- tokens saved
- reduction percent
- validation pass/fail
- accepted/rejected
- rejection reason

---

## 9.4 Tests

Files:

```text
tests/schema_optimizer/test_extract_fields.py
tests/schema_optimizer/test_tokenize_schemas.py
tests/schema_optimizer/test_rewrite_rules.py
tests/schema_optimizer/test_validator.py
tests/schema_optimizer/test_reports.py
```

Required tests:

- fields extracted correctly
- token counts deterministic
- rewrite does not change parameter names
- rewrite does not change required fields
- unsafe rewrite rejected
- accepted rewrite has lower token count
- report includes validation status

---

## 9.5 Definition of done

Schema optimization is done when:

- top candidate schemas are measured
- rewrite candidates are generated
- unsafe rewrites are rejected
- accepted rewrites pass validation
- before/after report exists
- schema behavior is preserved

---

# 10. Component E — Semantic Benchmark Suite

Benchmarking is the final proof layer.

It should be built after token attribution, compression, caching, and schema optimization are implemented enough to compare.

---

## 10.1 Goal

Run the same tasks with and without Aperture and measure:

- token savings
- compression ratio
- cache hit rate
- API calls avoided
- schema savings
- task success
- missing information
- extra tool calls
- latency

---

## 10.2 Benchmark modes

```text
raw                 → normal Composio-style outputs
aperture_compressed → output compression enabled
aperture_cached     → compression + cache enabled
aperture_full       → compression + cache + schema optimization
shadow              → measure compression but return raw
```

---

## 10.3 Task format

File:

```text
aperture/benchmarks/tasks/*.jsonl
```

Example:

```json
{
  "task_id": "github_001",
  "category": "github",
  "user_prompt": "Find all auth-related GitHub issues and summarize the top blockers.",
  "tools_allowed": ["GITHUB_LIST_ISSUES"],
  "expected_behavior": "Agent identifies auth-related issues, summarizes blockers, and cites issue numbers.",
  "evaluation_type": "field_presence_and_llm_judge",
  "critical_fields": ["title", "state", "labels", "body", "comments"]
}
```

---

## 10.4 Runner

File:

```text
aperture/benchmarks/runner.py
```

Function:

```python
def run_benchmark(task_set: list[BenchmarkTask], mode: str) -> BenchmarkRunResult:
    """Run tasks in selected mode and collect metrics."""
```

---

## 10.5 Evaluators

File:

```text
aperture/benchmarks/evaluators.py
```

Implement:

1. exact evaluator
2. field-presence evaluator
3. trace comparison evaluator
4. LLM-judge evaluator stub/config
5. human-review export

---

## 10.6 Metrics

File:

```text
aperture/benchmarks/metrics.py
```

Track:

```python
@dataclass(frozen=True)
class BenchmarkMetrics:
    task_id: str
    mode: str
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float
    cache_hits: int
    api_calls_avoided: int
    schema_tokens_saved: int
    task_success: bool
    success_score: float
    missing_critical_info: bool
    extra_tool_calls: int
    raw_fallback_used: bool
    latency_ms: int
```

---

## 10.7 Report

File:

```text
aperture/benchmarks/report.py
```

Final report must include:

- tasks run
- tools tested
- modes compared
- token savings
- compression savings
- cache savings
- schema savings
- task success comparison
- failure cases
- raw vs compressed examples
- recommendation for production mode

---

## 10.8 Tests

Files:

```text
tests/benchmarks/test_task_set.py
tests/benchmarks/test_runner.py
tests/benchmarks/test_evaluators.py
tests/benchmarks/test_metrics.py
tests/benchmarks/test_report.py
```

Required tests:

- tasks load from JSONL
- runner supports all modes
- metrics aggregate correctly
- evaluators return pass/fail/score
- report includes token and quality metrics

---

## 10.9 Definition of done

Benchmarking is done when:

- raw and Aperture modes are compared
- benchmark outputs metrics JSON
- benchmark outputs Markdown report
- task quality is measured
- failure cases are documented
- final claims are based on measured values

---

# 11. Integration Pipeline

After components exist individually, integrate them in this order:

```text
tool execution result
    ↓
maybe_execute_with_cache(...)
    ↓
compress_tool_output(...)
    ↓
emit token/compression/cache events
    ↓
return model-facing payload
```

Recommended wrapper:

```python
async def aperture_tool_result_pipeline(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    execute_fn,
) -> object:
    """Run cache, compression, and token attribution around a tool call."""
```

Expected behavior:

1. cache checks before execution
2. execution happens only on miss/not-cacheable
3. raw output is compressed after execution or cache retrieval
4. token events are emitted
5. final payload is returned to model

---

# 12. Implementation Timeline

## Week 1 — Token attribution foundation

Build:

- serializer
- tokenizer registry
- token counter
- token events
- raw fixture baseline

Deliver:

- `raw_token_baseline.md`

---

## Week 2 — Compression engine

Build:

- profiles
- field pruning
- flattening
- list compaction
- raw store
- envelope
- main compressor

Deliver:

- `compression_report.md`

---

## Week 3 — Compression hardening and observability

Build:

- event integration
- compression reports
- fixtures for 5 tools
- end-to-end compression tests

Deliver:

- working compression pipeline

---

## Week 4 — Safe caching

Build:

- policy
- normalizer
- key builder
- cache store
- interceptor
- bypass
- cache reports

Deliver:

- `cache_report.md`

---

## Week 5 — Schema optimization

Build:

- schema fetcher/fixtures
- field extractor
- schema tokenizer
- rewrite rules
- validator
- reports

Deliver:

- `schema_optimization_report.md`

---

## Week 6 — Integrated Aperture pipeline

Build:

- full wrapper pipeline
- integration tests
- docs
- security checks

Deliver:

- integrated Aperture core

---

## Week 7 — Benchmark suite

Build:

- task set
- runner
- evaluators
- metrics
- report generator

Deliver:

- first benchmark run

---

## Week 8 — Final demo and report

Build:

- final benchmark report
- polished examples
- demo script
- final handoff

Deliver:

- `benchmark_report.md`
- final project demo

---

# 13. Quality Gates

## Gate 1 — Token attribution

Pass if:

- deterministic counts
- no payload mutation
- event emission works
- reports group correctly

Fail if:

- raw sensitive payloads are stored in events
- unknown models crash counting

---

## Gate 2 — Output compression

Pass if:

- preserve fields remain
- compressed output marks compression
- raw reference exists when detail is omitted
- token count decreases on fixtures

Fail if:

- critical fields are removed
- unknown tools use unsafe compression
- private raw outputs are publicly stored

---

## Gate 3 — Caching

Pass if:

- writes/auth tools cannot be cached
- scoped keys include required IDs
- cache hit avoids execution
- bypass works

Fail if:

- private data can hit public cache
- failed responses are cached
- semantic matching is used for execution outputs

---

## Gate 4 — Schema optimization

Pass if:

- accepted rewrites preserve behavior
- required fields/types/names unchanged
- before/after report exists

Fail if:

- tool selection changes
- parameter behavior changes
- safety wording is removed silently

---

## Gate 5 — Benchmarking

Pass if:

- raw and Aperture modes compared
- token savings measured
- quality measured
- failure cases included

Fail if:

- claims are guessed
- only cherry-picked examples are shown

---

# 14. Security and Privacy Checklist

## Token attribution

- [ ] no raw payloads stored by default
- [ ] token counts and bytes only
- [ ] user/project/session boundaries respected
- [ ] approximate tokenizer marked

## Compression

- [ ] critical fields preserved
- [ ] compression visible
- [ ] raw references opaque
- [ ] private raw store scoped
- [ ] bypass supported

## Caching

- [ ] deny-by-default policy
- [ ] writes blocked
- [ ] auth blocked
- [ ] private scopes include required IDs
- [ ] cache key hashes logged, not raw keys

## Schema optimization

- [ ] parameter names unchanged
- [ ] parameter types unchanged
- [ ] required fields unchanged
- [ ] validation passed
- [ ] rollback possible

---

# 15. Final Deliverables

## Code deliverables

- token serializer
- tokenizer registry
- token counter
- event schema/emitter
- reports
- compression profiles
- profile loader
- field pruning
- flattening
- list compaction
- deduplication
- text compression
- raw output store
- envelope builder
- main compressor
- cache policy
- cache normalizer
- cache key builder
- cache store
- cache interceptor
- schema optimizer
- benchmark runner/evaluator/report

## Report deliverables

```text
reports/raw_token_baseline.md
reports/compression_report.md
reports/cache_report.md
reports/schema_optimization_report.md
reports/benchmark_report.md
```

## Docs deliverables

```text
docs/token_attribution.md
docs/output_compression.md
docs/caching.md
docs/schema_optimization.md
docs/benchmark_methodology.md
docs/security_privacy.md
docs/workbench_boundary.md
```

---

# 16. Perfect Coding-Agent Prompt Template

Use this when assigning work to a coding agent:

```md
You are building Aperture, a token-efficiency layer for Composio agents.

Project focus:
1. Token attribution
2. Schema-aware output compression
3. Safe repeated-call caching
4. Schema description optimization
5. Benchmarking as final proof

Rules:
- Do not cache writes/auth flows.
- Do not use public cache scope for private data.
- Do not remove preserved/critical fields.
- Do not store raw sensitive payloads in observability events.
- Preserve raw references when compression omits meaningful detail.
- Prefer deterministic compression before LLM summarization.
- Do not change schema behavior.
- Add tests for every module.
- End with a handoff block.

Your task:
[INSERT TASK CARD]

Files to work on:
[INSERT FILE PATHS]

Required interfaces:
[INSERT CONTRACTS]

Definition of done:
[INSERT ACCEPTANCE CRITERIA]
```

---

# 17. Final Summary

Aperture is complete when coding agents have built:

1. a deterministic token attribution layer,
2. a schema-aware output compression engine,
3. a safe exact-match repeated-call cache,
4. a validated schema description optimizer,
5. a semantic benchmark suite proving savings and quality.

Final proof:

```text
Same tasks.
Raw Composio vs Composio + Aperture.
Measured token savings.
Measured cache savings.
Measured schema savings.
Measured task quality.
```
