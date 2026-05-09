# Aperture — V1 Realignment Handoff

**Audience:** teammates and coding agents picking this codebase up to make it match `APERTURE_PROJECT_PLAN-v1.md`.
**Scope:** components A, B, C only. Components D (Session State Compressor) and E (Plan Quality Scorer) are out of scope and should not be built.
**Tone:** blunt. The current branch is far from the v1 plan. This document tells you exactly how far, why, and what to do about it.
**Branch state at write time:** `demo` at commit `96fd573` (merge of `2a0a4fa` "fixed transparency" onto `fbd5f1c` "validate live Aperture integration").

---

## 0. Bottom line, in one paragraph

This codebase is not the project v1 described. v1 specified a token-efficiency layer that intercepts Composio's six meta tools (`COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_MULTI_EXECUTE_TOOL`, etc.) and ships three things on top: a cross-agent execution cache, a token attribution observability layer that extends Composio's `/api/v3.1/usage/...` API, and an offline schema description rewriter. What got built is a userspace wrapper around `composio.Composio.tools.execute(...)` that does *output compression* on individual tool results, plus a single-tenant exact-match Redis cache, plus a custom FastAPI dashboard. The compression layer (large, well-engineered, ~4,000 LOC) is a project v1 never asked for. The cache wraps the wrong layer. The schema "optimizer" is a parameter-block one-liner, not a description rewriter. The observability layer emits events to JSONL traces, not to v1's specified `v3.1`-shape API. Approximately half the Python in `aperture/` solves problems v1 didn't pose, while the v1 components A and C are implemented at the wrong level or in the wrong shape, and v1's foundational Week 1 task (a real-token-cost baseline measured against real Composio session logs) was never done. The benchmarks save 75.5% on synthetic fixtures — a number v1 §5 explicitly warned not to present as a measured fact.

This handoff explains the gap, names every concrete file and line that is wrong, lays out two alignment paths (a strict v1-shaped MCP proxy and a pragmatic userspace reframe), recommends the proxy path, and gives a week-by-week rebuild plan with acceptance criteria.

---

## 1. The single most important fact: the architectural level is wrong

Read this section before anything else. Every other gap follows from it.

### 1.1 What v1 said the project would intercept

v1 §3 names the surface explicitly:

> The six meta tools (verified from reference docs): `COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_GET_TOOL_SCHEMAS`, `COMPOSIO_MULTI_EXECUTE_TOOL`, `COMPOSIO_MANAGE_CONNECTIONS`, `COMPOSIO_REMOTE_WORKBENCH`, `COMPOSIO_REMOTE_BASH_TOOL`.

v1 §4A says the cache "intercepts `COMPOSIO_MULTI_EXECUTE_TOOL` calls for read-heavy, idempotent operations before they reach the external API. … Also applies to `COMPOSIO_SEARCH_TOOLS` responses — same search query across many agents generates redundant round-trips today."

v1 §4B says token attribution "tokenizes meta-tool response payloads at emission point" and emits events keyed by `meta_tool_slug`.

v1 §4C says the schema optimizer rewrites the description fields returned by `COMPOSIO_GET_TOOL_SCHEMAS` and `COMPOSIO_SEARCH_TOOLS`.

**The entire v1 plan is keyed on intercepting these six meta tools.** Everything else (the API endpoints, the network-effect math, the repo structure, the privacy story) is downstream of that interception.

### 1.2 What the codebase actually intercepts

Run this grep yourself and confirm. From the repo root:

```bash
grep -r "MULTI_EXECUTE\|SEARCH_TOOLS\|GET_TOOL_SCHEMAS\|REMOTE_WORKBENCH\|REMOTE_BASH" aperture/ api/ scripts/ tests/
```

Result: **zero matches.** The six meta tools are not referenced anywhere in the implementation. The only meta-tool reference in any Python file is in `aperture/cache/policy.py:64-65`:

```python
# Auth
"COMPOSIO_MANAGE_CONNECTIONS",
"COMPOSIO_INITIATE_CONNECTION",
```

Both listed only as never-cacheable. There is no interception of any meta-tool flow.

What the code wraps is the regular Composio SDK at `aperture/agent/composio_agent.py:489-492`:

```python
def execute_live():
    return client.tools.execute(
        slug, args, user_id=user_id,
        dangerously_skip_version_check=True,
    )
```

`client.tools.execute()` is the SDK's high-level call to execute one tool by slug. It does *not* expose the meta-tool layer that v1 wanted to instrument. The agent loop also calls `client.tools.get(user_id=..., tools=[...])` (`composio_agent.py:349`) to fetch tool schemas — this is the SDK's helper that returns Anthropic-shaped tool definitions, not the meta-tool `COMPOSIO_GET_TOOL_SCHEMAS` response.

Look at `scripts/honest_comparison.py:53-78` — the "vanilla Composio" example that the codebase contrasts itself against. It uses:

```python
session = c.create(user_id=..., toolkits=["googlesheets"], connected_accounts={...})
resp = session.execute(tool_slug="GOOGLESHEETS_BATCH_GET", arguments={...})
```

Note `session.execute(tool_slug=...)`. This is the Composio SDK's session-style execution path. The MCP URL Composio returns from session creation, the meta-tool dispatch flow that runs inside Composio's Tool Router, the actual `MULTI_EXECUTE_TOOL` call wire format — none of that is observed by Aperture. The cache, attribution, and compression all sit *outside* Composio, between the user's agent code and the SDK call.

### 1.3 Why this matters

It matters because every v1 design decision was downstream of intercepting meta tools:

1. **v1's "cross-agent" cache is impossible at this level.** A cache that wraps `client.tools.execute()` in one developer's process cannot share hits with another developer's process. The v1 vision — "100,000 active developers … 60–80% hit rate within hours of platform usage" — requires the cache to live inside Composio's infrastructure where requests from all customers converge. The current cache is *single-tenant*; it can never be cross-agent.

2. **v1's token attribution endpoints can't be Composio-shaped.** v1 §4B specified `POST /api/v3.1/project/usage/input_tokens_contributed` to match Composio's existing `/api/v3.1/project/usage/{entity_type}` API. The codebase exposes `/api/...` endpoints in a custom shape (`api/main.py`). A developer using vanilla Composio cannot query Aperture's data through Composio's SDK; they have to talk to a separate Aperture HTTP server.

3. **v1's schema optimizer can't actually commit results to the registry.** v1 §4C Step 5 says "Commit accepted rewrites to registry, keep original descriptions in a `description_verbose` field, tag with `aperture_optimized: true`". The Composio registry is internal to Composio. Without internal access (which v1 §7 listed as an open question), Aperture cannot land its rewrites where every Composio session would benefit. The code instead returns a one-line compact form that a *developer's* code could substitute, but only if they explicitly opt in per session.

4. **v1's privacy story doesn't apply.** v1 §5 spent a whole section on "cross-agent caching may conflict with Composio's enterprise privacy commitments." That risk is moot when the cache is single-tenant. But the *flip side* is moot too: the network effect that justified the project is also gone. A single-tenant exact-match cache is a fine local optimization, but it isn't the lever v1 was after.

5. **v1's success metrics are not measurable.** §11 listed cache hit rate "across MULTI_EXECUTE calls" as a must-have metric. The codebase doesn't see MULTI_EXECUTE calls. This metric cannot be reported.

### 1.4 Why this happened (educated guess from the artifacts)

Two plausible reasons, neither documented:

**(a) No internal Composio access.** v1 §7 question 1 asks: *"Does Composio's Tool Router run as a monolith or microservices? Which service handles MULTI_EXECUTE_TOOL? Where would the cache interceptor live?"* If the team never got an answer (no internal access), the only place left to put the interceptor is userspace.

**(b) The "Phases 1–4" pivot.** `TRANSFER.md` describes a different project: task-aware compression, lazy hydration, prompt-cache optimization, upstream field selection. The v1 project plan is not mentioned in `TRANSFER.md`; the doc reads as if the team forked off a separate roadmap. About half the code in `aperture/compression/` (`task_profiles.py`, `hydration.py`, `prompt_cache.py`, `field_profiles.py`) belongs to this Phases-1-to-4 project, not v1.

Whatever the reason, the result is the same: the codebase is a different project than v1 with v1's name attached.

### 1.5 What to do about it

You have to pick one of two paths. The rest of this document treats Path 1 as the recommended path. Path 2 is documented for completeness in §11.

**Path 1 (recommended): build an MCP proxy that gives Aperture visibility into the meta-tool layer from outside Composio.** This is the path that lets v1 actually be implemented. Detailed in §11 and §12.

**Path 2: explicitly reframe the project as a userspace SDK wrapper, accept that v1's framing was wrong, and rewrite the plan to match.** This is honest but means the v1 doc gets retired.

If the team chose Path 1 in spirit but never built the proxy, then the rest of this document is the playbook. If the team is actually doing Path 2, stop here and rewrite the plan — there is no point chasing v1 metrics on a userspace tool.

---

## 2. Reading map

You can read this document linearly or jump to what you need:

