# Aperture — Execution-Ready Project Plan for Coding Agents

## Token-Efficiency Layer for Composio Agents

**Status:** Validated implementation plan  
**Primary scope:** Token attribution, safe caching, measured schema optimization  
**Audience:** Coding agents, research agents, QA agents, reviewer agents, human engineers  
**Goal:** Make Composio-powered agents cheaper, faster, and easier to debug by measuring Composio-contributed token cost, caching safe repeated tool calls, and optimizing tool schemas without degrading agent behavior.

---

# 0. Agent Operating Rules

This section is intentionally first. Every coding/research/QA agent working on Aperture should follow these rules.

## 0.1 Non-negotiable rules

1. **Do not guess internal Composio behavior.** If a hook point, payload shape, storage path, or API behavior is unknown, mark it as `UNKNOWN` and create an investigation task.
2. **Prefer conservative behavior over clever behavior.** Especially for caching. A cache miss is better than a wrong or private cache hit.
3. **Never cache writes.** Any action that mutates state must be non-cacheable by default.
4. **Never share private data across users/accounts.** Private cache keys must include the correct user/account/project scope.
5. **Do not optimize schemas by shortening them blindly.** A schema rewrite is only valid if behavior stays the same under validation.
6. **Do not claim full LLM cost attribution unless Aperture is in the LLM provider call path.** The correct claim is: `Composio-contributed input tokens`.
7. **Every module must have tests.** No module is considered complete without unit tests and at least one integration-style test.
8. **Every event must be privacy-safe.** Store counts, metadata, hashes, payload sizes, and token counts. Do not store raw sensitive payloads unless explicitly allowed by existing Composio logging policy.
9. **Every accepted optimization must be reversible.** Cache can be bypassed. Schema rewrites must have before/after diffs. Token attribution can be disabled by config.
10. **Every agent handoff must include assumptions, unknowns, files changed, tests run, and next steps.**

## 0.2 Agent handoff format

Every agent should end its work with this handoff block:

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

## 0.3 How agents should prioritize

Priority order:

1. Correctness
2. Privacy/security
3. Measurability
4. Simplicity
5. Performance
6. Extra features

If two approaches are possible, choose the one that is easier to audit and safer to roll back.

---

# 1. Project Summary

Aperture is a token-efficiency infrastructure layer for Composio’s meta-tool architecture.

It improves Composio-powered agents in three practical ways:

1. **Token Attribution Observability**  
   Measures how many LLM input tokens are contributed by Composio meta-tool responses, tool schemas, tool execution results, workbench outputs, and planning payloads.

2. **Safe Repeated Tool-Call Caching**  
   Caches approved, idempotent, read-only tool results using conservative exact-match keys, so repeated calls can avoid duplicate external API calls and repeated result payloads.

3. **Schema Token Optimization**  
   Rewrites verbose tool descriptions and parameter descriptions into shorter versions, then validates that agents still select the right tools and fill parameters correctly.

Aperture is not a replacement for Composio, MCP, LangChain, OpenAI Agents SDK, Workbench, or any LLM orchestration framework. It is an efficiency and observability layer around Composio’s existing tool discovery/execution flow.

---

# 2. Correct Framing After Validation

## 2.1 Best one-sentence description

Aperture makes Composio-powered agents more efficient by measuring Composio-contributed token cost, caching safe repeated tool calls, and optimizing tool schemas without degrading agent behavior.

## 2.2 Best technical description

Aperture instruments Composio meta-tool responses to attribute input-token contribution, adds a conservative exact-match cache around idempotent read executions, and runs a tokenizer-aware schema optimization pipeline with behavioral validation.

## 2.3 What to avoid saying

Do not say:

- “Composio has zero schema optimization.”
- “Aperture measures the full LLM bill.”
- “All repeated tool calls can be cached.”
- “Session context compression is automatic.”
- “Semantic caching is safe for arbitrary tool calls.”

## 2.4 Better claims

Say:

- “Composio has some schema simplification and schema modifier capabilities; Aperture adds measured tokenizer-aware optimization with validation.”
- “Aperture measures Composio-contributed input tokens.”
- “Aperture caches approved safe read-only calls with strict scoping and TTLs.”
- “Session state compression is follow-on, opt-in, and requires orchestrator cooperation.”

---

# 3. MVP Scope

## 3.1 In scope

| Area | MVP behavior |
|---|---|
| Token attribution | Count tokens for Composio-originated payloads returned to agents |
| Usage reporting | Aggregate by project, user, session, meta tool, toolkit, tool, payload kind, date |
| Cache | Redis exact-match cache for approved read-only tool calls |
| Cache safety | Deny-by-default policy, user/account scoping, TTLs, bypass |
| Cache metrics | Hit/miss/bypass/not-cacheable events and estimated tokens/API calls saved |
| Schema optimization | Optimize top 25 high-impact schemas with validation |
| Benchmarks | Before/after workflows proving measured impact |
| Docs | Developer and internal engineering documentation |

## 3.2 Out of scope for MVP

| Out of scope | Reason |
|---|---|
| Semantic result caching | Too risky for arbitrary execution outputs |
| Cross-tenant shared private cache | Legal/security risk |
| Automatic context compression | Requires orchestrator control |
| Automatic plan pruning | Outcome signal is noisy |
| Full LLM provider bill attribution | Requires LLM API call path access |
| Full 1,000+ schema rewrite | Too large for MVP |
| UI dashboard | Nice-to-have after report/API works |

## 3.3 MVP success definition

The MVP succeeds if a developer can answer:

1. Which Composio meta-tool responses are costing the most tokens?
2. Which sessions/users/toolkits are most expensive?
3. Which repeated safe calls were served from cache?
4. How many external API calls did the cache avoid?
5. How many estimated tokens did caching save?
6. Which schemas were optimized, by how much, and with what validation result?

---

# 4. Architecture

## 4.1 Existing Composio flow

