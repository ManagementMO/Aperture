# Aperture V2 — Working Plan

**Team:** Khai, Evan, Mo  
**Start:** Tomorrow (coding phase)  
**Scope:** Token-efficiency layer around Composio. We instrument their tool harness, not replace it.  
**Stack:** Python, Redis, tiktoken (or model-native tokenizer), LLM for semantic similarity, Composio SDK.

> We checked Composio docs (toolkits, reference, cookbooks, workbench). They do not ship token attribution, execution caching, or schema compaction. These are real gaps. We avoid their workbench and auth flows entirely.

---

## 1. Token Cost Measurement (Observability)

**Problem:** When Composio executes a tool and returns the payload, that payload gets injected into the LLM context window. No one knows how many tokens Composio is responsible for.

**What we build:**
- Intercept Composio tool responses before they hit the MCP / model context.
- Serialize the payload deterministically (sorted keys, compact JSON).
- Count tokens with the correct tokenizer for the target model (tiktoken for OpenAI, model-native counters for Anthropic, etc.).
- Attach token metadata to the response so the orchestrator knows the Composio-contributed token cost.
- Emit events: `tool_slug`, `payload_kind` (schema / result / search / plan), `input_tokens_contributed`, `model`, `timestamp`, `session_id`.

**Key files:**
- `aperture/observability/serializers.py` — deterministic JSON serialization
- `aperture/observability/token_counter.py` — tokenizer registry + count
- `aperture/observability/event_emitter.py` — emit attribution events

**Goal:** Any agent framework using Aperture can answer: "How many input tokens did Composio just add to my context?"

---

## 2. Smart Tool-Call Caching (Exact + Semantic)

**Problem:** Agents repeat read-only tool calls. Exact repeats waste API quota and tokens. Near-identical repeats (same tool, slightly different params) waste even more.

**What we build:**

### Phase A — Exact-match cache (Redis)
- Deny-by-default cache policy. Only idempotent reads are cacheable.
- Normalize params (sort keys, strip metadata), build a scoped cache key.
- Redis GET before execution; SET on success with TTL.
- Scopes: `public` / `project` / `user` / `account` / `session`. Private data never leaks across scopes.
- Never cache writes, auth, or connection management.

### Phase B — Semantic / partial cache (LLM-assisted)
- When an exact miss happens, query Redis for recent cached calls to the same tool.
- Use an LLM to compare the new request params against cached request params.
- The LLM returns a similarity score and a diff: "these requests are 85% the same; the only difference is the `date_range` field."
- If similarity is above threshold, the LLM generates a "delta prompt" — essentially: "take cached result X and change only the date_range to the new value."
- Execute only the delta (or use the cached result + lightweight patch) instead of a full external call.
- Cache the new result for future hits.

**Why LLM and not vector similarity?**
- Tool arguments are structured JSON. Embedding similarity is noisy for param-level differences.
- An LLM can reason: "same repo, different branch" vs "same repo, same branch, different file." That nuance matters for correctness.

**Key files:**
- `aperture/cache/policy.py` + `policy.yaml` — deny-by-default rules
- `aperture/cache/normalizer.py` — param normalization
- `aperture/cache/key_builder.py` — scoped Redis keys
- `aperture/cache/redis_store.py` — get/set with TTL
- `aperture/cache/interceptor.py` — exact-match wrapper
- `aperture/cache/semantic_cache.py` — LLM similarity + delta generation

**Goal:** Exact repeats are free (cache hit). Near-identical repeats are cheap (delta compute only).

---

## 3. Schema Optimization (Compaction)

**Problem:** Composio serves 1000+ toolkits. Tool descriptions and param descriptions are verbose. Every time schemas are loaded into context, they burn tokens.

**What we build:**
- Fetch schemas from Composio's registry.
- Extract all description fields (tool desc, param desc, enum desc).
- Count tokens per field. Rank by `token_count × usage_frequency`.
- Generate compact rewrites:
  - Verbose prose → imperative ("Creates a new issue..." → "Create a GitHub issue.")
  - Redundant type wording → stripped ("A string containing the title..." → "Issue title.")
  - Long optional/param lists → structured shorthand
- **Validate every rewrite:** Run a suite of test prompts against both the original schema and the compact schema. If the LLM selects the same tool and fills the same params correctly, accept. If behavior drifts, reject.
- Only accept rewrites that pass validation. Produce before/after diffs + savings report.

**Guardrails:**
- Never change slugs, param names, types, required fields, or auth requirements.
- Preserve disambiguation text (e.g., "send email" vs "create draft").
- Every accepted rewrite must have validation evidence.

**Key files:**
- `aperture/schema_optimizer/fetch_schemas.py`
- `aperture/schema_optimizer/extract_fields.py`
- `aperture/schema_optimizer/tokenize_schemas.py`
- `aperture/schema_optimizer/rewrite_rules.py`
- `aperture/schema_optimizer/validator.py`
- `aperture/schema_optimizer/reports.py`

**Goal:** Schemas cost fewer tokens. Agent behavior stays identical. Savings are measured, not guessed.

---

## Architecture Sketch

```
Agent / Orchestrator
        ↓
Composio meta-tool call
        ↓
Aperture Cache Layer
  ├─ Exact match? → Redis hit → return cached result
  ├─ Semantic match? → LLM diff → patched result → return
  └─ Miss → execute via Composio
        ↓
Composio executes tool, returns payload
        ↓
Aperture Observability Layer
  ├─ Serialize payload
  ├─ Count tokens
  └─ Emit attribution event
        ↓
Aperture Schema Layer (offline / init)
  ├─ Fetch schemas
  ├─ Compact descriptions
  └─ Validate behavior
        ↓
Payload enters LLM context (now measured + cached + compact)
```

---

## Dev Notes

- **Composio does not solve these problems.** Their docs cover toolkits, auth, triggers, CLI, workbench, and cookbooks. No token counting, no execution cache, no schema compaction.
- **We work on branches.** Khai, Evan, Mo — each opens PRs. I review all PRs.
- **Every module gets tests.** Unit + integration. No exceptions.
- **Conservative by default.** A cache miss is better than a wrong cache hit. A longer schema is better than a broken agent.
- **Use Redis for cache.** Use tiktoken (or model-native) for token counting. Use an LLM call for semantic similarity — but only on exact misses, not the hot path.

---

## Immediate Next Steps (Tomorrow)

1. Scaffold repo: `pyproject.toml`, `aperture/` package, `tests/`, Redis connection setup.
2. Build serializer + token counter (standalone, no Composio dependency yet).
3. Build cache policy loader + exact-match interceptor with fake Redis store.
4. Fetch a sample of Composio schemas and run them through the compaction pipeline manually.
5. Evan and Mo pick up cache layer and schema layer in parallel once scaffold is in.