- §3 — What the codebase has today, organized by v1 lens
- §4 — v1 Component A (cache): every divergence with file/line
- §5 — v1 Component B (attribution): every divergence with file/line
- §6 — v1 Component C (schema optimizer): every divergence with file/line
- §7 — v1 §3 (Composio architecture context): how the code maps
- §8 — Files: keep / refactor / delete (every Python file, decided)
- §9 — Target repository structure
- §10 — Migration strategy (don't break the demo while pivoting)
- §11 — Two paths forward, in detail
- §12 — Week-by-week rebuild plan
- §13 — Acceptance criteria per component
- §14 — Test plan
- §15 — Risk register (specific to this realignment)
- §16 — Open questions that block progress
- §17 — Appendices: contracts, endpoints, YAML, prompts

---

## 3. State of the codebase as of `96fd573`

### 3.1 Inventory by directory

```
aperture/
  __init__.py                          version "0.1.0"; trivial
  config.py                            Upstash Redis client + env loading; KEEP
  contracts.py                         dataclasses; needs rewrite to v1 names
  integration.py                       ApertureRunner; the wiring point; refactor heavily
  adapters/
    langgraph.py                       not in v1; ignore for now (don't delete; harmless)
  agent/
    composio_agent.py        831 LOC   userspace agent loop; out of scope for v1
    tool_cache.py            196 LOC   process-local cache; duplicate of cache/; DELETE
  benchmarks/
    harness.py                         mode-matrix benchmark; refactor to v1 modes
    vanilla_vs_aperture.py             3-scenario fixture benchmark; partially keep
  cache/
    interceptor.py                     CachedExecutor; rebuild as v1 interceptor
    key_builder.py                     scoped key; needs v1 key format (v1: prefix, scope-id)
    policy.py                          ~30 tools; needs to expand to 1000+ via YAML
    store.py                           Upstash + memory; KEEP, rename to redis_store.py
  compression/                          NOT IN V1 AT ALL — see §3.3
    engine.py                714 LOC   output compression
    field_classifier.py      667 LOC   model-assisted field promotion
    field_policy.py          224 LOC   denial-list + promotion logic
    field_profiles.py                  upstream field selection (TRANSFER.md Phase 4)
    hydration.py                       lazy placeholders (TRANSFER.md Phase 2)
    prompt_cache.py                    multi-tier prompt caching (TRANSFER.md Phase 3)
    task_profiles.py                   task-aware fields (TRANSFER.md Phase 1)
    rtk_inspired.py                    ultra-summary + tier marker
    stopwords.py                       caveman pruning
    toon.py                            tabular encoding
  demo/
    agent_simulator.py                 pre-Anthropic demo
    mock_data.py                       fixture generators
    scenarios.py                       fixture scenarios
  observability/
    events.py                          token + cache event emission; partially align
    trace.py                           run trace export; KEEP
  routing/                              NOT IN V1 — see §3.3
    effort_modes.py                    low/medium/high/auto
    intelligent_effort.py              auto-effort picker
    quality_gate.py                    signal-preserving mode picker
    selector.py                        intent → effort
    semantic_selector.py               embedding-based selector
  schema_optimizer/
    auto_profile.py          328 LOC   payload-shape profile generator (NOT v1)
    type_group.py                      parameter-block compaction (NOT v1)
                                       v1's description rewriter is ABSENT
  tokenization/
    counter.py                         tiktoken wrapper; partially align
    serializers.py                     stable_json_dumps; KEEP
    budget_manager.py                  context budget tracking; not in v1 but useful

api/main.py                            27 endpoints; will rebuild against v3.1 shape
dashboard/app.py                       Streamlit demo; deprioritize
frontend/                              React/Vite; deprioritize, only Demo+Overview kept
data/                                  fixture datasets; KEEP for now
scripts/                               benchmarks + demos; refactor to v1 weekly tasks
tests/                                 180 tests; rewrite test plan
docs/                                  v1 plan + v3 plan + Spokane reviews; KEEP
```

### 3.2 Total code by direction

Roughly:

- **In v1's direction** (cache, attribution, schema_optimizer, tokenization, observability core): ~1,800 LOC. Half of it is wrong-shape and needs rewrite.
- **Not in v1, but useful** (compression engine core, routing, contracts): ~1,500 LOC. Decision: defer or extract out as a separate library, do not delete.
- **Not in v1, not core** (frontend, dashboard, agent, TRANSFER.md phases 1–4): ~6,000 LOC. Decision: freeze, don't touch during realignment.

### 3.3 Things that exist that v1 didn't ask for

Be honest about this. They are not bad code, but they are scope creep relative to v1:

| Module / area | LOC | Belongs to | Decision |
|---|---|---|---|
| `aperture/agent/composio_agent.py` | 831 | Live demo project | Freeze; don't extend |
| `aperture/agent/tool_cache.py` | 196 | Duplicate of `cache/` | DELETE |
| `aperture/compression/engine.py` | 714 | Output compression (not v1) | Keep but de-couple from v1 path |
| `aperture/compression/field_classifier.py` | 667 | TRANSFER project | Freeze |
| `aperture/compression/{hydration, prompt_cache, field_profiles, task_profiles}.py` | ~600 | TRANSFER Phases 1–4 | Freeze |
| `aperture/compression/{rtk_inspired, stopwords, toon}.py` | ~350 | Compression sub-features | Freeze |
| `aperture/routing/*.py` | 1,100 | Auto-effort routing (not v1) | Freeze |
| `aperture/schema_optimizer/auto_profile.py` | 328 | Payload-shape profiles (not v1) | Move to `aperture/compression/`; this is a compression feature, not schema optimization |
| `aperture/schema_optimizer/type_group.py` | 130 | Parameter-block compaction (related but not v1) | Move to `aperture/schema_optimizer/v0_param_compaction.py`; document as a separate kind of optimization |
| `dashboard/app.py` (Streamlit) | 908 | Demo dashboard | Freeze; don't extend |
| `frontend/` 14 pages | ~5,000 | Demo dashboard | Freeze; trim to 2 pages once v1 work lands |

The phrase "Freeze; don't extend" means: the file stays on disk, the existing tests still run, but **no new feature work goes into it**. After v1 components land you can decide what to keep.

---

## 4. Component A — Cross-Agent Execution Cache: every divergence

This section walks every paragraph of v1 §4A and matches it to a file/line. Anywhere the code disagrees with the plan, the disagreement is named and the fix is given.

### 4.1 v1 said: cache intercepts `COMPOSIO_MULTI_EXECUTE_TOOL` and `COMPOSIO_SEARCH_TOOLS`

**Reality:** Cache wraps `client.tools.execute()` at `aperture/cache/interceptor.py:18-100`, called from `aperture/integration.py:87-92` and `aperture/agent/composio_agent.py:495-505`. There is no `COMPOSIO_MULTI_EXECUTE_TOOL` interception. There is no `COMPOSIO_SEARCH_TOOLS` cache (no SEARCH_TOOLS query → schema/plan caching of any kind).

**Why it's wrong:** Single-tenant. No cross-agent sharing possible. Doesn't see meta-tool traffic. SEARCH_TOOLS (the most-called meta tool per v1 §3) gets zero benefit.

**Fix:**

- **For Path 1 (MCP proxy):** the cache must live inside the proxy and key off the meta-tool envelope. When the LLM sends a `COMPOSIO_MULTI_EXECUTE_TOOL` call, the proxy intercepts it before forwarding to Composio. See §11.1 for proxy architecture.
- **For Path 2 (userspace):** explicitly redefine v1's "cross-agent" as "cross-process within one developer's tenant," document the limit, and remove the cross-tenant network-effect claims from any pitch.

### 4.2 v1 said: two-tier lookup — Redis exact key, then Qdrant semantic search at threshold 0.95, namespaced by `tool_slug`

**Reality:** `aperture/cache/interceptor.py:67-80` does `self.store.get(cache_key)` (Redis only, exact-match). No Qdrant. No semantic fallback. Grep `qdrant` repo-wide: zero matches.

**Why it's wrong (only partially):** v1 §8 explicitly endorsed Redis-only for v1 of this component and said Qdrant is v2. So missing Qdrant is on-plan for v1-of-v1. **But:** Qdrant was supposed to be reserved for SEARCH_TOOLS query caching — and SEARCH_TOOLS caching is missing entirely, so even the v1-of-v1 cut shouldn't ship without at least the Redis-only SEARCH_TOOLS cache for *exact* query strings.

**Fix:** keep Redis-only for MULTI_EXECUTE. Add an exact-match SEARCH_TOOLS query → response cache (Redis-only) immediately. Defer Qdrant. Detailed file plan in §8 and §12.

### 4.3 v1 said: cache key design must use exact-match for user-specific output, write ops, and time-sensitive output

**Reality:** `aperture/cache/policy.py:51-66` has a `_NEVER_CACHE` set covering writes (`GITHUB_CREATE_ISSUE`, `GMAIL_SEND_EMAIL`, etc.) and auth (`COMPOSIO_MANAGE_CONNECTIONS`, `COMPOSIO_INITIATE_CONNECTION`). `aperture/cache/policy.py:76-89` defines `get_cache_scope()` returning `"public"` for `GITHUB_GET_REPO`/`GITHUB_GET_A_REPOSITORY`/`GITHUB_SEARCH_REPOS` and `"account"` for everything else.

**Why it's partially wrong:**

1. v1 calls out three policy categories: write, user-specific, time-sensitive. The code only encodes two (cacheable / never-cache) and a binary scope (public / account). v1's STATIC / DYNAMIC / LIVE / PRIVATE / WRITE category system is absent.
2. v1 says `GMAIL_SEARCH_EMAILS` is PRIVATE with a 5-minute TTL. The code has it cacheable with a 60-second TTL (`policy.py:95`) which is fine but doesn't match v1's category language.
3. v1 says the TTL config "must ship as a maintained config file" (§4A and §14). The code keeps TTL as Python substring rules in `get_cache_ttl()` at `policy.py:92-101` — `if "SLACK" in tool_slug or "GMAIL" in tool_slug: return 60`. Brittle.

**Fix:** introduce `aperture/cache/policy.yaml`. Define the v1 categories. Per-tool entries. See §17.3 for the YAML schema.

### 4.4 v1 said: namespace isolation — every key prefixed by `user_id` for private, `PUBLIC` for cross-user

**Reality:** `aperture/cache/key_builder.py:35-56` uses scopes: `public`, `ca:{connected_account_id}`, `u:{user_id}`, `t:{tenant_id}`. Format: `aperture:cache:{scope}:{tool_slug}:{args_hash}`.

**Why it's partially right and partially wrong:**

- ✅ Private data has scope-id prefix. Good.
- ✅ Public scope returns `None` if a connected_account is present. (`key_builder.py:36-40`) Good.
- ❌ The keys are missing v1's policy version segment. v1 §17 in this doc and the SPOKANE review both note the cache key has no `v1:` prefix and no schema version — meaning when a Composio tool changes its response shape, old cache entries silently keep being served. The code has `schema_version` and `api_version` fields in `CacheEvent` (`contracts.py:78-79`) but they're never populated.
- ❌ The format does not match v1's specified shape `aperture:v1:{scope}:{scope_id}:{tool_slug}:{sha256(...)}` (v3 plan §8.4 — but v1's text strongly implies a similar form). The code has `aperture:cache:{scope}:{tool_slug}:{hash}`, which is fine functionally but breaks if you ever introduce v2 keys.

**Fix:** rename prefix to include version and policy version. New format:

```
aperture:v1:p1:{scope}:{scope_id}:{tool_slug}:{sha256(normalized_params)}
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              full sha256, not first 16 chars
```

`p1` is the policy YAML version. When the YAML version bumps, all keys invalidate automatically. Concrete migration in §8.

### 4.5 v1 said: SEARCH_TOOLS response caching must split schema+plan (shareable) from connection status (per-user)

**Reality:** No SEARCH_TOOLS caching exists. So this entire concern doesn't manifest. But when you build it (per §11.1, §12 Week 4), you must respect this split.

**Fix specification:** when caching `COMPOSIO_SEARCH_TOOLS` responses (Path 1 in the proxy), the cache key for the *schema + plan* portion should be:

```
aperture:v1:p1:public:none:SEARCH_TOOLS:sha256(query_string_normalized)
```

Connection status portion is fetched fresh per request and merged into the response before returning to the LLM. The proxy assembles the merged response.

### 4.6 v1 said: full TTL classification for 1,000+ Composio tools

**Reality:** `aperture/cache/policy.py:4-66` lists ~30 tools, hand-coded in Python. Tools added to Composio after this file was written are deny-by-default (good for safety, bad for utility — the cache can never hit on new tools without code changes).

**Why it's wrong:** v1 §4A: "The full 1,000-tool TTL config is real work — probably 2–3 days of classification, but it only needs to be done once and maintained as tools are added." That work hasn't been done.

**Fix:** §17.3 has a YAML schema. Initial population strategy:

1. Run `client.tools.list()` (the SDK helper that returns all tool metadata) once and dump the slugs to a JSON file: `aperture/cache/_seed_tool_list.json`.
2. Auto-classify by slug pattern:
   - Contains `_CREATE_`, `_UPDATE_`, `_DELETE_`, `_SEND_`, `_REMOVE_`, `_MERGE_`, `_CLOSE_`, `_REOPEN_`, `_COMMENT_`, `_REPLY_`, `_ASSIGN_`, `_INVITE_`, `_PUBLISH_`, `_POST_`, `_PUT_`, `_PATCH_` → category `WRITE`, `cacheable: false`
   - Contains `GMAIL_`, `SLACK_`, `LINEAR_`, `NOTION_` *not* matching above + read verb → `PRIVATE`, TTL 5 min, account scope
   - Contains `GITHUB_GET_`, `GITHUB_SEARCH_REPOS` → `STATIC`, TTL 2 hours, public scope when no connected account present
   - Contains `GITHUB_LIST_` → `DYNAMIC`, TTL 15 min, account scope
   - Contains `GOOGLESHEETS_BATCH_GET`, `SUPABASE_FETCH_TABLE_ROWS` → `DYNAMIC`, TTL 10 min, account scope
   - Default → `cacheable: false` (deny by default)
3. Hand-review the auto-classification against the seed list, edit YAML, commit.
4. Verify every cacheable entry has TTL and scope set; v1 §4A risk register is explicit that missing scope must prevent caching, and the code already enforces this at `key_builder.py:42-54` — keep it that way.

Acceptance criterion: the YAML covers ≥80% of the seed tool list (writes auto-deny, reads explicitly classified). Use `tests/cache/test_policy_yaml.py` to assert no tool in the seed list is missing a category.

### 4.7 v1 said: cache bypass via `X-Aperture-Cache-Bypass: true` header

**Reality:** Bypass is a `cache_bypass: bool` field on `ApertureRunConfig` at `aperture/contracts.py:26`. Honored at `interceptor.py:34-44`. No HTTP header parsing module.

**Why it's wrong:** v1 §4A: "Need a cache bypass header / parameter for time-sensitive sessions." The header form matters because it's the way an LLM-facing proxy can be told "this turn don't serve from cache" without rewriting the request body. In a userspace SDK the field is sufficient. In a proxy (Path 1), the header is necessary.

**Fix (Path 1):** add `aperture/cache/bypass.py` with a parser for the header and the metadata field. Wire it into the proxy's request entry point. See §17.4.

**Fix (Path 2):** keep the field, document it as the only mechanism, drop the header from v1 plan claims.

### 4.8 v1 said: only cache `status: success` responses; validate response schema before caching

**Reality:** `aperture/cache/interceptor.py:108-115`:

```python
def _success_response(response: object) -> bool:
    if isinstance(response, dict):
        if response.get("success") is False:
            return False
        if response.get("error"):
            return False
    return True
```

✅ Success-only caching is implemented. Failed-response test exists at `tests/test_cache.py:101-123`.

❌ "Validate response schema before caching" is not implemented. The code caches anything dict-like that isn't an explicit failure.

**Fix:** add a per-tool optional response schema in the YAML (`response_schema_check: enabled | disabled`), run a JSON-Schema validator on the payload before storing. For v1 of v1, just a sanity check (e.g., for `GITHUB_GET_REPO` assert `name` and `id` exist). For v2, full JSON-Schema.

### 4.9 v1 said: cache poisoning mitigations — don't cache failed/corrupted results, validate response shape

✅ Failed responses not cached (above).
❌ Corruption check not implemented.

**Fix:** see §4.8.

### 4.10 v1 said: semantic collision risk — keep semantic matching to SEARCH_TOOLS only, threshold ≥0.95

**Reality:** No semantic matching anywhere. Risk doesn't manifest. **Build it Qdrant-only for SEARCH_TOOLS in v2 (per v1 §8).**

### 4.11 Summary of Component A status

| v1 sub-spec | File | Verdict |
|---|---|---|
| Intercepts MULTI_EXECUTE meta tool | n/a | ❌ wrong layer (intercepts SDK call) |
| Intercepts SEARCH_TOOLS responses | n/a | ❌ not built |
| Redis exact-match v1 | `cache/store.py:39-95` | ✅ works, single-tenant only |
| Qdrant semantic v2 (SEARCH_TOOLS only) | n/a | ❌ not built (deferred per plan, OK) |
| Namespace `user_id`/`PUBLIC` prefixes | `cache/key_builder.py:35-54` | ⚠️ similar shape, missing version segment |
| Full 1000+ tool TTL config | `cache/policy.py:4-101` | ❌ ~30 tools, Python substring rules |
| TTL config "ships as maintained config file" | n/a | ❌ Python, not YAML |
| Cache bypass header | n/a | ❌ field-based only |
| Cache only success responses | `cache/interceptor.py:108-115` | ✅ |
| Validate response schema before caching | n/a | ❌ |
| `(connected_account_id)` part of user-scoped keys | `key_builder.py:42-44` | ✅ |
| Cache hit returns `CachedResult(data, age, original_cost_tokens)` | `interceptor.py:67-80` | ⚠️ returns raw value + CacheEvent; no `age`, no `original_cost_tokens` field |

Eight gaps. Fix list mapped to weeks in §12.

---

## 5. Component B — Token Attribution Observability: every divergence

### 5.1 v1 said: tokenize meta-tool response payloads at emission point

**Reality:** Tokenizes individual tool result payloads at `aperture/integration.py:138-149` (token event for compressed result) and arguments at `integration.py:59-70` (token event for arguments). Meta-tool responses are not seen, so cannot be tokenized.