```text
Developer application / agent framework
        ↓
LLM sees Composio meta tools
        ↓
LLM calls a Composio meta tool
        ↓
Composio Tool Router discovers, executes, manages auth, or uses Workbench
        ↓
Composio returns schemas/results/plans/workbench payloads
        ↓
Returned payload enters future LLM context
```

## 4.2 Aperture-enhanced flow

```text
Developer application / agent framework
        ↓
LLM calls Composio meta tool
        ↓
Aperture pre-execution layer checks cache policy if execution call
        ↓
Cache hit: return cached result
Cache miss: execute normally through Composio
        ↓
Aperture post-response layer serializes payload
        ↓
Aperture tokenizes payload
        ↓
Aperture emits token/cache events
        ↓
Aggregation/reporting layer exposes usage and savings
```

## 4.3 Module map

```text
aperture/
  observability/        # token attribution and usage aggregation
  cache/                # exact-match cache policy, keys, Redis store, interceptor
  schema_optimizer/     # schema token measurement, rewriting, validation, reports
  benchmarks/           # before/after workflows and final reports
  docs/                 # implementation and user documentation
  tests/                # unit, integration, safety, regression tests
```

## 4.4 Integration points to discover

Coding agents must identify actual internal hook points. Until confirmed, use these names as conceptual placeholders:

| Conceptual hook | Purpose | Required? |
|---|---|---:|
| `before_multi_execute` | Check cache before underlying tool execution | Yes |
| `after_multi_execute` | Store successful cacheable responses | Yes |
| `after_meta_tool_response` | Count tokens for returned payloads | Yes |
| `usage_event_writer` | Store token/cache events | Yes |
| `schema_registry_reader` | Fetch current tool schemas | Yes |
| `schema_registry_writer` | Apply approved schema diffs | Optional for MVP; report-only acceptable |

---

# 5. Data Contracts

These contracts are the stable interface between agents/modules.

## 5.1 `ExecutionContext`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ExecutionContext:
    project_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    connected_account_id: Optional[str]
    toolkit_slug: Optional[str]
    meta_tool_slug: Optional[str]
    model: Optional[str]
    cache_bypass: bool = False
```

## 5.2 `TokenAttributionEvent`

```python
@dataclass(frozen=True)
class TokenAttributionEvent:
    event_type: str                 # always "input_tokens_contributed"
    timestamp: str
    project_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    meta_tool_slug: Optional[str]
    tool_slug: Optional[str]
    toolkit_slug: Optional[str]
    model: Optional[str]
    tokenizer: str
    payload_kind: str               # schema/search/result/workbench/plan/other
    payload_bytes: int
    input_tokens_contributed: int
    cache_status: Optional[str]     # hit/miss/bypass/not_cacheable/null
    aperture_version: str
```

## 5.3 `CacheLookupEvent`

```python
@dataclass(frozen=True)
class CacheLookupEvent:
    event_type: str                 # always "cache_lookup"
    timestamp: str
    project_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    connected_account_id: Optional[str]
    tool_slug: str
    toolkit_slug: Optional[str]
    cache_status: str               # hit/miss/bypass/not_cacheable/error
    cache_scope: str                # public/project/user/account/session/none
    cache_key_hash: Optional[str]
    ttl_seconds: Optional[int]
    cached_age_seconds: Optional[int]
    tokens_saved_estimate: int
    api_call_avoided: bool
    reason: Optional[str]
```

## 5.4 `CachePolicy`

```python
@dataclass(frozen=True)
class CachePolicy:
    tool_slug: str
    cacheable: bool
    operation_type: str             # read/write/auth/unknown
    privacy_scope: str              # public/project/user/account/session/none
    ttl_seconds: Optional[int]
    matching: str                   # exact/none
    cache_failed_responses: bool = False
    reason: Optional[str] = None
```

## 5.5 `SchemaOptimizationResult`

```python
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
    behavior_differences: list[str]
    accepted: bool
    rejection_reason: Optional[str]
```

---

# 6. Component A — Token Attribution Observability

## 6.1 Problem

Developers often know total LLM cost from their model provider, but not which Composio payloads caused that cost. Aperture makes Composio-originated token contribution visible.

## 6.2 Correct measurement claim

Aperture measures:

> Tokens contributed by Composio-originated payloads that are returned to the agent and may enter LLM context.

Aperture does not automatically measure:

- Total provider bill
- User/system prompt tokens outside Composio
- Assistant output tokens
- Hidden reasoning tokens
- Non-Composio tool payloads

## 6.3 Payloads to measure

| Payload kind | Examples |
|---|---|
| `tool_search_response` | `COMPOSIO_SEARCH_TOOLS` result |
| `tool_schema_response` | `COMPOSIO_GET_TOOL_SCHEMAS` result |
| `tool_execution_result` | `COMPOSIO_MULTI_EXECUTE_TOOL` result |
| `workbench_output` | Remote workbench response |
| `plan_payload` | Learned/recommended plan text |
| `connection_payload` | Connection status payload, if returned to agent |
| `other` | Anything not classified yet |

## 6.4 Algorithm

```text
For every Composio meta-tool response:
  1. Classify payload kind.
  2. Serialize payload using stable JSON.
  3. Select tokenizer based on model hint, else fallback.
  4. Count tokens.
  5. Emit TokenAttributionEvent.
  6. Continue returning original payload unchanged.
```

## 6.5 Stable serialization requirements

The serializer must:

- Sort object keys
- Use compact separators
- Preserve Unicode safely
- Avoid nondeterministic fields where possible
- Optionally redact fields before storage/logging, but count the actual returned payload unless privacy policy says otherwise

Example:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

## 6.6 Tokenizer selection

Priority order:

1. Model-specific tokenizer if known
2. Provider-family tokenizer if known
3. Default fallback tokenizer

Example mapping:

```yaml
gpt-4.1: cl100k_base
gpt-4o: o200k_base
gpt-4o-mini: o200k_base
claude-sonnet-4: anthropic_count_tokens
unknown: cl100k_base
```

If a tokenizer is approximate, event metadata must indicate approximation.

## 6.7 Public functions

```python
def stable_serialize_payload(payload: object) -> str:
    """Return deterministic string representation for token counting."""