**Fix (Path 1):** the proxy tokenizes every meta-tool response before forwarding to the LLM. `meta_tool_slug` is the response envelope's outermost identifier (`COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_GET_TOOL_SCHEMAS`, `COMPOSIO_MULTI_EXECUTE_TOOL`). The wrapped tool inside MULTI_EXECUTE is a separate `tool_slug`.

The event must therefore carry **both** `meta_tool_slug` and `tool_slug`:

```python
@dataclass
class TokenAttributionEvent:
    ...
    meta_tool_slug: str        # one of: SEARCH_TOOLS, MULTI_EXECUTE_TOOL, GET_TOOL_SCHEMAS, ...
    tool_slug: str | None      # populated for MULTI_EXECUTE; None for others
    ...
```

The current `TokenEvent` at `aperture/contracts.py:87-103` has only `tool_slug` and `toolkit_slug`. It needs a `meta_tool_slug` field.

### 5.2 v1 said: tiktoken for OpenAI, Anthropic tokenizer for Claude, cl100k_base fallback

**Reality:** `aperture/tokenization/counter.py:42-55` lists Claude models in the registry but maps them all to `cl100k_base` and sets `approximate=True`:

```python
"claude-opus-4-7": "cl100k_base",
"claude-opus-4-6": "cl100k_base",
...
```

**Why it's wrong:** v1 §8 says "Anthropic's tokenizer for Claude models". Anthropic publishes a tokenizer endpoint (`POST /v1/messages/count_tokens` since 2024) and a `count_tokens` SDK method. `approximate=True` is correct for the cl100k fallback, but a real Anthropic tokenizer should be tried first when the SDK is available.

**Fix:** add a thin wrapper:

```python
# aperture/tokenization/anthropic_tokenizer.py
import anthropic
_client: anthropic.Anthropic | None = None

def count_anthropic_tokens(payload: object, model: str) -> int:
    """Use Anthropic's official tokenizer.

    Falls back to None on error; caller should use cl100k_base fallback.
    """
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    text = payload if isinstance(payload, str) else _stable_json(payload)
    try:
        resp = _client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
        )
        return resp.input_tokens
    except Exception:
        return None
```

In `counter.py`, when model starts with `claude-`, try Anthropic count first, fall back to cl100k. Mark `approximate=False` only when Anthropic count succeeded.

This adds a network call per token count, which is too slow for hot paths. So:
- Cache results in Redis keyed by `sha256(text) + model` for 24 hours.
- Allow opt-out via `APERTURE_USE_ANTHROPIC_TOKENIZER=false`.
- Fall back silently if no `ANTHROPIC_API_KEY`.

### 5.3 v1 said: emit event `{session_id, meta_tool_slug, input_tokens_contributed, timestamp}`

**Reality:** Current event shape from `aperture/contracts.py:87-103`:

```python
@dataclass
class TokenEvent:
    event_type: str             # schema | argument | result | compressed | cache
    run_id: str
    toolkit_slug: str | None
    tool_slug: str | None
    payload_kind: str           # schema | argument | result | compressed | cache
    model: str | None
    tokenizer: str
    approximate: bool
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    compression_ratio: float | None
    cache_status: str | None
```

**Divergences:**

1. v1 calls the field `input_tokens_contributed`. Code uses `raw_tokens` and `compressed_tokens`. The semantic is *almost* the same — `input_tokens_contributed` is what the meta tool added to the LLM's input context, which after compression is `compressed_tokens`. But the rename matters because v1's API endpoints use `input_tokens_contributed` as the entity name.
2. v1 has `session_id`. Code has `run_id`. Different concept — v1 means a Composio session (a tool router session). `run_id` is a per-Aperture-execution identifier.
3. No `meta_tool_slug` field.
4. `event_type` and `payload_kind` overlap confusingly. v1 doesn't specify either.

**Fix:** rewrite `TokenEvent` to match v1's `TokenAttributionEvent`:

```python
@dataclass(frozen=True)
class TokenAttributionEvent:
    event_type: str            # "meta_tool_response" | "argument" | "result" | "compressed" | "cache_hit_savings"
    timestamp: str             # ISO 8601 UTC
    project_id: str | None
    user_id: str | None
    session_id: str | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    payload_kind: str          # "schema" | "execution_result" | "plan" | "compressed_result"
    model: str | None
    tokenizer: str
    tokenizer_is_approximate: bool
    raw_payload_bytes: int | None
    compressed_payload_bytes: int | None
    raw_tokens: int | None
    compressed_tokens: int | None
    input_tokens_contributed: int          # what the meta tool added to LLM input context
    tokens_saved: int
    compression_ratio: float | None
    cache_status: str | None
    aperture_version: str
```

This is the v3 execution plan §5.3 contract. Honor it. The current `TokenEvent` is missing 11 of these fields.

### 5.4 v1 said: model parameter from `COMPOSIO_SEARCH_TOOLS` selects tokenizer

**Reality:** Model is passed through `ApertureRunConfig.model` at construction (`contracts.py:24`) and used at `tokenization/counter.py:79-92`. There's no read of the `model` parameter from a SEARCH_TOOLS call because SEARCH_TOOLS isn't intercepted.

**Fix (Path 1):** when the proxy sees a `COMPOSIO_SEARCH_TOOLS` call with a `model` param in the payload, capture that as the session's model and use it for all subsequent tokenizations in that session.

### 5.5 v1 said: new `/api/v3.1/project/usage/input_tokens_contributed` endpoint

**Reality:** Custom FastAPI surface in `api/main.py` with 27 endpoints; none match the v1 shape. No `/v3.1/project/usage/...` path.

**Fix:** add a v3.1-shaped subset. New file: `aperture/observability/api_endpoints.py` (matches v1 §9 repo structure). Mount it at `/api/v3.1/project/usage/...`. See §17.2 for exact payloads.

### 5.6 v1 said: group_by `meta_tool_slug`, `toolkit_slug`, `session_turn`, `user_id`, `date`

**Reality:** Some grouping in dashboard. None matches the API shape v1 wants. `session_turn` is not tracked anywhere — there is no concept of a "session turn" in the current event model.

**Fix:** add `session_turn: int` to `TokenAttributionEvent`. Increment it per assistant→tool→assistant cycle in the proxy or, in userspace mode, expose `runner.next_turn()`.

### 5.7 v1 said: cache_tokens_saved entity

**Reality:** Cache events do carry `tokens_saved_estimate` at `aperture/contracts.py:82`. There's a `/api/cache/stats` endpoint in `api/main.py:702-755`. There's no `cache_tokens_saved` entity in v3.1 shape.

**Fix:** add the entity-shape endpoint per v1 §4B last code block:

```
POST /api/v3.1/project/usage/cache_tokens_saved
{
  "group_by": "tool_slug",
  "dt_gt": "2026-05-01T00:00:00Z"
}
```

Returns aggregated `tokens_saved_estimate` from cache events grouped per the request.

### 5.8 v1 said: aggregate by user/toolkit/tool/session/date — bucketed time series

**Reality:** No time bucketing. Events are stored as JSONL via `RunTrace.export_jsonl()` at `observability/trace.py:48-52`.

**Fix:** add an aggregator that consumes events and produces hourly/daily buckets. Storage choice:

- v1-of-v1: SQLite. One table `attribution_events`, one table `cache_events`. Aggregations are SQL queries. Lightweight, no infra.
- v2: Postgres or whatever the team decides.

The aggregator file v1 specified is `aperture/observability/aggregator.py`.

### 5.9 Summary of Component B status

| v1 sub-spec | Reality | Verdict |
|---|---|---|
| Tokenize meta-tool responses | tokenizes individual tool results | ❌ wrong layer |
| tiktoken for OpenAI | yes | ✅ |
| Anthropic tokenizer for Claude | falls back to cl100k_base, marked approximate | ⚠️ partial |
| cl100k_base fallback | yes | ✅ |
| Per-event field `input_tokens_contributed` | called `raw_tokens` / `compressed_tokens` | ❌ rename needed |
| Field `meta_tool_slug` | absent | ❌ |
| Field `session_id` | called `run_id`, different semantics | ❌ |
| Field `session_turn` | absent | ❌ |
| Field `aperture_version` | absent | ❌ |
| Field `payload_bytes` (raw and compressed) | absent | ❌ |
| API: `/api/v3.1/project/usage/input_tokens_contributed` | absent | ❌ |
| API: `/api/v3.1/project/usage/cache_tokens_saved` | absent | ❌ |
| Group by meta_tool_slug | not in API | ❌ |
| Group by session_turn | not tracked | ❌ |
| Time bucketing on aggregations | absent | ❌ |
| Token cost report — top expensive tools | dashboard renders this; not as a v1 report | ⚠️ partial |
| Real-session baseline (Week 1 of v1 plan) | not done | ❌ |

Of 17 specific v1 commitments, 14 are missing or wrong. The Component B engineering work is the largest single chunk in the realignment.

---

## 6. Component C — Schema Tokenizer Optimizer: every divergence

This is the most missing component. The plan is detailed; the code has nothing for it.

### 6.1 v1 said: pull all schemas from Composio registry

**Reality:** No schema-fetcher script exists. The agent loop at `aperture/agent/composio_agent.py:337-358` uses `client.tools.get(user_id=..., tools=[wanted_slugs])` to fetch tool schemas for execution, but that is per-session, returns Anthropic-shaped tools, and is not stored. There's no offline pipeline that pulls and persists every tool schema.

**Fix:** new file `aperture/schema_optimizer/fetch_schemas.py`:

```python
"""Pull all Composio tool schemas via the SDK and persist them as JSON."""

import json
from pathlib import Path
from composio import Composio

OUT = Path(__file__).parent / "_schemas.json"

def fetch_all() -> list[dict]:
    """Fetch every tool schema from Composio.

    Returns a list of normalized schema dicts:
        [{"slug": "GITHUB_LIST_ISSUES", "toolkit": "github", "description": "...",
          "parameters": {...}, "required": [...]}, ...]
    """
    client = Composio()
    # composio.tools.list() returns metadata; we then need full schemas via
    # composio.tools.get(tools=[slug, ...]) in batches.
    all_tools = client.tools.list()       # returns lightweight metadata
    slugs = [t.slug for t in all_tools]
    schemas: list[dict] = []
    for i in range(0, len(slugs), 50):
        batch = slugs[i:i + 50]
        full = client.tools.get(tools=batch)
        for tool in full:
            schemas.append({
                "slug": tool["name"],
                "toolkit": tool["name"].split("_", 1)[0].lower(),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            })
    OUT.write_text(json.dumps(schemas, indent=2, sort_keys=True))
    return schemas

if __name__ == "__main__":
    schemas = fetch_all()
    print(f"Fetched {len(schemas)} schemas → {OUT}")
```