def count_payload_tokens(
    payload: object,
    model: str | None = None,
    tokenizer_hint: str | None = None,
) -> tuple[int, str]:
    """Return token count and tokenizer name."""


def emit_token_event(
    event: TokenAttributionEvent,
) -> None:
    """Write token attribution event to configured event sink."""
```

## 6.8 Required tests

### Unit tests

- Same payload produces same serialized output.
- Different object key order produces same serialized output.
- Empty payload counts without crashing.
- Large payload counts without crashing.
- Unknown model uses fallback.
- Token count is positive for non-empty payload.

### Integration tests

- Simulated `COMPOSIO_SEARCH_TOOLS` response emits event.
- Simulated `COMPOSIO_GET_TOOL_SCHEMAS` response emits event.
- Simulated `COMPOSIO_MULTI_EXECUTE_TOOL` response emits event.
- Event includes project/session/meta-tool metadata.

## 6.9 Definition of done

This component is done when:

- 95%+ of known meta-tool response paths emit token events.
- Events are queryable by project, user, session, meta tool, toolkit, and date.
- Counts are deterministic for the same payload.
- Reports identify top token-expensive payload kinds.
- No raw sensitive payloads are stored by the new event system unless explicitly approved.

---

# 7. Component B — Safe Repeated Tool-Call Caching

## 7.1 Problem

Agents repeat safe read-only calls. Repeating those calls wastes time, API quota, and tokens. Aperture should avoid repeated work when safe.

## 7.2 Core policy

Caching is deny-by-default.

A tool call is cacheable only if all are true:

1. Tool is classified as read-only/idempotent.
2. Tool is not auth/session/connection management.
3. Tool is not a write/mutation.
4. Cache scope is known.
5. TTL is defined.
6. Params can be normalized safely.
7. Response status is success.

## 7.3 Cache safety matrix

| Operation | Cache? | Notes |
|---|---:|---|
| Get public repo metadata | Yes | Public or account scoped depending auth |
| List public issues | Yes | Short TTL |
| Search private emails | Yes | Exact only, account scoped, short TTL |
| Read private email | Yes | Exact only, account scoped, short TTL |
| Send email | No | Write |
| Create GitHub issue | No | Write |
| Delete file | No | Write |
| OAuth connect | No | Auth |
| Refresh token | No | Auth |
| Calendar availability | Maybe | Account scoped, very short TTL |
| Web search | Maybe | TTL depends on freshness needs |

## 7.4 Cache flow

```text
Before underlying tool execution:
  1. Read tool_slug, params, context.
  2. Check bypass.
  3. Load cache policy.
  4. If not cacheable: emit not_cacheable event; execute normally.
  5. Build scoped exact key.
  6. Redis GET key.
  7. If hit: emit hit event; return cached payload.
  8. If miss: execute normally.
  9. If success and cacheable: Redis SET key with TTL.
  10. Emit miss event with stored=true.
```

## 7.5 Cache key format

```text
aperture:{version}:{scope}:{tool_slug}:{param_hash}
```

Examples:

```text
aperture:v1:public:GITHUB_GET_REPO:sha256(...)
aperture:v1:account:ca_123:GMAIL_SEARCH_EMAILS:sha256(...)
aperture:v1:user:user_456:SLACK_LIST_CHANNELS:sha256(...)
```

## 7.6 Cache scope rules

| Scope | Required identifier | Used for |
|---|---|---|
| `public` | none | Truly public data only |
| `project` | `project_id` | Project-scoped shared cache |
| `user` | `user_id` | User-specific data |
| `account` | `connected_account_id` | Private connected-account data |
| `session` | `session_id` | Session-only data |
| `none` | none | Not cacheable |

If required identifier is missing, do not cache.

## 7.7 Parameter normalization

Required behavior:

- Sort dictionary keys recursively.
- Preserve list order unless a field is explicitly order-insensitive.
- Remove explicitly ignored metadata fields such as `aperture_cache_bypass`.
- Preserve user query strings exactly by default.
- Do not lowercase arbitrary strings unless tool-specific rules approve it.
- Include version number in key to allow future invalidation.

## 7.8 Bypass methods

Support at least one in MVP:

```text
Header: X-Aperture-Cache-Bypass: true
```

Optional:

```json
{
  "aperture_cache_bypass": true
}
```

## 7.9 Public functions

```python
def load_cache_policy(tool_slug: str) -> CachePolicy:
    """Return cache policy for tool, defaulting to not cacheable."""


def normalize_params(tool_slug: str, params: dict) -> dict:
    """Return deterministic normalized params for exact-match keying."""


def build_cache_key(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    policy: CachePolicy,
) -> str | None:
    """Return scoped cache key or None if unsafe/impossible."""


async def maybe_execute_with_cache(
    tool_slug: str,
    params: dict,
    context: ExecutionContext,
    execute_fn,
):
    """Return cached result on hit; otherwise execute and store if safe."""
```

## 7.10 Required tests

### Unit tests

- Policy defaults unknown tools to not cacheable.
- Write tools are not cacheable.
- Same params in different key order produce same key.
- Different account IDs produce different keys.
- Missing account ID prevents account-scoped caching.
- Bypass skips cache lookup.
- Failed responses are not cached.
- Cached response includes metadata but preserves original payload.

### Integration tests

- Cache miss calls execution function exactly once.
- Cache hit does not call execution function.
- TTL is set in Redis.
- Cache hit emits event.
- Cache miss emits event.
- Not-cacheable emits event.

### Security regression tests

- `GMAIL_SEARCH_EMAILS` results never appear under public scope.
- `GITHUB_CREATE_ISSUE` is never cached.
- `COMPOSIO_MANAGE_CONNECTIONS` is never cached.
- Connected account ID is included for account-scoped tools.

## 7.11 Definition of done

This component is done when:

- Approved safe read tools can be cached.
- Writes/auth tools are impossible to cache under policy.
- Cache hit avoids external execution.
- Cache events report hit/miss/bypass/not-cacheable.
- Developers can bypass cache.
- Unit, integration, and security tests pass.

---

# 8. Component C — Schema Token Optimization

## 8.1 Problem

Tool descriptions and parameter descriptions cost tokens every time they are shown to the LLM. Some descriptions are verbose. Shorter descriptions can save tokens, but only if the agent still uses the tools correctly.

## 8.2 Unique Aperture contribution

Aperture does not simply shorten text. It creates a measured and validated optimization pipeline:

1. Measure schema token cost.
2. Rank high-impact schemas.
3. Generate compact rewrites.
4. Validate behavior.
5. Accept only safe rewrites.
6. Produce before/after reports.

## 8.3 What may be changed

Allowed:

- Tool description text
- Parameter description text
- Enum description text
- Redundant examples if behavior is preserved
- Repeated verbose wording

Not allowed without explicit review:

- Tool slug
- Parameter names
- Required fields
- Types
- Auth requirements
- Execution behavior
- Return schema
- Safety-critical warnings

## 8.4 Optimization algorithm

```text
For each tool schema:
  1. Extract description fields.
  2. Count original tokens.
  3. Estimate impact = token_count × usage_frequency.
  4. Rank candidates.
  5. Generate candidate rewrites.
  6. Validate against test prompts.
  7. Accept candidate only if validation passes.
  8. Save report and diff.
```

## 8.5 Rewrite patterns

### Pattern 1 — Verbose prose to compact imperative

Before:

```text
Creates a new issue in a specified GitHub repository.
```

After:

```text
Create a GitHub issue.
```

### Pattern 2 — Required/optional structure

Before:

```text
You must provide the repository owner username, repository name, and issue title. Optionally, you may include a body and labels.
```

After:

```text
Required: owner, repo, title. Optional: body, labels.
```

### Pattern 3 — Remove redundant type wording

Before:

```text
A string containing the title of the issue.
```

After:

```text
Issue title.
```

### Pattern 4 — Preserve disambiguation

Keep wording that helps distinguish:

- Send email vs create draft
- Create issue vs create pull request
- Query database vs get page
- List messages vs send message
- Upload file vs download file

## 8.6 Validation cases

Validation case format:

```json
{
  "case_id": "github_create_issue_001",
  "user_prompt": "Create a GitHub issue in composioHQ/composio titled 'Fix login bug' and label it bug.",
  "expected_tool": "GITHUB_CREATE_ISSUE",
  "expected_required_params": {
    "owner": "composioHQ",
    "repo": "composio",
    "title": "Fix login bug"
  },
  "expected_optional_params_present": ["labels"],
  "forbidden_tools": ["GITHUB_CREATE_PULL_REQUEST"]
}
```

## 8.7 Validation dimensions

| Dimension | Pass condition |
|---|---|
| Tool selection | Optimized schema selects same tool as original/expected |
| Required params | Required params are present and correct |
| Optional params | Optional params are included/excluded correctly |
| Disambiguation | Similar tools are not confused |
| Edge cases | Unusual but valid prompts still work |
| Real prompts | Historical prompts still work where available |

## 8.8 Public functions

```python
def extract_description_fields(schema: dict) -> list[SchemaField]:
    """Return tool/parameter/enum description fields with field paths."""


def count_schema_field_tokens(field: SchemaField, model: str | None = None) -> int:
    """Count tokens in a schema description field."""


def generate_rewrite_candidates(field: SchemaField) -> list[str]:
    """Return compact candidate rewrites."""


def validate_schema_candidate(
    original_schema: dict,
    candidate_schema: dict,
    validation_cases: list[ValidationCase],
) -> ValidationResult:
    """Return behavior validation result."""


def produce_schema_optimization_report(results: list[SchemaOptimizationResult]) -> str:
    """Return Markdown/JSON report."""