Run once. Commit `_schemas.json` to the repo (it's small — couple MB). Re-run weekly via cron or whenever Composio's changelog notes new tools.

### 6.2 v1 said: tokenize every description field, sort by `tokens × frequency`

**Reality:** Not done.

**Fix:** new file `aperture/schema_optimizer/extract_fields.py`:

```python
"""Extract every description field from every schema."""

from dataclasses import dataclass

@dataclass(frozen=True)
class SchemaField:
    tool_slug: str
    field_path: str           # "description" | "parameters.properties.owner.description" | ...
    text: str
    is_top_level: bool        # True for tool description, False for param descriptions

def extract_fields(schema: dict) -> list[SchemaField]:
    out: list[SchemaField] = []
    slug = schema["slug"]
    if schema.get("description"):
        out.append(SchemaField(slug, "description", schema["description"], True))
    props = schema.get("parameters", {}).get("properties", {}) or {}
    for name, defn in props.items():
        if isinstance(defn, dict) and defn.get("description"):
            path = f"parameters.properties.{name}.description"
            out.append(SchemaField(slug, path, defn["description"], False))
    return out
```

Then `aperture/schema_optimizer/tokenize_schemas.py`:

```python
"""Token-count every schema field."""

from aperture.tokenization import count_tokens
from aperture.schema_optimizer.extract_fields import SchemaField

@dataclass(frozen=True)
class FieldTokenCount:
    field: SchemaField
    tokens: int
    tokenizer: str

def tokenize_field(field: SchemaField, model: str = "gpt-4o") -> FieldTokenCount:
    tc = count_tokens(field.text, model=model)
    return FieldTokenCount(field=field, tokens=tc.tokens, tokenizer=tc.tokenizer)
```

Then `aperture/schema_optimizer/rank_candidates.py`:

```python
"""Rank fields by (tokens × estimated_call_frequency) descending."""

# call_frequency.json is produced by Week 1 of v1 — real Composio session log analysis.
# Until that's done, fall back to estimated frequency by toolkit.
TOOLKIT_FREQ_PRIOR = {
    "github": 1.0, "gmail": 0.7, "slack": 0.5, "notion": 0.4,
    "linear": 0.3, "googlesheets": 0.3, "supabase": 0.2,
}

def rank(token_counts: list[FieldTokenCount]) -> list[FieldTokenCount]:
    def score(fc: FieldTokenCount) -> float:
        tk = fc.field.tool_slug.split("_", 1)[0].lower()
        freq = TOOLKIT_FREQ_PRIOR.get(tk, 0.1)
        return fc.tokens * freq
    return sorted(token_counts, key=score, reverse=True)
```

The ranking is approximate until Week 1 (the real-session baseline) is done. v1 §10 was emphatic that Week 1 must precede Week 5 (schema optimizer). This sequencing is non-negotiable for v1; the optimizer is supposed to optimize the *highest-leverage* descriptions first, and you don't know which those are without real frequency data.

### 6.3 v1 said: rewrite candidates per rules a–e

**Reality:** Not built. v1 lists the rules:

- (a) Strip verbose preambles
- (b) Compress parameter lists
- (c) Remove redundant type annotation prose
- (d) Use imperative mood consistently
- (e) Replace multi-token compound phrases with single-token equivalents

Generate 3 candidate rewrites per field at different compression levels.

**Fix:** new file `aperture/schema_optimizer/rewrite_rules.py`:

```python
"""Generate compact description rewrite candidates.

Three compression levels: light (just rules a, c, d), medium (a, b, c, d),
heavy (a, b, c, d, e). Each is a deterministic regex/heuristic transform.
"""

import re

# Rule (a) — strip verbose preambles
_PREAMBLES = [
    (re.compile(r"^Creates? a new "), "Create a "),
    (re.compile(r"^Sends? an? "), "Send a "),
    (re.compile(r"^Fetches? "), "Fetch "),
    (re.compile(r"^Lists? "), "List "),
    (re.compile(r"^Returns? a "), "Return a "),
    (re.compile(r"^Returns? the "), "Return the "),
    (re.compile(r"^Provides? "), ""),
]

def _apply_preambles(text: str) -> str:
    for pat, repl in _PREAMBLES:
        text = pat.sub(repl, text, count=1)
    return text

# Rule (c) — remove redundant type prose
_TYPE_PROSE = [
    (re.compile(r"\bA string containing the\s+", re.IGNORECASE), ""),
    (re.compile(r"\bA list of\s+", re.IGNORECASE), ""),
    (re.compile(r"\bAn? array of\s+", re.IGNORECASE), ""),
    (re.compile(r"\bProvide a string for the\s+", re.IGNORECASE), ""),
    (re.compile(r"\b\(must be a string\)", re.IGNORECASE), ""),
]

# Rule (b) — collapse "You must provide X, Y, Z. Optionally, you may include..."
_REQUIRED_PROSE = re.compile(
    r"You must (?:provide|specify) (?:the )?([^.]+)\.\s*",
    re.IGNORECASE,
)
_OPTIONAL_PROSE = re.compile(
    r"(?:Optionally|Optional[ly]?),? (?:you may )?(?:include|specify|provide)?\s*([^.]+)\.",
    re.IGNORECASE,
)

# Rule (d) — imperative mood
_INDICATIVE_TO_IMPERATIVE = [
    (re.compile(r"^Sends? "), "Send "),
    (re.compile(r"^Creates? "), "Create "),
    (re.compile(r"^Fetches? "), "Fetch "),
]

def light_rewrite(text: str) -> str:
    out = _apply_preambles(text)
    for pat, repl in _TYPE_PROSE:
        out = pat.sub(repl, out)
    for pat, repl in _INDICATIVE_TO_IMPERATIVE:
        out = pat.sub(repl, out)
    return out.strip()

def medium_rewrite(text: str) -> str:
    out = light_rewrite(text)
    # Apply rule (b) — collapse required/optional prose
    req = _REQUIRED_PROSE.search(out)
    opt = _OPTIONAL_PROSE.search(out)
    if req:
        out = out[:req.start()] + out[req.end():]
        required = req.group(1).strip().rstrip(".").strip()
        out += f" Required: {required}."
    if opt:
        out = out[:opt.start()] + out[opt.end():]
        optional = opt.group(1).strip().rstrip(".").strip()
        out += f" Optional: {optional}."
    return out.strip()

def heavy_rewrite(text: str) -> str:
    out = medium_rewrite(text)
    # Rule (e) — multi-token compound phrases
    out = out.replace("repository", "repo")
    out = out.replace("authenticated user", "user")
    out = out.replace("recipient email address", "recipient")
    return out.strip()

def candidates(text: str) -> list[str]:
    """Return [light, medium, heavy] rewrites. Caller validates each."""
    return [light_rewrite(text), medium_rewrite(text), heavy_rewrite(text)]
```

This is illustrative. The real rule set will need iteration once you can run the validator (next subsection) against real candidates and see which rules cause regressions.

### 6.4 v1 said: semantic equivalence validation — 50 prompts × 3 candidates × 1,000 tools = 150,000 inference calls

**Reality:** Not built.

**Fix:** new file `aperture/schema_optimizer/validator.py`. The hard parts are: (1) where do the 50 prompts come from, (2) how do you measure "same tool selected and same parameters extracted."

For (1) — prompts:
- Ideal: pull real prompts from Week 1 session logs.
- Fallback: synthetic prompts written per toolkit. v1 §4C: "When testing the schema optimizer, use real Composio session logs (from week 1 measurement) as the test prompts — not synthetic prompts."

For (2) — validation:

```python
"""Validate that a schema rewrite preserves agent behavior.

Method: present the original and rewritten schemas to an LLM in separate calls,
ask it to "select the right tool and fill in the parameters" for the same prompt.
Accept the rewrite only if all 50 prompts produce identical tool selection and
parameter extraction.
"""

import anthropic
from dataclasses import dataclass

@dataclass(frozen=True)
class ValidationResult:
    cases_run: int
    cases_passed: int
    cases_failed: list[dict]   # {prompt, expected, got, reason}
    accepted: bool

def validate(
    original_schema: dict,
    candidate_schema: dict,
    prompts: list[str],
    similar_tools: list[dict],   # to test disambiguation
    model: str = "claude-haiku-4-5",
) -> ValidationResult:
    """Run prompts through both schemas. Compare tool selection and params."""
    client = anthropic.Anthropic()
    failed = []

    for prompt in prompts:
        original_pick = _ask_model_pick_tool(client, model, prompt, [original_schema] + similar_tools)
        candidate_pick = _ask_model_pick_tool(client, model, prompt, [candidate_schema] + similar_tools)

        if original_pick != candidate_pick:
            failed.append({
                "prompt": prompt,
                "original": original_pick,
                "candidate": candidate_pick,
                "reason": "tool_selection_or_params_diverged",
            })

    accepted = len(failed) == 0
    return ValidationResult(
        cases_run=len(prompts),
        cases_passed=len(prompts) - len(failed),
        cases_failed=failed,
        accepted=accepted,
    )

def _ask_model_pick_tool(client, model, prompt, tools):
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        tools=tools,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            # Normalize so dict ordering / null fields don't cause spurious diffs
            return {
                "name": block.name,
                "input": _normalize_args(block.input),
            }
    return None

def _normalize_args(args: dict) -> dict:
    """Sort keys, drop None values, lower-case enum values to match Composio."""
    if not isinstance(args, dict):
        return args
    return {k: _normalize_args(v) for k, v in sorted(args.items()) if v is not None}
```

Disambiguation requirement (v1 §4C "Important caveat"): the validator must include "similar tools" in the candidate set. For `GITHUB_CREATE_ISSUE`, include `GITHUB_CREATE_PULL_REQUEST` and `GITHUB_LIST_ISSUES`. The prompt set must include cases that require distinguishing between them.

For the prompt set, build a per-toolkit base set and seed with real prompts when Week 1 data exists. Initial seeds in §17.5.

### 6.5 v1 said: 150k validation calls, $90–150 one-time cost

**Reality:** No budgeting, no validation has happened.

**Fix:** add `aperture/schema_optimizer/budget.py` that tracks token use during validation runs and aborts if it exceeds a configured cap. Default: $50/run. Print a summary at end: "Validated 25 tools, ran 3,750 prompts, spent $42.18."

### 6.6 v1 said: accept only candidates where all 50 prompts produce identical tool selection and parameter extraction

**Reality:** No accept/reject decision logic.

**Fix:** the `ValidationResult.accepted` flag in §6.4 implements this. Be strict: 49/50 is rejected. v1 §4C is explicit ("Accept only candidates where *all* 50 prompts produce identical tool selection").

### 6.7 v1 said: keep original descriptions in `description_verbose`, tag with `aperture_optimized: true` + version

**Reality:** No registry write path. The Composio registry is internal, and we don't have access (probably).

**Fix:** since we cannot land changes in Composio's registry, the optimizer's output is a **proposed schema overlay** — a JSON file that maps `slug → optimized_description` plus metadata:

```json
{
  "version": 1,
  "aperture_optimizer_version": "0.1.0",
  "tools": {
    "GITHUB_CREATE_ISSUE": {
      "description_optimized": "Create a GitHub issue. Required: owner, repo, title. Optional: body, assignees (usernames), milestone (number), labels.",
      "description_verbose": "Creates a new issue in a specified GitHub repository...",
      "validation": {"cases_run": 50, "cases_passed": 50, "accepted": true},
      "savings": {"original_tokens": 68, "optimized_tokens": 28, "reduction_pct": 0.59}
    }
  }
}
```

This file lives at `aperture/schema_optimizer/_overlay.json`. Developers using Aperture can opt in by passing the overlay to their agent's tool list — Aperture provides a helper:

```python
from aperture.schema_optimizer import apply_overlay

tools = client.tools.get(user_id=..., tools=wanted_slugs)
optimized = apply_overlay(tools, "aperture/schema_optimizer/_overlay.json")
# optimized is the same shape as tools, but with rewritten descriptions for any
# slug that has an accepted entry in the overlay.
```

This is **not** v1's vision (v1 wanted Composio-side changes). But until you have internal Composio access, this is the closest you can get. Document the limitation in the produced report.

### 6.8 v1 said: report includes original tokens, optimized tokens, tokens saved, reduction%, validation pass/fail, accepted/rejected, rejection reason

**Reality:** No report module.

**Fix:** new file `aperture/schema_optimizer/reports.py`:

```python
"""Generate the schema optimization report."""

from pathlib import Path
import json

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

def write_schema_report(results: list[SchemaOptimizationResult]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "schema_optimization_report.md"
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    total_savings = sum(r.reduction_tokens for r in accepted)
    md = [
        "# Schema Optimization Report\n",
        f"- Tools processed: {len(results)}",
        f"- Accepted: {len(accepted)}",
        f"- Rejected: {len(rejected)}",
        f"- Total tokens saved per session (across accepted descriptions): {total_savings}",
        "",
        "## Accepted",
        "",
        "| Tool | Field | Original | Optimized | Saved | % | Validation |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in accepted:
        md.append(f"| {r.tool_slug} | {r.field_path} | {r.original_tokens} | "
                  f"{r.optimized_tokens} | {r.reduction_tokens} | {r.reduction_pct:.0%} | "
                  f"{r.validation_cases_run}/{r.validation_cases_run} ✓ |")
    md.append("")
    md.append("## Rejected")
    md.append("")
    md.append("| Tool | Field | Reason |")
    md.append("|---|---|---|")
    for r in rejected:
        md.append(f"| {r.tool_slug} | {r.field_path} | {r.rejection_reason} |")
    out.write_text("\n".join(md))
    return out
```

The `reports/` directory is supposed to exist per v1 §9 but doesn't; this file creates it.

### 6.9 v1 said: integrate as step in tool onboarding pipeline

**Reality:** No integration; not feasible without internal Composio access.

**Fix:** document as a future step. For v1-of-v1, run the optimizer manually on a schedule and produce overlays.

### 6.10 What `aperture/schema_optimizer/` has today (and why it's not what v1 means)

The directory contains:

- `auto_profile.py` (328 LOC) — analyzes a tool's *response payload* to decide which fields to compress. **This is output compression configuration, not schema optimization.** v1's schema optimizer is about the *input schema description*. Move this file to `aperture/compression/auto_profile.py` to clarify.
- `type_group.py` (130 LOC) — compresses the *parameters block* into a one-liner like `GET_REPO(string:owner,repo,ref?;int:per_page?;bool:archived?)`. **This is schema *structural* compaction, not description rewriting.** It's a legitimate optimization but a different one. Move to `aperture/schema_optimizer/v0_param_compaction.py` and document it as an additional optimization that runs alongside (not instead of) the description rewriter.

After the move, `aperture/schema_optimizer/` should look like:

```
aperture/schema_optimizer/
  __init__.py
  _schemas.json                      output of fetch_schemas.py, gitignored or LFS
  _overlay.json                      output of the pipeline, committed
  budget.py                          token budget tracking for validator runs
  extract_fields.py                  per v1 §6.2
  fetch_schemas.py                   per v1 §6.1
  pipeline.py                        orchestrates the full pipeline
  rank_candidates.py                 per v1 §6.2
  reports.py                         per v1 §6.8
  rewrite_rules.py                   per v1 §6.3
  tokenize_schemas.py                per v1 §6.2
  v0_param_compaction.py             current type_group.py, kept for compatibility
  validator.py                       per v1 §6.4
  prompts/
    github.jsonl                     test prompts per toolkit
    gmail.jsonl
    slack.jsonl
    notion.jsonl
    linear.jsonl
```

### 6.11 Summary of Component C status

| v1 sub-spec | Reality | Verdict |
|---|---|---|
| Pull all schemas | not done | ❌ |
| Tokenize all description fields | not done | ❌ |
| Rank by `tokens × frequency` | not done | ❌ |
| Generate 3 candidates per field | not done | ❌ |
| Apply rules a–e | not done | ❌ |
| Run 50-prompt validation per candidate | not done | ❌ |
| Accept only candidates with 100% pass | not done | ❌ |
| Disambiguation tests | not done | ❌ |
| Parameter inference tests | not done | ❌ |
| Edge case tests | not done | ❌ |
| Token reduction measurement | not done | ❌ |
| Commit accepted rewrites to registry | infeasible (no internal access) | ❌ replaced by overlay file |
| `description_verbose` field | not done | ❌ replaced by overlay |
| `aperture_optimized: true` + version | not done | ❌ replaced by overlay metadata |
| Report with before/after, savings, validation | not done | ❌ |
| Run on schedule for new tools | not done | ❌ |
| Headline rewrite example: `GITHUB_CREATE_ISSUE` 68→28 tokens | nowhere in code | ❌ |

**Component C is essentially absent.** What's in `schema_optimizer/` now is unrelated work in the same directory. The signature contribution of v1 — turning verbose descriptions into compact ones — is not implemented in any form.

---

## 7. v1 §3 (Composio architecture context) — how the code maps

Quick reference. v1 §3 describes Composio's six meta tools and the session model. Here's how each one shows up (or doesn't) in code:

### 7.1 The six meta tools

| Meta tool | Purpose per v1 | Code reference | Status |
|---|---|---|---|
| `COMPOSIO_SEARCH_TOOLS` | discovery + plans | none | ❌ never seen by Aperture |
| `COMPOSIO_GET_TOOL_SCHEMAS` | fetch full schemas | none | ❌ never seen by Aperture |
| `COMPOSIO_MULTI_EXECUTE_TOOL` | execute up to 50 tools | none (replaced by `client.tools.execute()` per slug) | ❌ never seen by Aperture |
| `COMPOSIO_MANAGE_CONNECTIONS` | OAuth flows | `cache/policy.py:64` (in NEVER_CACHE) | ⚠️ named, not intercepted |
| `COMPOSIO_REMOTE_WORKBENCH` | Python sandbox | none | n/a not used |
| `COMPOSIO_REMOTE_BASH_TOOL` | bash in sandbox | none | n/a not used |

### 7.2 Session model

v1 §3: "Sessions are created via `POST /api/v3.1/tool_router/sessions` with: `user_id`, `toolkits.enabled`, `tools`, `tags.enabled`/`tags.disabled`, `auth_configs` / `connected_accounts`, `workbench.enable`, `multi_account`, `experimental.assistive_prompt`, `experimental.custom_toolkits`."

**Code:** `scripts/honest_comparison.py:58-64` and `aperture/agent/composio_agent.py:253-269` use `Composio(api_key=...)` and the SDK's session-style helpers. The fields `tags.enabled` (`readOnlyHint`) and `experimental.assistive_prompt` are not used anywhere — and v1 §14 explicitly recommended both as cache-classification hooks. Worth wiring in once the cache lives at the right layer.

### 7.3 The two existing API families

v1 §3:

> Two API families under `/api/v3.1/`:
> - Execution logs (`/logs/tool_calls`)
> - Usage metering (`/project/usage/{entity_type}`)

**Code:** Aperture exposes 27 endpoints under `/api/...` (`api/main.py:131-1198`). None match these v3.1 paths.

If we cannot extend Composio's actual `/api/v3.1` (no internal access), the closest thing is to mount Aperture's API at the same path shape on a different host:

```
https://aperture.example.com/api/v3.1/project/usage/input_tokens_contributed
https://aperture.example.com/api/v3.1/project/usage/cache_tokens_saved
```

Developers query Aperture for token cost; they query Composio for tool counts; the two are joined client-side using `session_id`.

---

## 8. File-by-file disposition

This section names every Python file in `aperture/`, `api/`, `dashboard/`, `scripts/`, and `tests/` and assigns one of: KEEP / KEEP-WITH-CHANGES / RENAME / MOVE / REFACTOR / DELETE / FREEZE. Where changes are needed, the line-level work is named.

### 8.1 `aperture/`

#### Top-level

```
aperture/__init__.py                  KEEP. Bump version to 0.3.0 once realignment lands.
aperture/config.py                    KEEP. Already loads Upstash creds correctly.
aperture/contracts.py                 REFACTOR — rewrite to v1's contract names. See §17.1.
aperture/integration.py               REFACTOR — must split into proxy mode + sdk mode.
                                      The single ApertureRunner class becomes:
                                      - aperture/proxy/handler.py (Path 1)
                                      - aperture/sdk/runner.py (Path 2 / current behavior)
```

#### `aperture/agent/`

```
aperture/agent/composio_agent.py      FREEZE. Out of v1 scope. Don't extend.
                                      Has correct uses of composio.Composio + AnthropicProvider.
                                      Continues to work as the live demo.
aperture/agent/tool_cache.py          DELETE. Duplicate of cache/. Causes confusion in
                                      Spend Studio dashboard. Remove all imports of it.
                                      Files that import it (must be updated):
                                        - aperture/agent/composio_agent.py:27-31
                                        - api/main.py:1170-1186
                                      Replace with calls to the real cache layer.
```

#### `aperture/cache/`

```
aperture/cache/__init__.py            KEEP.
aperture/cache/interceptor.py         REFACTOR — async support, response schema
                                      validation hook, cache hit returns CachedResult
                                      dataclass not raw value.
aperture/cache/key_builder.py         REFACTOR — new key format with v1: + p1: prefix.
                                      Migration: old keys expire naturally. Don't try
                                      to hot-swap.
aperture/cache/policy.py              REPLACE — load from policy.yaml.
aperture/cache/policy.yaml            CREATE — v1 §17.3 schema. Auto-classify on first
                                      run. Hand-review.
aperture/cache/normalizer.py          CREATE — param normalization (sort keys, strip
                                      Aperture metadata, preserve list order).
aperture/cache/store.py               RENAME → redis_store.py. Update all imports.
aperture/cache/redis_store.py         (after rename of store.py).
aperture/cache/qdrant_store.py        CREATE — stub for v2. Implementation deferred.
aperture/cache/bypass.py              CREATE — header parser per §17.4.
```

#### `aperture/observability/`

```
aperture/observability/__init__.py    KEEP.
aperture/observability/events.py      RENAME → event_emitter.py.
                                      REFACTOR to emit TokenAttributionEvent (v1 shape).
aperture/observability/event_schema.py CREATE — the contracts dataclasses extracted here.
aperture/observability/aggregator.py  CREATE — SQL aggregation over event log.
aperture/observability/api_endpoints.py CREATE — /api/v3.1/project/usage/... routes.
aperture/observability/reports.py     CREATE — top_expensive_tools_report and friends.
aperture/observability/trace.py       KEEP. Its JSONL export is still useful.
```

#### `aperture/schema_optimizer/`

```
aperture/schema_optimizer/__init__.py KEEP. Add `apply_overlay` re-export.
aperture/schema_optimizer/auto_profile.py MOVE → aperture/compression/auto_profile.py.
                                      It's compression configuration, not schema work.
                                      Update imports in api/main.py:37 and tests.
aperture/schema_optimizer/type_group.py RENAME → v0_param_compaction.py.
                                      Document in README that this is a separate
                                      optimization (parameter block compaction) and
                                      runs alongside the description rewriter.
aperture/schema_optimizer/fetch_schemas.py CREATE per §6.1.
aperture/schema_optimizer/extract_fields.py CREATE per §6.2.
aperture/schema_optimizer/tokenize_schemas.py CREATE per §6.2.
aperture/schema_optimizer/rank_candidates.py CREATE per §6.2.
aperture/schema_optimizer/rewrite_rules.py CREATE per §6.3.
aperture/schema_optimizer/validator.py CREATE per §6.4.
aperture/schema_optimizer/budget.py   CREATE per §6.5.
aperture/schema_optimizer/reports.py  CREATE per §6.8.
aperture/schema_optimizer/pipeline.py CREATE — orchestrates fetch → extract → tokenize →
                                      rank → rewrite → validate → report → write overlay.
aperture/schema_optimizer/prompts/    CREATE — per-toolkit JSONL prompt sets per §17.5.
```

#### `aperture/tokenization/`

```
aperture/tokenization/__init__.py     KEEP.
aperture/tokenization/counter.py      REFACTOR — try Anthropic count first for claude-*.
aperture/tokenization/anthropic_tokenizer.py CREATE per §5.2.
aperture/tokenization/serializers.py  KEEP.
aperture/tokenization/budget_manager.py FREEZE. Useful but not v1.
aperture/tokenization/tokenizer_registry.py RENAME — extract registry from counter.py.
                                      v1 §9 expects the registry as a separate file.
```

#### `aperture/compression/`

```
ALL FILES IN THIS DIRECTORY: FREEZE.

aperture/compression/auto_profile.py  (moved here from schema_optimizer/)
aperture/compression/engine.py        FREEZE
aperture/compression/field_classifier.py FREEZE
aperture/compression/field_policy.py  FREEZE
aperture/compression/field_profiles.py FREEZE
aperture/compression/hydration.py     FREEZE
aperture/compression/prompt_cache.py  FREEZE
aperture/compression/rtk_inspired.py  FREEZE
aperture/compression/stopwords.py     FREEZE
aperture/compression/task_profiles.py FREEZE
aperture/compression/toon.py          FREEZE
```

The compression engine is large, well-tested, and not in v1's plan. It is also useful for the demo and the team has built tests for it. Don't delete it, don't extend it.

If the team wants to publish the output compression separately later, it could be extracted into its own package. For v1 realignment, just leave it where it is.

#### `aperture/routing/`

```
ALL FILES IN THIS DIRECTORY: FREEZE.

aperture/routing/effort_modes.py      FREEZE
aperture/routing/intelligent_effort.py FREEZE
aperture/routing/quality_gate.py      FREEZE
aperture/routing/selector.py          FREEZE
aperture/routing/semantic_selector.py FREEZE
```

Same reasoning as compression. Useful, tested, not v1.

#### `aperture/demo/`

```
aperture/demo/agent_simulator.py      FREEZE
aperture/demo/mock_data.py            KEEP. Used by test fixtures.
aperture/demo/scenarios.py            KEEP. Used by benchmarks.
```

#### `aperture/benchmarks/`

```
aperture/benchmarks/harness.py        REFACTOR — add v1 modes:
                                        raw                  (no Aperture)
                                        aperture_compressed  (output compression only)
                                        aperture_cached      (cache + compression)
                                        aperture_full        (cache + compression + schema overlay)
                                      Current modes (off/safe/balanced/low/aggressive)
                                      describe compression intensity, not the v1 stack-up.
                                      They should remain as a sub-axis but the primary
                                      axis is "what's enabled."
aperture/benchmarks/vanilla_vs_aperture.py REFACTOR — rename to baseline_suite.py per
                                      v1 §9. Add 17 more workflows to reach v1's 20.
aperture/benchmarks/runner.py         CREATE — wraps harness in v1's task-set + mode loop.
aperture/benchmarks/evaluators.py     CREATE — exact / field-presence / trace / LLM-judge
                                      evaluators. Current quality probes (in
                                      vanilla_vs_aperture.py:138-247) move here.
aperture/benchmarks/metrics.py        CREATE — BenchmarkMetrics dataclass per v3 §10.6.
aperture/benchmarks/report.py         CREATE — Markdown report writer.
aperture/benchmarks/tasks/            CREATE — JSONL task files:
  github_tasks.jsonl
  gmail_tasks.jsonl
  slack_tasks.jsonl
  notion_tasks.jsonl
  mixed_tasks.jsonl
                                      Convert existing scenarios to JSONL.
```

#### `aperture/adapters/`

```
aperture/adapters/__init__.py         KEEP
aperture/adapters/langgraph.py        FREEZE
```

### 8.2 `api/`

```
api/main.py                           SPLIT —
                                        api/aperture_v1.py  (new, v1 endpoints)
                                        api/legacy.py       (existing 27 endpoints)
                                      The legacy endpoints back the demo dashboard;
                                      keep them mounted but mark deprecated.

                                      api/aperture_v1.py mounts:
                                        POST /api/v3.1/project/usage/input_tokens_contributed
                                        POST /api/v3.1/project/usage/cache_tokens_saved
                                        GET  /api/v3.1/logs/tool_calls
                                        POST /api/v3.1/tool_router/sessions/{session_id}/reports
```

### 8.3 `dashboard/`

```
dashboard/app.py                      FREEZE.
```

### 8.4 `frontend/`

Frozen entirely during v1 realignment. After v1 lands, trim to:

```
frontend/src/pages/Demo.tsx           keep
frontend/src/pages/Overview.tsx       keep
frontend/src/pages/V1Reports.tsx      CREATE — pulls from /api/v3.1/...
                                      Replaces all of:
                                        Benchmarks.tsx
                                        CacheStats.tsx
                                        Compression.tsx
                                        EffortCalibrator.tsx
                                        FieldPolicy.tsx
                                        FieldSelect.tsx
                                        Placeholder.tsx
                                        PromptCache.tsx
                                        SchemaCompaction.tsx
                                        SpendStudio.tsx
                                        TaskAware.tsx
                                        TokenWaterfall.tsx
```

But this is post-v1 cleanup. During the realignment, leave the frontend alone.

### 8.5 `scripts/`

```
scripts/benchmark.py                  REFACTOR — call new aperture.benchmarks.runner.
scripts/demo.py                       FREEZE
scripts/dynamic_agent_demo.py         FREEZE
scripts/honest_comparison.py          KEEP. The script's framing is correct ("Aperture is
                                      a userspace optimization layer") even though it's
                                      not v1's framing. Useful as a Path 2 baseline.
scripts/vanilla_vs_aperture.py        REFACTOR — rename to baseline_report.py.
scripts/demo_mock_datasets.py         KEEP

scripts/v1_week_1_baseline.py         CREATE — Week 1 task: pull 100 real Composio session
                                      logs, manually count payload sizes, produce real
                                      token cost report. This is the foundation for
                                      everything else.
scripts/run_schema_optimizer.py       CREATE — runs the full pipeline end-to-end.
```

### 8.6 `tests/`

Current 180 tests cover compression, hydration, prompt_cache, field_profiles, field_policy, field_classifier, task_profiles, tokenization, toon, type_group, vanilla_vs_aperture, cache, engine_modes, engine_normalizers, quality_gate, stopwords, tokenizer_registry.

```
tests/test_cache.py                   KEEP (already covers most v1 cache safety)
tests/test_compression.py             FREEZE
tests/test_engine_modes.py            FREEZE
tests/test_engine_normalizers.py      FREEZE
tests/test_field_classifier.py        FREEZE
tests/test_field_classifier_cache.py  FREEZE
tests/test_field_policy.py            FREEZE
tests/test_field_profiles.py          FREEZE
tests/test_hydration.py               FREEZE
tests/test_prompt_cache.py            FREEZE
tests/test_quality_gate.py            FREEZE
tests/test_stopwords.py               FREEZE
tests/test_task_profiles.py           FREEZE
tests/test_tokenization.py            REFACTOR — add Anthropic tokenizer test.
tests/test_tokenizer_registry.py      KEEP
tests/test_toon.py                    FREEZE
tests/test_type_group.py              KEEP (this is v0_param_compaction).
tests/test_vanilla_vs_aperture.py     REFACTOR — replace with v1 mode benchmarks.

tests/cache/                          CREATE — directory for v1 cache tests
  test_policy_yaml.py                 CREATE
  test_normalizer.py                  CREATE
  test_key_builder_v1.py              CREATE — v1: + p1: prefix tests
  test_redis_store.py                 CREATE
  test_interceptor.py                 CREATE
  test_bypass.py                      CREATE
tests/observability/
  test_event_schema.py                CREATE
  test_event_emitter_v1.py            CREATE
  test_aggregator.py                  CREATE
  test_api_endpoints.py               CREATE
  test_reports.py                     CREATE
tests/schema_optimizer/
  test_extract_fields.py              CREATE
  test_tokenize_schemas.py            CREATE
  test_rank_candidates.py             CREATE
  test_rewrite_rules.py               CREATE
  test_validator.py                   CREATE — uses recorded LLM responses (don't burn
                                      $150 on every CI run; record + replay).
  test_budget.py                      CREATE
  test_reports.py                     CREATE
  test_pipeline.py                    CREATE
tests/benchmarks/
  test_task_set.py                    CREATE
  test_runner.py                      CREATE
  test_evaluators.py                  CREATE
  test_metrics.py                     CREATE
  test_report.py                      CREATE
tests/integration/
  test_v1_aperture_full.py            CREATE — end-to-end with all three components on.
```

---

## 9. Target repository structure

After realignment:

```
aperture/
  README.md
  pyproject.toml
  .env.example
  Makefile

  aperture/
    __init__.py
    config.py
    contracts.py                              v1 contract names

    proxy/                                    Path 1 only (recommended)
      __init__.py
      handler.py                              MCP request → Aperture pipeline → Composio
      mcp_protocol.py                         MCP message parsing helpers
      session.py                              session-level state + turn tracking

    sdk/                                      Path 2 fallback / legacy compat
      __init__.py
      runner.py                               (renamed from integration.py)

    tokenization/
      __init__.py
      anthropic_tokenizer.py
      serializers.py
      tokenizer_registry.py
      counter.py

    observability/
      __init__.py
      event_schema.py                         dataclasses
      event_emitter.py
      aggregator.py
      api_endpoints.py                        v3.1 routes
      reports.py
      trace.py

    cache/
      __init__.py
      policy.yaml                             1000+ tools classified
      policy.py                               loader
      normalizer.py
      key_builder.py                          v1:p1:scope:scope_id:tool:hash
      redis_store.py
      qdrant_store.py                         v2 stub
      interceptor.py
      bypass.py
      reports.py

    schema_optimizer/
      __init__.py
      _schemas.json                           output of fetch_schemas.py
      _overlay.json                           accepted rewrites
      fetch_schemas.py
      extract_fields.py
      tokenize_schemas.py
      rank_candidates.py
      rewrite_rules.py
      validator.py
      budget.py
      reports.py
      pipeline.py
      v0_param_compaction.py                  current type_group.py
      prompts/
        github.jsonl
        gmail.jsonl
        slack.jsonl
        notion.jsonl
        linear.jsonl

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

    compression/                              FROZEN — TRANSFER project, not v1
      ... (existing files, unchanged)

    routing/                                  FROZEN
      ... (existing files, unchanged)

    agent/                                    FROZEN
      composio_agent.py
                                              tool_cache.py is DELETED

    demo/
      ... (existing files, mostly unchanged)

    adapters/
      ... (existing files, unchanged)

  api/
    aperture_v1.py                            v3.1-shape endpoints
    legacy.py                                 the current 27 endpoints
    main.py                                   thin top-level mounting both

  dashboard/                                  FROZEN
    app.py

  frontend/                                   FROZEN (post-v1 cleanup deferred)
    ...

  scripts/
    v1_week_1_baseline.py                     real-session token measurement
    run_schema_optimizer.py
    benchmark.py
    baseline_report.py                        renamed from vanilla_vs_aperture.py
    honest_comparison.py
    demo.py
    dynamic_agent_demo.py
    demo_mock_datasets.py

  tests/
    cache/
      ...
    observability/
      ...
    schema_optimizer/
      ...
    tokenization/
      ...
    benchmarks/
      ...
    integration/
      test_v1_aperture_full.py
    test_cache.py                             v0 tests, KEPT
    test_compression.py                       FROZEN
    test_engine_modes.py                      FROZEN
    ... (other frozen tests)

  docs/
    APERTURE_PROJECT_PLAN.md                  v1 plan
    APERTURE_CODING_AGENT_EXECUTION_PLAN.md
    Aperture_V2_workingon.md
    SPOKANE_FINAL_ENGINEERING_REVIEW.md
    SPOKANE_BRANCH_CHANGELOG_AND_PLAN_GAPS.md
    HANDOFF_V1_REALIGNMENT.md                 THIS FILE
    architecture.md                           CREATE
    token_attribution.md                      CREATE
    output_compression.md                     CREATE (documents the frozen-but-useful
                                              compression engine and its non-v1 status)
    caching.md                                CREATE
    schema_optimization.md                    CREATE
    benchmark_methodology.md                  CREATE
    security_privacy.md                       CREATE
    workbench_boundary.md                     CREATE
    v3.1_api_reference.md                     CREATE

  reports/                                    CREATE the directory
    raw_token_baseline.md                     output of Week 1 baseline
    token_attribution_report.md
    cache_report.md
    schema_optimization_report.md
    benchmark_report.md
```

---

## 10. Migration strategy — keep the demo working

The team can't ship the realignment as one big PR. Here's how to land it incrementally without breaking the existing demo:

### 10.1 Branch model

Create a long-lived branch `v1-realignment` off `demo`. Open small PRs into `v1-realignment`. Periodically merge `v1-realignment` → `demo` once a checkpoint is reached. This keeps the demo branch shippable.

### 10.2 Parallel paths

Don't delete code while building. The new v1-shape code lives alongside the old code. Only flip the call sites once the new code is fully tested.

Example for `cache/`:

1. PR 1: add `aperture/cache/policy.yaml`, `policy_loader.py`, `key_builder_v1.py` (note the `_v1` suffix). Keep `policy.py`, `key_builder.py` untouched.
2. PR 2: add tests proving v1 behavior matches v0 for cacheable cases.
3. PR 3: add `aperture/cache/interceptor_v1.py` that uses the new policy + key. Existing `interceptor.py` stays.
4. PR 4: route `ApertureRunner` to use `interceptor_v1.py` behind a feature flag (`APERTURE_V1=true` env var).
5. PR 5: flip the flag default. Run benchmarks to confirm savings unchanged.
6. PR 6: rename `interceptor_v1.py` → `interceptor.py`, delete the old. Update imports.
7. PR 7: same pattern for `policy.py`, `key_builder.py`.

This is slow but won't break anything in flight.

### 10.3 Don't touch the frozen files during this work

Anyone making changes in `aperture/compression/`, `aperture/routing/`, `aperture/agent/`, `frontend/`, or `dashboard/` while v1 realignment is in progress should expect a code review veto. The frozen surface is large (~6,000 LOC) and changes there create rebase conflicts that compound the realignment work.

### 10.4 Don't break the 180 tests

Every PR must keep `uv run pytest` at 180+ passing. New tests add to that count; refactors must not subtract from it. If a frozen test would conflict with a v1 change, the v1 change is in the wrong place.

---

## 11. The two paths forward, in detail

### 11.1 Path 1 — MCP proxy (recommended)

**Architecture:**

```
LLM (Claude/GPT)
    │  HTTP POST to MCP endpoint
    ▼
Aperture MCP Proxy (NEW)
    │  Inspects MCP message: which meta tool? what args?
    │  - if SEARCH_TOOLS → check Aperture cache, possibly bypass forward
    │  - if MULTI_EXECUTE → check Aperture cache per inner tool
    │  - else → forward
    │  Tokenizes the response before returning to LLM
    │  Emits TokenAttributionEvent
    ▼
Composio Tool Router (existing)
    │  Dispatches to external APIs
    ▼
External APIs (GitHub, Gmail, ...)
```

**What the proxy is:**

A FastAPI service that the developer points their agent's MCP URL at (instead of the raw Composio MCP URL). The proxy receives MCP protocol messages, parses them, intercepts the meta-tool calls, runs Aperture's cache + attribution + schema overlay, then forwards to Composio.

**Deployment:** the proxy can run as a sidecar (one process per developer) or as a hosted service (one Aperture deployment for all developers using its MCP URL). Either way, it gives Aperture the meta-tool visibility v1 needs.

**Risk:** the MCP protocol semantics need to be honored carefully. MCP supports streaming responses; the proxy must not deadlock or change response shapes. There's published MCP server code in Anthropic's `mcp` Python package — start there.

**Effort:** ~2–3 weeks to build the proxy shell. Once it's in place, all the v1 component work plugs into it.

### 11.2 Path 2 — Userspace SDK reframe (pragmatic)

**Architecture:** what's already there. Aperture wraps `client.tools.execute(...)` calls in user code.

**What changes:** the v1 plan gets retired. Write a new plan that says: "Aperture is a userspace token-efficiency wrapper. It reduces token cost per individual tool call. It doesn't intercept Composio's meta-tool layer because that's internal to Composio. The optimizations are: (1) output compression, (2) per-process exact-match cache, (3) opt-in schema overlay."

**Pros:** matches what's already built. No architectural pivot. Fast to ship.

**Cons:** loses the cross-agent network effect. The 100k-developer hit-rate math is no longer true. The "v3.1 API extension" framing is gone. The component names ("Cross-Agent Execution Cache") are misleading and should be renamed.

### 11.3 Recommendation

**Path 1.** The reasons:

1. v1's signature contributions (cross-agent cache, v3.1 API extension, registry-side schema rewrites) all require meta-tool visibility. A proxy is the only way to get that without internal Composio access.
2. The proxy can be built once and host all three components. It's load-bearing for the project; without it, you're just polishing a userspace wrapper.
3. The MCP protocol is open and documented (Anthropic publishes the spec). Building a proxy is concrete and bounded.
4. The proxy can be tested without real Composio traffic by replaying recorded MCP messages.

If the team picks Path 2, this entire document still applies to the cache and observability components (which work the same in userspace as in a proxy), but Component C (schema optimizer) becomes much weaker — it can only produce overlays, not registry changes.

---

## 12. Week-by-week rebuild plan

This mirrors v1 §10. Adjusted for the realignment.

### Week 1 — Real-token-cost baseline (v1 mandatory, currently undone)

**Goal:** understand actual Composio session costs before writing new code.

**Tasks:**
- [ ] Wire `COMPOSIO_API_KEY` from `.env` and confirm `client.connected_accounts.list()` returns active accounts.
- [ ] Run 100 real sessions covering the user's connected toolkits (GitHub, Gmail, Slack, Notion, Linear, GoogleSheets, Supabase, YouTube). Use real prompts; don't synthesize.
- [ ] For each session: log every meta-tool call payload. (If on Path 2 / userspace, log `client.tools.execute()` calls instead — note this is a degraded measurement.)
- [ ] Tokenize each payload using `aperture/tokenization/counter.py` (with Anthropic tokenizer when applicable).
- [ ] Produce `reports/raw_token_baseline.md` with: per-tool token cost (mean, median, p95), per-toolkit cost, per-meta-tool cost, frequency of each tool.

**Deliverable:** `scripts/v1_week_1_baseline.py` and `reports/raw_token_baseline.md`.

**Definition of done:** the report contains real numbers from real sessions, not fixtures. Numbers can be referenced in pitch deck.

### Week 2 — Token attribution instrumentation

**Goal:** real-time token cost measurement per meta-tool call.

**Tasks:**
- [ ] Build `aperture/tokenization/anthropic_tokenizer.py` per §5.2.
- [ ] Refactor `counter.py` to use it for `claude-*` models.
- [ ] Rewrite `aperture/contracts.py` `TokenEvent` → `TokenAttributionEvent` per §17.1.
- [ ] Refactor `aperture/observability/events.py` (rename to `event_emitter.py`) to emit the new contract.
- [ ] Add `aperture/observability/event_schema.py` with the dataclasses extracted.
- [ ] Update all event consumers (`api/main.py`, `dashboard/app.py`, `aperture/integration.py`, tests).

**Deliverable:** `aperture/observability/event_emitter.py` emits v1-shape events.

**Definition of done:** running the agent path emits `TokenAttributionEvent` with `meta_tool_slug`, `session_id`, `session_turn`, `input_tokens_contributed`, `aperture_version`. Tests in `tests/observability/test_event_emitter_v1.py` pass.

### Week 3 — Token attribution API

**Goal:** developers can query token cost via `v3.1`-shape API.

**Tasks:**
- [ ] Build `aperture/observability/aggregator.py` — SQL aggregation over event log (SQLite for v1).
- [ ] Build `aperture/observability/api_endpoints.py` — `POST /api/v3.1/project/usage/input_tokens_contributed` and `POST /api/v3.1/project/usage/cache_tokens_saved`.
- [ ] Mount under `api/aperture_v1.py`.
- [ ] Update existing dashboard pages that consume custom endpoints to read v3.1 endpoints (or freeze and serve from legacy).

**Deliverable:** `POST /api/v3.1/project/usage/input_tokens_contributed` returns aggregated data.

**Definition of done:** request shape matches v1 §4B exactly. `group_by: meta_tool_slug` works. `dt_gt`/`dt_lt` time filtering works.

### Week 4 — Cache v1 (Redis exact-match for both MULTI_EXECUTE and SEARCH_TOOLS)

**Goal:** v1's cache shape, deny-by-default, classified TTL.

**Tasks:**
- [ ] Run `client.tools.list()` and dump to `aperture/cache/_seed_tool_list.json`.
- [ ] Auto-classify per §4.6 algorithm. Hand-review.
- [ ] Build `aperture/cache/policy.yaml` covering ≥80% of seed tools. v1 categories.
- [ ] Build `aperture/cache/normalizer.py`.
- [ ] Refactor `aperture/cache/key_builder.py` to v1 format (`aperture:v1:p1:...`).
- [ ] Refactor `aperture/cache/interceptor.py` to load policy from YAML and use new key format. Also add response-schema validation hook.
- [ ] Build `aperture/cache/bypass.py` (header parser for proxy mode).
- [ ] Add SEARCH_TOOLS exact-match query cache (Redis-only, no Qdrant in v1).

**Deliverable:** `aperture/cache/` matches v1 §4A v1-of-v1 spec.

**Definition of done:** all `tests/cache/*` pass. `aperture/cache/policy.yaml` covers ≥800 tools. Cache key format includes `v1:p1:`.

### Week 5 — Schema optimizer fetch + tokenize + baseline

**Goal:** know how inefficient current schemas are.

**Tasks:**
- [ ] Build `aperture/schema_optimizer/fetch_schemas.py`. Run it. Commit `_schemas.json`.
- [ ] Build `extract_fields.py`, `tokenize_schemas.py`, `rank_candidates.py`.
- [ ] Run the ranker, output `reports/schema_optimization_baseline.md`.

**Deliverable:** baseline report listing top 100 optimization opportunities.

**Definition of done:** report shows expected savings × frequency for the top 100 description fields.

### Week 6 — Schema optimizer rewrite + validate top 25

**Goal:** ship 25 accepted schema rewrites.

**Tasks:**
- [ ] Build `rewrite_rules.py`.
- [ ] Build `validator.py`. Use record-and-replay for tests.
- [ ] Build `prompts/{toolkit}.jsonl` — 50 prompts each for github/gmail/slack/notion/linear.
- [ ] Build `pipeline.py` orchestrator.
- [ ] Run on top 25 tools by ranking. Validate 50 prompts × 3 candidates × 25 = 3,750 inference calls. Budget: $40.
- [ ] Generate `reports/schema_optimization_report.md`.
- [ ] Write `_overlay.json` with accepted entries.

**Definition of done:** ≥35% average reduction across the 25 accepted descriptions. Report includes original/optimized text per accepted rewrite. Rejection reasons documented for any rejected.

**Acceptance gate:** 25 candidates can be rejected if quality fails. Don't lower the bar.

### Week 7 — Aperture full integration + benchmark suite

**Goal:** all three components work together.

**Tasks:**
- [ ] Wire all three components into the proxy (Path 1) or runner (Path 2).
- [ ] Add `aperture/benchmarks/runner.py`, `evaluators.py`, `metrics.py`, `report.py`.
- [ ] Convert existing scenarios to JSONL task format.
- [ ] Add 17 more workflows to reach v1's 20.
- [ ] Run baseline benchmark with the four modes (raw, aperture_compressed, aperture_cached, aperture_full).
- [ ] Generate `reports/benchmark_report.md`.

**Deliverable:** `reports/benchmark_report.md` with real numbers across the four modes.

**Definition of done:** Aperture full mode shows ≥50% token savings on aggregate vs raw mode. Quality probes pass on every workflow.

### Week 8 — Production polish

- [ ] Add the documentation files in `docs/` per §9.
- [ ] Reach 0 ruff findings on the v1-shape modules (`aperture/cache/`, `aperture/observability/`, `aperture/schema_optimizer/`, `aperture/tokenization/`).
- [ ] Add CI step that runs the benchmark and asserts ≥40% savings.
- [ ] Add CI step that runs the schema optimizer in dry-run mode on every PR.

---

## 13. Acceptance criteria per component

This is the gate: when all of these are true, the component is done.

### 13.1 Component A — Cache (v1-of-v1)

- [ ] `aperture/cache/policy.yaml` exists and is loaded at startup.
- [ ] YAML has explicit entries for ≥800 tools across the seven seed toolkits.
- [ ] Default behavior is deny-by-default.
- [ ] Cache key format is `aperture:v1:p1:{scope}:{scope_id}:{tool_slug}:{sha256(normalized_params)}`.
- [ ] Required scope ID missing → `key_builder` returns `None` → cache is skipped.
- [ ] Write/auth tools (NEVER_CACHE list) cannot be cached; tested.
- [ ] Failed responses (`success: false` or `error` field) not cached; tested.
- [ ] Cache bypass works via both `cache_bypass=True` field and `X-Aperture-Cache-Bypass: true` header (Path 1).
- [ ] Cache hit returns `CachedResult(data, age, original_cost_tokens)` per v1 §4A.
- [ ] Cache event emitted: `cache_status ∈ {hit, miss, bypass, not_cacheable, error}`.
- [ ] SEARCH_TOOLS responses are cached separately with `connection_status` excluded from the cache key, fetched fresh on assemble.
- [ ] Tests: `tests/cache/test_*.py` all pass. ≥40 tests covering policy loading, normalizer determinism, key versioning, scope safety, bypass, hit-vs-miss, schema-version invalidation.

### 13.2 Component B — Token Attribution

- [ ] `TokenAttributionEvent` matches v1 §17.1 exactly. All fields present.
- [ ] Anthropic tokenizer used when `model.startswith("claude-")` and `ANTHROPIC_API_KEY` set.
- [ ] `meta_tool_slug` populated for every event in proxy mode (None in userspace mode).
- [ ] `session_id` and `session_turn` populated.
- [ ] Events flow into a SQLite event log.
- [ ] `POST /api/v3.1/project/usage/input_tokens_contributed` returns aggregated data per `group_by` parameter.
- [ ] `POST /api/v3.1/project/usage/cache_tokens_saved` returns aggregated data per `group_by` parameter.
- [ ] Five named reports per v3 §6.5: `top_expensive_tools_report`, `compression_savings_report`, `cache_savings_report`, `session_cost_report`, `schema_savings_report` — each generates Markdown.
- [ ] Tests: `tests/observability/test_*.py` all pass. ≥30 tests.

### 13.3 Component C — Schema Optimizer

- [ ] `_schemas.json` exists with all Composio tools fetched.
- [ ] Top 100 optimization opportunities ranked.
- [ ] ≥25 tools have accepted rewrites in `_overlay.json`.
- [ ] Average reduction across accepted rewrites ≥35%.
- [ ] Validator: 50 prompts × 3 candidates × 25 tools all run with verifiable record-and-replay.
- [ ] No rewrite accepted unless 50/50 prompts produce identical tool selection and parameter extraction.
- [ ] Report `reports/schema_optimization_report.md` generated.
- [ ] Tests: `tests/schema_optimizer/test_*.py` all pass. Validator tests use replay; do not call live LLM in CI.

### 13.4 End-to-end

- [ ] Benchmark suite has 20 workflows.
- [ ] Four modes (`raw`, `aperture_compressed`, `aperture_cached`, `aperture_full`) all run.
- [ ] Aperture full mode achieves ≥50% aggregate token savings vs raw.
- [ ] Quality probes pass for every workflow in every mode.
- [ ] `reports/benchmark_report.md` published.
- [ ] All 17 documentation files in `docs/` exist with non-trivial content.

---

## 14. Test plan

### 14.1 Test directory layout

Create directories per v3 §4 plan structure, mirroring v1. New tests are split out:

```
tests/
  cache/                  ← new
  observability/          ← new
  schema_optimizer/       ← new
  tokenization/           ← new
  benchmarks/             ← new
  integration/            ← new
```

### 14.2 Test data

Three data sources:

1. **Fixtures** — synthetic data for fast unit tests. Already in `aperture/demo/mock_data.py` and `data/`.
2. **Replay corpus** — recorded LLM responses for validator tests. New: `tests/schema_optimizer/replay/`.
3. **Real-session corpus** — real Composio sessions captured in Week 1. Stored in `tests/integration/sessions/` (gitignored if PII; otherwise committed).

### 14.3 What MUST be tested

For each v1 sub-spec listed in §4–§6 with status ⚠️ or ❌, there should be a corresponding test asserting the v1 behavior. Coverage gates at PR review:

- Cache: every cell of v1 §4A's spec (10+ tests already; need ≥40 total).
- Observability: every TokenAttributionEvent field (≥30 tests).
- Schema: rewrite rules a–e (≥15 tests), validator with replay (≥10 tests), pipeline integration (≥5 tests).

### 14.4 What MUST NOT happen in CI

- No live LLM calls during `uv run pytest`. All validator tests use recorded responses.
- No live Composio calls. All cache tests use `_MemoryStore` or a stubbed Composio client.
- No real Anthropic tokenizer calls. Use `count_tokens(model="gpt-4o")` (cl100k registry) as the default; the Anthropic path is opt-in via env var.

### 14.5 Live tests (run manually, not in CI)

```
tests/live/
  test_composio_real.py        runs only when COMPOSIO_API_KEY is set
  test_anthropic_tokenizer.py  runs only when ANTHROPIC_API_KEY is set
  test_upstash_redis.py        runs only when UPSTASH_REDIS_REST_URL is set
```

Use pytest markers:

```python
@pytest.mark.live_composio
def test_repo_lookup():
    if not os.getenv("COMPOSIO_API_KEY"):
        pytest.skip("no key")
    ...
```

CI runs `pytest -m "not live_composio and not live_anthropic and not live_redis"`.

---

## 15. Risk register (this realignment)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Team picks Path 1 (proxy) but never finishes the proxy | Medium | High | Start the proxy in Week 0. If not working by end of Week 1, fall back to Path 2 explicitly. |
| MCP protocol semantics break under load | Medium | High | Use Anthropic's `mcp` Python library; don't roll your own. Replay recorded MCP traffic in tests. |
| Schema optimizer validation costs more than budget | Low | Medium | `budget.py` aborts at $50/run. |
| Anthropic tokenizer adds too much latency | Medium | Low | Cache results in Redis for 24h. Opt-out env var. |
| Renaming `TokenEvent` breaks 50+ call sites | High | Medium | Use `git grep -l "TokenEvent"` first. Refactor in one PR with mass sed + tests. |
| YAML cache policy gets out of date | Medium | Low | CI step that runs `client.tools.list()` and asserts every slug appears in policy.yaml. |
| Frozen compression layer drifts from realignment | Medium | Low | Don't touch frozen files. Code review must reject changes there during realignment. |
| Schema overlays can't actually be applied because Composio's SDK doesn't accept overlay format | Medium | Medium | Test the `apply_overlay` helper end-to-end early (Week 6). If the SDK shape doesn't match, escalate before Week 7. |
| Real-session Week 1 data has PII | Medium | High | Strip user-content fields before saving session logs. Document in `docs/security_privacy.md`. |
| Test count drops below 180 during refactor | Medium | Low | Each PR asserts test count went up or stayed flat. CI gate. |

---

## 16. Open questions that block progress

These need answers before Week 1 can start. Get them resolved.

1. **Path 1 or Path 2?** This determines the next 8 weeks of work. Default to Path 1. Decide explicitly.
2. **Does the team have or can it acquire internal Composio access?** If yes, several gaps shrink (registry write path, real session log access). If no, every component is overlay-shaped or proxy-shaped.
3. **Can `client.tools.list()` actually return all 1000+ Composio tools in one call?** Or does it require pagination? Test this in Week 0.
4. **Does the Composio SDK expose a way to inspect raw meta-tool wire format?** If yes, userspace mode (Path 2) becomes more powerful. If no, Path 1 is required for real meta-tool visibility.
5. **What is the team's Anthropic budget for the schema optimizer validator run?** v1 estimated $90–150 one-time. Confirm this is approved.
6. **Where does the SQLite event log live?** Local file, Postgres, somewhere else. Decide in Week 2.
7. **What is the production deployment target?** Local-only (current state), Railway, Kubernetes, Lambda? Affects how the proxy is deployed.
8. **How does Composio's MCP URL handle auth?** Is the MCP URL itself a bearer token, or does the LLM client pass auth separately? The proxy needs to handle this.
9. **Are there real Composio session logs accessible (the team has API access; can they pull `/logs/tool_calls`)?** Required for Week 1.
10. **What is the team's posture on the Phases 1–4 (TRANSFER.md) work?** Freeze, extract, or delete? This document assumes freeze.

---

## 17. Appendices

### 17.1 Exact data contracts

Place these in `aperture/observability/event_schema.py`. They are the contracts every other module imports.

```python
"""v1 contracts. Mirror aperture/v1 plan exactly.

Every module that emits or consumes events MUST use these dataclasses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    tokenizer: str
    tokenizer_is_approximate: bool
    payload_bytes: int


@dataclass(frozen=True)
class ExecutionContext:
    """Carried through every Aperture pipeline. Replaces ApertureRunConfig."""
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


@dataclass(frozen=True)
class TokenAttributionEvent:
    """A single token-cost data point. Goes to event_log; queried via api_endpoints."""
    event_type: Literal[
        "meta_tool_response", "argument", "result",
        "compressed_result", "cache_hit_savings", "schema_savings"
    ]
    timestamp: str                 # ISO 8601 UTC
    project_id: str | None
    user_id: str | None
    session_id: str | None
    session_turn: int | None
    connected_account_id: str | None
    toolkit_slug: str | None
    tool_slug: str | None
    meta_tool_slug: str | None
    payload_kind: Literal["schema", "execution_result", "plan", "compressed_result"]
    model: str | None
    tokenizer: str
    tokenizer_is_approximate: bool
    raw_payload_bytes: int | None
    compressed_payload_bytes: int | None
    raw_tokens: int | None
    compressed_tokens: int | None
    input_tokens_contributed: int  # what this meta tool added to LLM input context
    tokens_saved: int
    compression_ratio: float | None
    cache_status: str | None
    aperture_version: str          # always "0.3.0" or whatever __init__.py reports


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
    mode: str                      # "off" | "shadow" | "safe" | "balanced"


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


@dataclass(frozen=True)
class CachePolicy:
    tool_slug: str
    cacheable: bool
    operation_type: Literal["read", "write", "auth", "unknown"]
    privacy_scope: Literal["public", "project", "user", "account", "session", "none"]
    ttl_seconds: int | None
    matching: Literal["exact", "none"]
    reason: str | None = None


@dataclass(frozen=True)
class CacheEvent:
    event_type: Literal["hit", "miss", "bypass", "not_cacheable", "error"]
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


@dataclass(frozen=True)
class CachedResult:
    """What CachedExecutor.execute returns on a hit."""
    data: object
    cached_age_seconds: int
    original_cost_tokens: int    # what the original execution cost (token-wise)


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

### 17.2 Exact API endpoint shapes

Mount under `/api/v3.1/`.

#### `POST /api/v3.1/project/usage/input_tokens_contributed`

Request:

```json
{
  "group_by": "meta_tool_slug" | "toolkit_slug" | "session_turn" | "user_id" | "date",
  "order_by": "total_quantity" | "name",
  "order_direction": "asc" | "desc",
  "dt_gt": "2026-04-28T00:00:00Z",
  "dt_lt": "2026-05-05T23:59:59Z",
  "user_id": "optional filter",
  "session_id": "optional filter",
  "page": 1,
  "page_size": 100
}
```

Response:

```json
{
  "data": [
    {
      "group_value": "COMPOSIO_SEARCH_TOOLS",
      "total_input_tokens_contributed": 482301,
      "total_calls": 1284,
      "average_per_call": 375.6
    },
    {
      "group_value": "COMPOSIO_MULTI_EXECUTE_TOOL",
      "total_input_tokens_contributed": 295103,
      "total_calls": 612,
      "average_per_call": 482.2
    }
  ],
  "page": 1,
  "page_size": 100,
  "total_groups": 2,
  "queried_at": "2026-05-09T16:30:00Z"
}
```

#### `POST /api/v3.1/project/usage/cache_tokens_saved`

Request:

```json
{
  "group_by": "tool_slug" | "toolkit_slug" | "user_id" | "date",
  "dt_gt": "2026-05-01T00:00:00Z",
  "dt_lt": "2026-05-08T23:59:59Z"
}
```

Response shape mirrors the above.

#### `GET /api/v3.1/logs/tool_calls`

(Optional. Mirrors Composio's existing endpoint; useful if the team builds the proxy and wants to expose meta-tool-level logs.)

Query params:

```
date_gt, date_lt, status, user_id, session_id, toolkit_slug, tool_slug, page, page_size
```

Response includes one record per Aperture-observed meta-tool call, with full request/response payloads (truncated for large payloads, with reference ID for hydration).

### 17.3 `aperture/cache/policy.yaml` schema

```yaml
version: 1                      # bumping this invalidates ALL cache keys via p{version}: prefix
default:
  cacheable: false
  operation_type: unknown
  privacy_scope: none
  ttl_seconds: null
  matching: none
  reason: deny_by_default

categories:
  STATIC:
    description: Changes very rarely. Long TTL.
    default_ttl_seconds: 7200
  DYNAMIC:
    description: Changes on a schedule. Medium TTL.
    default_ttl_seconds: 900
  LIVE:
    description: Changes constantly. Short or no TTL.
    default_ttl_seconds: 60
  WRITE:
    description: Mutates state. Never cache.
    default_ttl_seconds: null
  PRIVATE:
    description: User-specific. Account-scoped, exact-match only.
    default_ttl_seconds: 300

tools:
  GITHUB_GET_REPO:
    category: STATIC
    cacheable: true
    operation_type: read
    privacy_scope: public
    ttl_seconds: 7200
    matching: exact
    response_schema_check: enabled
    notes: Public repo metadata.

  GITHUB_GET_A_REPOSITORY:
    category: STATIC
    cacheable: true
    operation_type: read
    privacy_scope: public
    ttl_seconds: 7200
    matching: exact
    notes: Alias for GITHUB_GET_REPO. Composio sometimes uses this name.

  GITHUB_LIST_ISSUES:
    category: DYNAMIC
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 900
    matching: exact

  GITHUB_LIST_REPOSITORY_ISSUES:
    category: DYNAMIC
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 900
    matching: exact

  GITHUB_CREATE_ISSUE:
    category: WRITE
    cacheable: false
    operation_type: write
    privacy_scope: account
    ttl_seconds: null
    matching: none
    reason: write_operation

  GMAIL_SEARCH_EMAILS:
    category: PRIVATE
    cacheable: true
    operation_type: read
    privacy_scope: account
    ttl_seconds: 300
    matching: exact

  GMAIL_SEND_EMAIL:
    category: WRITE
    cacheable: false
    operation_type: write
    privacy_scope: account
    ttl_seconds: null
    matching: none
    reason: write_operation

  COMPOSIO_MANAGE_CONNECTIONS:
    category: WRITE
    cacheable: false
    operation_type: auth
    privacy_scope: none
    ttl_seconds: null
    matching: none
    reason: auth_operation

  COMPOSIO_SEARCH_TOOLS:
    category: STATIC
    cacheable: true
    operation_type: read
    privacy_scope: public         # query → schema/plan portion is shareable
    ttl_seconds: 3600
    matching: exact
    notes: |
      Connection status portion is per-user; cache only the schema+plan
      portion of the response and re-fetch connection status on every assemble.

# … repeat for every Composio tool …
```

### 17.4 `aperture/cache/bypass.py`

```python
"""Cache bypass parsing.

Honors:
  - HTTP header: X-Aperture-Cache-Bypass: true|1|yes
  - Metadata field on the request: aperture_cache_bypass: true
  - Configuration: ExecutionContext.cache_bypass = True
"""

from typing import Mapping

_TRUTHY = {"true", "1", "yes", "on"}

def is_bypass_requested(
    headers: Mapping[str, str] | None = None,
    metadata: dict | None = None,
    context_flag: bool = False,
) -> bool:
    if context_flag:
        return True
    if headers:
        v = headers.get("X-Aperture-Cache-Bypass") or headers.get("x-aperture-cache-bypass")
        if v and v.lower() in _TRUTHY:
            return True
    if metadata and isinstance(metadata.get("aperture_cache_bypass"), bool):
        return metadata["aperture_cache_bypass"]
    return False
```

### 17.5 Schema optimizer prompts

Per-toolkit JSONL files. Example for `aperture/schema_optimizer/prompts/github.jsonl`:

```jsonl
{"prompt": "Create an issue titled 'Login broken' in composioHQ/composio.", "expects_tool": "GITHUB_CREATE_ISSUE", "expects_args": {"owner": "composioHQ", "repo": "composio", "title": "Login broken"}}
{"prompt": "Open a new issue in composio repo with title Auth failure on Safari.", "expects_tool": "GITHUB_CREATE_ISSUE", "expects_args": {"owner": "composioHQ", "repo": "composio", "title": "Auth failure on Safari"}}
{"prompt": "Submit a PR titled 'Fix OAuth' against composioHQ/composio main branch from my-fork:fix.", "expects_tool": "GITHUB_CREATE_PULL_REQUEST", "expects_args": {"owner": "composioHQ", "repo": "composio", "title": "Fix OAuth", "head": "my-fork:fix", "base": "main"}}
{"prompt": "List all open issues in composioHQ/composio.", "expects_tool": "GITHUB_LIST_ISSUES", "expects_args": {"owner": "composioHQ", "repo": "composio", "state": "open"}}
{"prompt": "Show me the top 5 issues labeled 'bug' in the composio repository.", "expects_tool": "GITHUB_LIST_ISSUES", "expects_args": {"owner": "composioHQ", "repo": "composio", "labels": "bug", "per_page": 5}}
```

50 prompts per toolkit minimum. Mix of:

- 30 prompts that should select tool X with specific params (positive cases)
- 10 disambiguation prompts that test tool-similarity (e.g., issue vs PR)
- 5 ambiguous prompts where a small description change might make the wrong tool look right (negative-control cases)
- 5 edge cases (non-English, unusual params)

Build one set per toolkit. Reuse across all tools within that toolkit.

### 17.6 Cache key migration

Old format (current): `aperture:cache:{scope}:{tool_slug}:{16-char-hash}`
New format (v1): `aperture:v1:p1:{scope}:{scope_id}:{tool_slug}:{full-sha256}`

Strategy:
- New format goes live in PR after policy.yaml lands.
- Old format keeps being read (never written) for 1 day to drain in-flight TTLs. Add a feature flag `APERTURE_READ_LEGACY_KEYS=true` (default true for 1 day, then false).
- After the drain window, remove legacy reads.

### 17.7 Reference reading list

Required reading for anyone working on this realignment:

1. `docs/APERTURE_PROJECT_PLAN.md` — v1 plan, the target state.
2. `docs/APERTURE_CODING_AGENT_EXECUTION_PLAN.md` — v3 execution plan; parallel reference for contracts and module shapes.
3. `docs/SPOKANE_FINAL_ENGINEERING_REVIEW.md` — what the previous reviewer confirmed worked. Note: stale on `/api/bench/rtk` and `VsRtk.tsx` claims.
4. `docs/SPOKANE_BRANCH_CHANGELOG_AND_PLAN_GAPS.md` — what changed during the last validation pass.
5. Composio docs:
   - https://docs.composio.dev/api-reference (the actual `/api/v3.1` shapes)
   - Tool Router session creation
   - The six meta tools' behavior
6. MCP protocol spec: https://modelcontextprotocol.io
7. Anthropic `mcp` Python package
8. `aperture/cache/interceptor.py` — current implementation, the starting point for refactor
9. `aperture/agent/composio_agent.py:253-358` — how the codebase currently uses the Composio SDK
10. This document.

### 17.8 Glossary

- **v1** — the original `APERTURE_PROJECT_PLAN.md` plan with five components A–E. (D and E out of scope per user.)
- **v3** — the `APERTURE_CODING_AGENT_EXECUTION_PLAN.md` execution spec. Parallel reference; not the target.
- **Meta tool** — one of the six `COMPOSIO_*` top-level tools. Aperture v1 was supposed to intercept these.
- **Tool slug** — a Composio tool identifier like `GITHUB_GET_REPO`. Inside `COMPOSIO_MULTI_EXECUTE_TOOL`, tools are dispatched by slug.
- **Cross-agent cache** — cache that serves hits to multiple developers' agents. Requires meta-tool visibility. Currently single-tenant; v1 wanted cross-tenant.
- **MCP** — Model Context Protocol. The wire format Composio's Tool Router uses to talk to LLM clients.
- **Path 1** — build an MCP proxy. Recommended.
- **Path 2** — userspace SDK reframe. Acceptable but loses v1's network effect.
- **Overlay** — the JSON file produced by the schema optimizer. Maps tool slug → optimized description + metadata.
- **Frozen** — file should not be touched during realignment. Stays as-is on disk.
- **TRANSFER project** — the Phases 1–4 dashboard project documented in `TRANSFER.md`. Not v1. Frozen.
- **Spokane** — the local branch / workspace these review docs were written against.

---

## 18. One-page summary for non-engineering reviewers

If someone with limited time asks "what's wrong and what's the plan?", give them this:

**What's wrong.** The codebase implements a different project than the original Aperture v1 plan asked for. v1 wanted a layer that intercepts Composio's six meta tools and adds three things: a cross-agent cache, a token attribution layer matching Composio's `/api/v3.1` shape, and an offline schema description rewriter. What got built is a userspace wrapper that intercepts individual tool calls, runs output compression on the responses, caches them in single-tenant Redis, and exposes a custom dashboard. Roughly half the code solves problems v1 didn't pose. The signature feature of v1 — rewriting tool descriptions to save tokens permanently across all Composio sessions — has zero implementation.

**Why.** Two likely reasons: (a) the team didn't get internal Composio access, so they couldn't intercept meta tools and pivoted to userspace; (b) a separate "Phases 1–4" project (output compression, hydration, prompt caching, field selection) ran alongside and consumed most of the engineering budget. Neither pivot is documented; both happened.

**What we're doing about it.** Eight-week realignment. Build an MCP proxy that gives Aperture meta-tool visibility from outside Composio. Ship v1's three components on top: cross-agent cache (Redis + YAML policy), v3.1-shape token attribution endpoints, and a schema description rewriter pipeline that produces an overlay file (since we can't write to Composio's registry). Components D and E (session state, plan scoring) remain out of scope. The frozen output-compression layer stays in place for the demo; v1 work happens alongside it.

**What's at stake.** v1's value proposition — cross-agent caching with network effects, registry-side schema savings — depends on meta-tool visibility. Without the realignment, "Aperture" is a useful but small userspace optimization. With it, it's the platform-level token-efficiency layer the v1 plan envisioned.

---

*End of handoff document. If you're a coding agent picking this up, start at §12 Week 1 (real-token-cost baseline). If you're a teammate, start at §0 (bottom line) and §11 (which path).*