```

## 8.9 Required tests

### Unit tests

- Description fields are extracted correctly.
- Token counts are deterministic.
- Rewrite candidates do not modify parameter names.
- Rewrite candidates do not modify required fields.
- Report includes original and optimized counts.

### Validation tests

- Accepted rewrite passes all validation cases.
- Rewrite causing wrong tool selection is rejected.
- Rewrite omitting important optional parameter description is rejected.
- Similar-tool disambiguation cases pass.

### Regression tests

- Known dangerous compression examples are rejected.
- Safety-critical wording is preserved or flagged for manual review.

## 8.10 Definition of done

This component is done when:

- Top 25 schemas are measured.
- Top 25 optimization candidates are generated.
- Every accepted rewrite has validation evidence.
- Every rejected rewrite has a reason.
- Before/after savings report exists.
- No execution behavior fields are changed.

---

# 9. Benchmark Suite

## 9.1 Purpose

The benchmark suite proves Aperture’s value and catches regressions.

It should answer:

- How many tokens did Composio contribute before and after?
- How many API calls did caching avoid?
- Did optimized schemas preserve tool behavior?
- Did latency improve on cache hits?
- Where did Aperture not help?

## 9.2 Benchmark modes

| Mode | Description |
|---|---|
| `baseline` | Vanilla Composio behavior |
| `observed` | Token attribution only |
| `cached` | Token attribution + cache |
| `optimized` | Token attribution + cache + optimized schemas |

## 9.3 Required workflows

At minimum:

1. GitHub issue triage
2. GitHub repo metadata lookup
3. Gmail search and summarize
4. Calendar availability lookup
5. Notion page lookup
6. Slack search digest
7. Tool-discovery-heavy workflow
8. Large-result workflow using Workbench

## 9.4 Metrics captured

```json
{
  "workflow_name": "github_issue_triage",
  "mode": "cached",
  "total_input_tokens_contributed": 8120,
  "meta_tool_calls": 6,
  "underlying_tool_calls": 4,
  "cache_hits": 2,
  "cache_misses": 2,
  "api_calls_avoided": 2,
  "estimated_tokens_saved_by_cache": 1900,
  "latency_ms_total": 8420,
  "tool_selection_accuracy": 1.0,
  "parameter_accuracy": 1.0
}
```

## 9.5 Required reports

1. `baseline_token_cost_sample.md`
2. `cache_savings_report.md`
3. `schema_optimization_report.md`
4. `aperture_mvp_benchmark.md`

## 9.6 Definition of done

Benchmarking is done when:

- All required workflows run in all required modes.
- Reports include successes and failures.
- Token savings are measured, not guessed.
- Cache hit/miss behavior is visible.
- Schema behavior validation is included.

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

    observability/
      __init__.py
      serializers.py
      token_counter.py
      tokenizer_registry.py
      event_schema.py
      event_emitter.py
      aggregations.py
      reports.py
      api.py

    cache/
      __init__.py
      policy.py
      policy.yaml
      normalizer.py
      key_builder.py
      redis_store.py
      interceptor.py
      bypass.py
      safety.py
      reports.py

    schema_optimizer/
      __init__.py
      fetch_schemas.py
      extract_fields.py
      tokenize_schemas.py
      rank_candidates.py
      rewrite_rules.py
      candidate_generator.py
      validator.py
      diff_writer.py
      reports.py
      fixtures/
        validation_cases.jsonl

    benchmarks/
      __init__.py
      runner.py
      metrics.py
      report.py
      workflows/
        github_issue_triage.py
        github_repo_lookup.py
        gmail_search_summary.py
        calendar_availability.py
        notion_page_lookup.py
        slack_search_digest.py
        tool_discovery_heavy.py
        workbench_large_result.py

  tests/
    observability/
      test_serializers.py
      test_token_counter.py
      test_event_emitter.py
    cache/
      test_policy.py
      test_normalizer.py
      test_key_builder.py
      test_interceptor.py
      test_safety.py
    schema_optimizer/
      test_extract_fields.py
      test_rewrite_rules.py
      test_validator.py
      test_reports.py
    benchmarks/
      test_runner.py
    integration/
      test_token_event_flow.py
      test_cache_flow.py

  docs/
    architecture.md
    integration_map.md
    token_attribution.md
    caching_policy.md
    schema_optimizer.md
    benchmark_methodology.md
    security_privacy.md
    follow_on_roadmap.md

  reports/
    .gitkeep
```

---

# 11. Coding Agent Task Cards

Each task card is designed to be assigned to one coding agent.

---

## Task A1 — Build stable payload serializer

### Goal

Create deterministic serialization for token counting.

### Inputs

- Any Python object / JSON-like payload

### Output

- Deterministic string

### Files

- `aperture/observability/serializers.py`
- `tests/observability/test_serializers.py`

### Requirements

- Sort keys recursively.
- Use compact separators.
- Preserve Unicode.
- Handle dataclasses if used.
- Handle non-JSON values by converting safely or raising clear error.

### Tests

- Same dict with different key order serializes identically.
- Nested dict key ordering is stable.
- Unicode text survives.
- Empty dict/list works.

### Definition of done

Serializer is deterministic and tests pass.

---

## Task A2 — Build token counter

### Goal

Count tokens for serialized Composio payloads.

### Files

- `aperture/observability/token_counter.py`
- `aperture/observability/tokenizer_registry.py`
- `tests/observability/test_token_counter.py`

### Requirements

- Accept payload and optional model.
- Use tokenizer registry.
- Fallback safely for unknown models.
- Return token count and tokenizer name.
- Do not fail on large payloads.

### Definition of done

Token counter works for known and unknown models and emits deterministic counts.

---

## Task A3 — Build token event emitter

### Goal

Create and emit `TokenAttributionEvent` objects.

### Files

- `aperture/observability/event_schema.py`
- `aperture/observability/event_emitter.py`
- `tests/observability/test_event_emitter.py`

### Requirements

- Define event dataclass or Pydantic model.
- Validate required fields.
- Support pluggable sink: in-memory for tests, DB/log sink for integration.
- Avoid raw payload storage.

### Definition of done

Events can be created, validated, and written to a test sink.

---

## Task A4 — Hook token attribution into meta-tool responses

### Goal

Emit token events whenever Composio returns a meta-tool response.

### Files

- Depends on actual Composio hook points
- `docs/integration_map.md`
- `tests/integration/test_token_event_flow.py`

### Requirements

- Identify response hook points.
- Count payload before returning it.
- Do not mutate payload.
- Include project/user/session/meta-tool metadata.

### Definition of done

Simulated or real meta-tool responses produce token events.

---

## Task B1 — Build cache policy loader

### Goal

Load cacheability rules from YAML.

### Files

- `aperture/cache/policy.yaml`
- `aperture/cache/policy.py`
- `tests/cache/test_policy.py`

### Requirements

- Unknown tools default to not cacheable.
- Invalid policy fails clearly.
- Write/auth tools are non-cacheable.
- TTL required for cacheable tools.

### Definition of done

Policy loader is deny-by-default and tested.

---

## Task B2 — Build parameter normalizer and key builder

### Goal

Produce stable exact-match keys.

### Files

- `aperture/cache/normalizer.py`
- `aperture/cache/key_builder.py`
- `tests/cache/test_normalizer.py`
- `tests/cache/test_key_builder.py`

### Requirements

- Sort dict keys recursively.
- Preserve list order.
- Remove Aperture-only metadata.
- Include cache scope.
- Return `None` if scope identifiers are missing.

### Definition of done

Equivalent params produce same key; private scopes cannot collide.

---

## Task B3 — Build Redis cache store

### Goal

Provide simple get/set cache operations with TTL.

### Files

- `aperture/cache/redis_store.py`
- `tests/cache/test_redis_store.py`

### Requirements

- `get(key)`
- `set(key, value, ttl_seconds)`
- `delete(key)` optional
- JSON serialization for values
- Testable with fake/in-memory store if Redis unavailable

### Definition of done

Store supports TTL behavior and test fake exists.

---

## Task B4 — Build cache interceptor

### Goal

Wrap tool execution with cache lookup/store behavior.

### Files

- `aperture/cache/interceptor.py`
- `aperture/cache/bypass.py`
- `tests/cache/test_interceptor.py`
- `tests/cache/test_safety.py`

### Requirements

- Check bypass.
- Check policy.
- Build scoped key.
- Return cached result on hit.
- Execute and store on miss.
- Emit cache events.
- Do not cache failed responses.

### Definition of done

Cache hit avoids execution and all safety tests pass.

---

## Task C1 — Fetch and inventory schemas

### Goal

Create baseline inventory of tool schemas.

### Files

- `aperture/schema_optimizer/fetch_schemas.py`
- `aperture/schema_optimizer/extract_fields.py`
- `tests/schema_optimizer/test_extract_fields.py`

### Requirements

- Fetch schemas from registry/API/source.
- Extract all description fields.
- Preserve field paths.
- Output JSON inventory.

### Definition of done

Schema fields can be listed with tool slug and field path.

---

## Task C2 — Tokenize and rank schema fields

### Goal

Identify highest-impact schema fields.

### Files

- `aperture/schema_optimizer/tokenize_schemas.py`
- `aperture/schema_optimizer/rank_candidates.py`

### Requirements

- Count tokens per field.
- Join with usage frequency if available.
- Rank by estimated impact.
- Produce top candidates report.

### Definition of done

Top 25 optimization candidates are identified.

---

## Task C3 — Generate rewrite candidates

### Goal

Produce compact candidate descriptions.

### Files

- `aperture/schema_optimizer/rewrite_rules.py`
- `aperture/schema_optimizer/candidate_generator.py`
- `tests/schema_optimizer/test_rewrite_rules.py`

### Requirements

- Apply rule-based rewrites.
- Do not touch non-description fields.
- Produce multiple candidates if useful.
- Flag safety-critical text.

### Definition of done

Candidate rewrites are shorter and structurally safe.

---

## Task C4 — Validate schema candidates

### Goal

Reject rewrites that change agent behavior.

### Files

- `aperture/schema_optimizer/validator.py`
- `aperture/schema_optimizer/fixtures/validation_cases.jsonl`
- `tests/schema_optimizer/test_validator.py`

### Requirements

- Run validation cases.
- Compare tool selection.
- Compare required parameter presence.
- Compare optional parameter behavior where test defines it.
- Reject on behavior difference.

### Definition of done

Validator accepts safe rewrites and rejects unsafe rewrites in tests.

---

## Task C5 — Generate schema optimization report

### Goal

Produce reviewable before/after report and diffs.

### Files

- `aperture/schema_optimizer/reports.py`
- `aperture/schema_optimizer/diff_writer.py`
- `reports/schema_optimization_report.md`

### Requirements

- Include original tokens.
- Include optimized tokens.
- Include reduction percent.
- Include validation pass/fail.
- Include rejection reasons.

### Definition of done

Human reviewer can approve/reject schema diffs from report.

---

## Task D1 — Build benchmark runner

### Goal

Run workflows in multiple modes and compare results.

### Files

- `aperture/benchmarks/runner.py`
- `aperture/benchmarks/metrics.py`
- `aperture/benchmarks/report.py`
- `tests/benchmarks/test_runner.py`

### Requirements

- Support modes: baseline, observed, cached, optimized.
- Capture metrics.
- Produce JSON and Markdown report.
- Allow mocked workflow execution for tests.

### Definition of done

Benchmark runner produces comparable mode reports.

---

# 12. Multi-Agent Work Breakdown

## 12.1 Recommended agents

| Agent | Focus | Primary output |
|---|---|---|
| Architecture Agent | Integration discovery | `docs/integration_map.md` |
| Observability Agent | Token counting/events/API | `observability/*` |
| Cache Agent | Cache policy/key/store/interceptor | `cache/*` |
| Schema Agent | Schema inventory/rewrite/validation | `schema_optimizer/*` |
| QA Agent | Tests, benchmarks, safety gates | `tests/*`, `benchmarks/*` |
| Docs Agent | Developer docs and reports | `docs/*`, `reports/*` |
| Review Agent | Security/privacy/code review | Review notes and approvals |

## 12.2 Parallelization plan

### Phase 1 can run in parallel

- Architecture Agent maps hook points.
- Observability Agent builds standalone serializer/token counter/event models.
- Cache Agent builds policy/key/store standalone.
- Schema Agent builds offline inventory/tokenization pipeline.
- QA Agent prepares test fixtures.

### Phase 2 depends on architecture map

- Observability Agent hooks into real response paths.
- Cache Agent hooks into real execution path.
- Benchmark Agent runs realistic workflows.

### Phase 3 depends on metrics

- Schema Agent ranks by real token/call data.
- Docs Agent writes final reports.

## 12.3 Dependency graph

```text
Integration map
   ├── Token response hooks
   │      └── Token attribution integration
   ├── Multi-execute hook
   │      └── Cache interceptor integration
   └── Schema registry access
          └── Schema optimizer fetch/diff

Serializer ─┬─ Token counter ─┬─ Token events ─┬─ Aggregations
            │                 │                └─ Benchmark metrics
            │                 └─ Schema tokenization
            └─ Cache payload token estimate

Cache policy ─ Key builder ─ Redis store ─ Cache interceptor ─ Cache reports

Schema inventory ─ Rewrite candidates ─ Validator ─ Schema report
```

---

# 13. Implementation Timeline

## Week 1 — Ground truth and foundations

### Goals

- Confirm integration points.
- Build standalone primitives.
- Produce baseline token-cost sample.

### Deliverables

- `docs/integration_map.md`
- Stable serializer
- Token counter
- Cache policy loader
- Cache key builder
- Schema field extractor
- Baseline sample report

### Gate

Do not proceed to runtime integration until hook points are identified or a wrapper/proxy fallback is chosen.

---

## Week 2 — Token attribution MVP

### Goals

- Emit token attribution events for meta-tool responses.
- Query or report token contribution.

### Deliverables

- Token event emitter
- Token response hook integration
- Token aggregation/report
- Tests passing

### Gate

At least three payload kinds must emit token events in dev/test.

---

## Week 3 — Cache MVP

### Goals

- Exact-match cache for approved read-only tools.
- Cache hit/miss events.

### Deliverables

- Redis/fake cache store
- Cache interceptor
- Bypass support
- Safety tests
- Initial cache report

### Gate

Writes/auth tools must be proven non-cacheable by tests.

---

## Week 4 — Schema baseline and top candidates

### Goals

- Measure schema token cost.
- Rank optimization candidates.

### Deliverables

- Schema inventory
- Field-level token report
- Top 25 candidate list
- Validation fixture structure

### Gate

No schema rewrite is accepted without validation cases.

---

## Week 5 — Schema rewrite and validation

### Goals

- Optimize top 25 schemas.
- Validate behavior.

### Deliverables

- Rewrite candidates
- Validator
- Accepted/rejected report
- Diffs for review

### Gate

Accepted rewrites must pass all validation cases.

---

## Week 6 — Benchmarks and reports

### Goals

- Run before/after workflows.
- Produce final MVP proof.

### Deliverables

- Benchmark runner
- Workflow reports
- Token/cache/schema savings report
- Known limitations

### Gate

Reports must separate measured results from estimates.

---

## Week 7 — Hardening

### Goals

- Fix issues found by benchmarks.
- Strengthen tests and docs.

### Deliverables

- Security/privacy review checklist
- Regression tests
- Improved docs
- Final demo flow

---

## Week 8 — Final delivery

### Goals

- Ship polished MVP artifacts.
- Prepare follow-on roadmap.

### Deliverables

- Final technical report
- Demo
- Handoff docs
- Follow-on roadmap

---

# 14. Configuration

## 14.1 Aperture config

```yaml
aperture:
  enabled: true
  version: "0.1.0"

  observability:
    enabled: true
    store_raw_payloads: false
    default_tokenizer: "cl100k_base"
    emit_token_events: true

  cache:
    enabled: true
    mode: "conservative"
    redis_url_env: "REDIS_URL"
    bypass_header: "X-Aperture-Cache-Bypass"
    default_unknown_tools_cacheable: false

  schema_optimizer:
    enabled: true
    validation_required: true
    top_n: 25
    allow_parameter_name_changes: false
    allow_required_field_changes: false
```

## 14.2 Cache policy example

```yaml
version: 1

default:
  cacheable: false
  operation_type: unknown
  privacy_scope: none
  ttl_seconds: null
  matching: none
  reason: "deny_by_default"

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
    reason: "write_operation"
```

---

# 15. API / Reporting Shape

## 15.1 Token usage query

```http
POST /api/v3.1/project/usage/input_tokens_contributed
```

Example request:

```json
{
  "group_by": "meta_tool_slug",
  "dt_gt": "2026-05-01T00:00:00Z",
  "dt_lt": "2026-05-08T00:00:00Z",
  "order_by": "total_input_tokens_contributed",
  "order_direction": "desc"
}
```

Example response:

```json
{
  "results": [
    {
      "meta_tool_slug": "COMPOSIO_SEARCH_TOOLS",
      "total_input_tokens_contributed": 412000,
      "calls": 220,
      "avg_tokens_per_call": 1872
    }
  ]
}
```

## 15.2 Cache savings query

```http
POST /api/v3.1/project/usage/cache_savings
```

Example response:

```json
{
  "results": [
    {
      "tool_slug": "GITHUB_LIST_ISSUES",
      "cache_hits": 120,
      "cache_misses": 300,
      "hit_rate": 0.2857,
      "api_calls_avoided": 120,
      "estimated_tokens_saved": 184000
    }
  ]
}
```

## 15.3 Schema optimization report output

```json
{
  "run_id": "schema_opt_2026_05_08",
  "tools_analyzed": 1000,
  "fields_analyzed": 6200,
  "candidates_generated": 75,
  "accepted_rewrites": 25,
  "rejected_rewrites": 50,
  "total_original_tokens": 8200,
  "total_optimized_tokens": 5100,
  "total_reduction_tokens": 3100,
  "average_reduction_pct": 37.8
}
```

---

# 16. Quality Gates

## 16.1 Gate 1 — Measurement correctness

Pass criteria:

- Token counts are deterministic.
- Unknown model fallback works.
- Events include metadata.
- Reports are generated.

Fail if:

- Token counting mutates payloads.
- Token event misses session/project metadata.
- Raw sensitive payloads are stored unexpectedly.

## 16.2 Gate 2 — Cache safety

Pass criteria:

- Writes are never cached.
- Private data is scoped.
- Bypass works.
- Failed responses are not cached.

Fail if:

- Any write tool can be cached.
- Private cache key omits account/user scope.
- Cache hit can occur across private accounts.

## 16.3 Gate 3 — Schema behavior preservation

Pass criteria:

- Accepted rewrites pass validation.
- Required fields unchanged.
- Tool selection unchanged.
- Diffs are reviewable.

Fail if:

- Parameter names/types change accidentally.
- Similar tools become confused.
- Validation cases are missing.

## 16.4 Gate 4 — Benchmark honesty

Pass criteria:

- Reports show measured values.
- Estimates are labeled.
- Failures/limitations included.

Fail if:

- Savings are guessed without measurement.
- Only cherry-picked workflows are reported.

---

# 17. Security and Privacy Requirements

## 17.1 Cache requirements

- Never cache auth tokens.
- Never cache OAuth responses.
- Never cache write responses unless explicitly approved later; MVP says no.
- Never use public scope for private tools.
- Never log raw cache keys; log key hashes only.
- Never use semantic matching for private execution results in MVP.

## 17.2 Observability requirements

- Token events should not store raw payloads by default.
- Store payload byte size and token count.
- Follow existing project/user/session access boundaries.
- Respect existing retention policies.
- Redact sensitive metadata in reports.

## 17.3 Schema optimizer requirements

- Preserve safety-critical wording unless manually reviewed.
- Keep original descriptions available for rollback.
- Every accepted rewrite must be traceable to validation results.

---

# 18. Failure Modes and Mitigations

| Failure mode | Severity | Mitigation |
|---|---:|---|
| Cache serves stale result | High | Short TTLs, bypass, conservative policy |
| Cache leaks private data | Critical | Account/user scoped keys, safety tests |
| Write accidentally cached | Critical | Deny-by-default, operation type tests |
| Token count differs from provider billing | Medium | Label as Composio-contributed estimate |
| Schema rewrite worsens tool use | High | Validation suite, manual review |
| No internal hook access | High | Build wrapper/report-only fallback |
| Cache hit rate low | Medium | Still useful observability; tune policy later |
| Schema optimizer overcompresses | High | Preserve disambiguation, reject on validation |
| Reports expose sensitive data | High | Metadata-only reports, redaction |

---

# 19. Human Review Checklist

Before merging:

## Token attribution

- [ ] Counts are deterministic.
- [ ] Payloads are not mutated.
- [ ] Metadata is complete.
- [ ] Sensitive payloads are not stored.

## Cache

- [ ] Policy is deny-by-default.
- [ ] Write/auth tools are blocked.
- [ ] Private scopes include account/user ID.
- [ ] TTLs are reasonable.
- [ ] Bypass works.

## Schema optimization

- [ ] Required fields unchanged.
- [ ] Parameter names unchanged.
- [ ] Types unchanged.
- [ ] Validation cases pass.
- [ ] Rewrites are understandable.
- [ ] Rollback path exists.

## Benchmarks

- [ ] Baseline included.
- [ ] Before/after values measured.
- [ ] Limitations included.
- [ ] Failures not hidden.

---

# 20. Final Deliverables

## Code deliverables

- Token serializer/counter
- Token event emitter
- Token aggregations/reporting
- Cache policy loader
- Cache key normalizer
- Redis/fake cache store
- Cache interceptor
- Schema inventory/tokenization pipeline
- Schema rewrite generator
- Schema validator
- Benchmark runner

## Document deliverables

```text
docs/integration_map.md
docs/architecture.md
docs/token_attribution.md
docs/caching_policy.md
docs/schema_optimizer.md
docs/security_privacy.md
docs/benchmark_methodology.md
docs/follow_on_roadmap.md
```

## Report deliverables

```text
reports/baseline_token_cost_sample.md
reports/cache_savings_report.md
reports/schema_optimization_report.md
reports/aperture_mvp_benchmark.md
reports/final_handoff.md
```

---

# 21. Follow-On Roadmap

## Phase 2 — Semantic `SEARCH_TOOLS` caching

Cache shared schema/plan portions of search-tool responses for semantically equivalent queries.

Rules:

- Do not cache connection status cross-user.
- Do not cache private auth state.
- Separate shared schema/plan data from user-specific status.

## Phase 3 — Session state compression SDK

Build opt-in framework helpers that:

- Store structured session state
- Limit message history to last N turns
- Inject state summary
- Update state after tool calls

Do not claim automatic compression unless the orchestrator actually truncates history.

## Phase 4 — Plan quality scoring

Start with optional explicit session outcome events and conservative heuristics.

Do not auto-prune plans until:

- Enough executions exist
- Scores are reliable
- Human review is available

## Phase 5 — Continuous schema optimization

Run optimizer in CI whenever schemas are added or changed.

---

# 22. Perfect Coding-Agent Prompt

Use this prompt when assigning an agent a task from this plan:

```md
You are working on Aperture, a token-efficiency layer for Composio agents.

Follow these rules:
- Be conservative and safety-first.
- Do not cache writes or auth operations.
- Do not share private data across users/accounts.
- Do not store raw sensitive payloads unless explicitly allowed.
- Do not modify schema behavior; only optimize descriptions after validation.
- Add tests for every module.
- End with a handoff: completed, files changed, tests run, assumptions, unknowns, next task.

Your task:
[INSERT TASK CARD]

Relevant contracts:
[INSERT DATA CONTRACTS]

Definition of done:
[INSERT DEFINITION OF DONE]
```

---

# 23. Final MVP Definition

Aperture MVP is complete when:

1. Composio-originated payloads are token-counted and attributed.
2. Developers can query/report token contribution by session/meta-tool/toolkit/tool/date.
3. Approved safe read-only calls can be cached with exact-match Redis keys.
4. Cache hit/miss/bypass/not-cacheable events are emitted.
5. Writes/auth/private data are protected by policy and tests.
6. Top 25 schema optimization candidates are measured, rewritten, validated, and reported.
7. Benchmark workflows show measured before/after impact.
8. Final docs and handoff are complete.

---

# 24. One-Page Summary for Reviewers

Aperture is an efficiency layer for Composio agents. It does three things:

1. **Measures token cost**  
   Counts Composio-contributed input tokens from meta-tool responses, schemas, results, plans, and workbench outputs.

2. **Caches safe repeated calls**  
   Uses conservative exact-match Redis caching for approved read-only tools with strict user/account scoping, TTLs, and bypass.

3. **Optimizes schemas safely**  
   Shortens tool descriptions and parameter descriptions only when validation shows tool selection and parameter behavior are preserved.

The MVP avoids risky claims and risky features. It does not do arbitrary semantic result caching, automatic context compression, cross-tenant private caching, or total LLM billing attribution. It focuses on measured, safe, high-value improvements that can be built and evaluated by coding agents.

