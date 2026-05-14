# Aperture v1 — Engineering Case Study

A token-efficiency layer for Composio-powered LLM agents. Built across
four implementation-fix commits on `v1-fixes`, followed by docs polish
and adversarial review at every step. This is a writeup of what I built,
the bugs that surfaced only
under live API testing, the engineering judgments those discoveries
forced, and what I learned about engineering AI-augmented systems. It is
deliberately specific and deliberately honest about gaps — the framing is
the point.

---

## Context

Composio's "Tool Router" exposes thousands of third-party SDKs (GitHub,
Gmail, Slack, Notion, Linear, etc.) to LLM agents through a Streamable-HTTP
MCP endpoint. The session Tool Router surface has six meta tools —
`SEARCH_TOOLS`, `GET_TOOL_SCHEMAS`,
`MULTI_EXECUTE_TOOL`, `MANAGE_CONNECTIONS`, `REMOTE_WORKBENCH`, and
`REMOTE_BASH_TOOL` — gate the LLM's access to the underlying registry.
Composio Connect also documents a seventh connection-wait tool; Aperture
forwards and tokenizes that path but does not cache or overlay it.
Every interaction with these meta tools is expensive: a single
`SEARCH_TOOLS` round-trip can cost thousands of tokens, and a chatty agent
makes dozens per session.

**Aperture sits between the LLM client and Composio as an MCP proxy.** It
forwards every request, but along the way it caches deterministic reads,
tokenizes responses for attribution, and rewrites verbose tool descriptions
through a Haiku/Sonnet-validated schema overlay. The goal: 30–50%
aggregate token savings without changing how the LLM client talks to
Composio. From the agent's perspective, Aperture is invisible. From the
billing department's perspective, it pays for itself.

The project has three components:

- **A — Cache.** Per-tool YAML policy with deny-by-default semantics, a
  policy-version-coupled cache key (`aperture:v1:p1:scope:scope_id:tool:hash`),
  partial-batch caching for `MULTI_EXECUTE_TOOL`, and scope isolation
  across public/account/user/project/session boundaries. 1,700+ tools
  classified across 15 toolkits.
- **B — Token attribution.** Every meta-tool response tokenized in the
  proxy's hot path (background, never blocks the response), events flow
  to SQLite, queryable through `/api/v3.1/...` FastAPI endpoints. The
  Anthropic `count_tokens` API is opt-in (`APERTURE_USE_ANTHROPIC_TOKENIZER=true`)
  for privacy reasons — defaulting to `cl100k_base` so non-Anthropic LLM
  providers don't have payloads forwarded to a third party.
- **C — Schema description optimizer.** Offline pipeline that ranks
  description fields by `tokens × frequency`, runs them through three
  deterministic rewrite levels (light → medium → heavy), then validates
  each candidate by running 50 prompts through Haiku with original vs.
  candidate schemas and comparing tool-selection + normalized arguments.
  Sonnet spot-checks 10% of accepted prompts. The result lands in a JSON
  overlay the proxy applies to outbound `tools/list` and
  `GET_TOOL_SCHEMAS` responses.

Total: ~6,500 lines of Python, ~600 lines of TypeScript dashboard, 234
tests, 0 ruff findings, 4 independent reviewer sign-offs.

---

## How the project began: salvage and the Path 1 vs Path 2 decision

This wasn't a greenfield project. A prior team had built a working `demo`
branch — a userspace SDK wrapper around Composio's `client.tools.execute()`
with output compression, a Redis-backed cache, and a 14-page React
dashboard. It shipped. It was not what v1 was supposed to be.

The v1 plan called for a *cross-agent* MCP proxy intercepting Composio's
session meta-tool surface — a fundamentally different architecture from the
demo's single-tenant userspace runner. Two paths forward:

- **Path 1 — MCP proxy.** Build a Streamable-HTTP MCP server that
  splices LLM-client ↔ Composio traffic. Hardest path; ~2-3 weeks of
  net-new protocol work; cross-agent semantics for free; matches v1
  vision exactly.
- **Path 2 — Keep the userspace wrapper.** Strap the cache and the
  attribution layer onto the existing demo. Faster to ship; loses
  cross-agent semantics; doesn't match v1.

I chose Path 1 explicitly, after asking. The reasoning: the cross-agent
cache is the entire reason v1 exists. A single agent's repeated
`SEARCH_TOOLS` calls are an easy fix; the hard problem is amortizing
those costs across dozens of agents on the same toolkits at the same
time. Path 2 doesn't solve that; the demo *was* Path 2 already. If we
were going to spend weeks shipping again, it should be on the harder
problem.

Then I made a second decision: **start from `aperture-plan-review` HEAD,
not from scratch.** A prior v1 attempt at commit `b4e2937` had ~80% of
the scaffolding done — types, YAML cache policy loader, deterministic
schema-optimizer pipeline, 41 test files. Plenty of audit work to do
(some of it had real bugs — the Anthropic tokenizer was secretly using
chars/4 fallback, the cache key was missing the policy-version segment,
the rewriter returned one candidate not three) but discarding 2,000
lines of working scaffolding to build greenfield seemed wasteful.
Reset, audit, and salvage was the right call. The demo branch stayed
parallel and untouched the entire time; the two never shared files.

**Lesson.** When a prior attempt exists, the cheapest first step is
usually an honest audit, not a fresh start. The audit told us what was
salvageable (most of it) and what was rotten (three real bugs and one
broken contract). Greenfield would have rediscovered all of those the
hard way.

---

## Architecture: where the safety lives

```
LLM client (Claude, GPT, etc.)
       │  MCP/HTTP — auth headers, tool calls
       ▼
┌──────────────────────────────────────────────────────────┐
│  Aperture proxy :8001                                    │
│  ────────────────────────────────────────────────────────│
│  1. Header passthrough (x-api-key, authorization)        │
│  2. session_id template substitution (loud-fail on miss) │
│  3. Cache lookup (CachedResult contract, isError gate)   │
│  4. Schema overlay applied (read-only positive list)     │
│  5. Background tokenization (drain on lifespan shutdown) │
│  6. Attribution event → SQLite + JSONL                   │
└──────────────────────────────────────────────────────────┘
       │  Streamable HTTP
       ▼
Composio Tool Router (https://backend.composio.dev/tool_router/{session_id}/mcp)
```

Two design choices set the tone:

**Lifespan-owned shared state, not module globals.** The proxy uses
Starlette's lifespan to construct `UpstreamClient`, `SessionRegistry`,
`TokenizerService`, `SchemaOverlay`, and the cache store (Redis or
in-memory) once at startup. Every request reads from the lifespan
context. The proxy survives `tools/list` and `tools/call` storms because
nothing is being constructed in the request hot path.

**Stateless on credentials.** The proxy never persists or logs auth
headers. They flow inbound from the LLM client's MCP request, get filtered
to drop hop-by-hop headers, and forward verbatim to Composio. If you
restart the proxy, every active LLM session continues without
re-authentication — because the proxy never had the credentials in the
first place. (Verified by `pre-commit-config.yaml` running
`scripts/secret_scan.py` on every commit — refuses to commit
`ak_…` / `sk-ant-api…` / `ca__…` patterns.)

---

## The deep-fix sequence

The project went through five iterations, each driven by an audit that
caught the previous iteration's hand-wavy claims.

| Commit | Driver | Net change |
|---|---|---|
| `13ff81d1` | Codex audit found proxy was a transparent forwarder, not actually wired | proxy uses `dispatch`, headers forwarded, session template substituted, cache/tokenizer/overlay/attribution all owned by lifespan |
| `cd0b1562` | Re-review found 11 residual gaps | `CachedResult` unwrap after dispatch, `isError` sentinel preventing cache poisoning, defense-in-depth in proxy `SchemaOverlay`, schema-shape `_to_anthropic_tool` adapter, silent-pass guard in `run_judge` |
| `e88b9122` | Live LLM judge ran (with bugs from `cd0b1562` fixed) and showed 0% rewriter compression | rewriter rule corpus expanded from ~20 to ~80 patterns, 110 new prompts (now 50–60 per toolkit), `MIN_OVERLAY_VALIDATION_CASES` raised back to 50, hand-wave sweep |
| `28f66883` | Overlay artifact still empty because top-N was dominated by write tools | read-only filter at the optimizer entry point (saves Anthropic budget), `quality_level` flag (`llm_judged` vs `structural_only`), populated artifact with explicit warning |
| `8d617e87` / `ee44a43c` | README + case study | reflects actual state, not aspirational |

The audit-driven cadence matters more than any individual fix. **Every
commit message has a stated motivation tied to a finding from the
previous review.** No "looks good, ship it." Every layer was assumed
broken until verified working.

---

## Four bugs mocks would never have caught

### 1. The silent-pass false-accept

**The setup.** The LLM judge runs each prompt through Haiku with the
original schema, then again with the candidate schema. If `tool_use.name`
and the normalized arguments match across the two calls, that prompt
"passes." If 100% of prompts pass, the candidate is accepted into the
overlay.

**The bug.** When an Anthropic call failed (4xx/5xx, network error,
credit exhaustion), the helper returned `JudgeOutcome(tool_name=None,
tool_input_normalized=None, raw_response_text="")`. The judge then ran:

```python
if (
    original_outcome.tool_name != candidate_outcome.tool_name
    or original_outcome.tool_input_normalized != candidate_outcome.tool_input_normalized
):
    failures.append(...)
    continue
haiku_passes += 1
```

Both outcomes were `None`. `None != None` is `False`. The check passed.
Every prompt "agreed." Every candidate was "accepted."

**The signal that exposed it.** The budget tracker. After running the
live pipeline against 8 candidates with a $2 cap:

```
budget: {'calls': 0, 'total_input_tokens': 0, 'total_output_tokens': 0,
         'total_usd': 0.0, 'cap_usd': 2.0, ...}
GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE | cases=30 accepted=True reason=None
```

`calls: 0` and `accepted: True` cannot both be true. Either no calls were
made (in which case how did anything pass?) or the budget tracker was
broken. Reading the logs showed 99 entries of `WARNING: anthropic call
failed` interleaved with `accepted=True` results.

**The fix.** In live mode, an outcome with no `tool_name`, no `tool_input`,
AND no `raw_response_text` is now classified as a hard failure with
reason `anthropic_call_failed`. The judge treats it as disagreement, not
agreement. A test fakes an empty-outcome live call and asserts the
rejection reason.

```python
def _is_failed_call(outcome: JudgeOutcome) -> bool:
    return (
        outcome.tool_name is None
        and outcome.tool_input_normalized is None
        and not outcome.raw_response_text
    )

if live and (_is_failed_call(original_outcome) or _is_failed_call(candidate_outcome)):
    api_failures += 1
    failures.append({"prompt": prompt, "stage": "haiku",
                     "reason": "anthropic_call_failed", ...})
    continue
```

**Lesson.** When a result looks too clean — the integration test that
"passes" with $0.00 spent, the validation report that accepts every
candidate without exception — the success path may be a no-op. Audit
call counts and budget telemetry, not just return values. *Silence is not
success.*

### 2. The schema-shape 400 cascade

**The setup.** Composio's `client.tools.get()` returns OpenAI-shape tool
schemas with `parameters` (matching OpenAI's function-calling API).
Anthropic's `client.messages.create(tools=...)` requires `input_schema`.

**The bug.** The judge passed schemas verbatim:

```python
response = client.messages.create(
    model=model,
    max_tokens=512,
    tools=[schema] + similar_tools,  # ← still has `parameters`, not `input_schema`
    messages=[{"role": "user", "content": prompt}],
)
```

Every call returned `400 — "tools.0.custom.input_schema: Field required"`.
Combined with bug #1, this meant every prior "live LLM judge run" in this
codebase had been 400-erroring then silent-passing. An earlier session's
verification report claimed `"Live Anthropic judge accepted GITHUB_CREATE_ISSUE
rewrite under budget — passed: true, haiku_passes: 5, sonnet_passes: 1,
budget.total_usd: 0.0194"`. That was almost certainly five 400 errors plus
five `None == None` agreements.

**The fix.** A `_to_anthropic_tool()` adapter that detects either shape:

```python
def _to_anthropic_tool(schema: dict) -> dict:
    if isinstance(schema.get("function"), dict):
        schema = schema["function"]  # OpenAI envelope shape
    return {
        "name": schema.get("name") or schema.get("slug") or "_unknown_",
        "description": schema.get("description") or "",
        "input_schema": (
            schema.get("input_schema")
            or schema.get("parameters")
            or {"type": "object", "properties": {}}
        ),
    }
```

After the fix, a fresh live run made **522 successful calls (474 Haiku +
48 Sonnet)** spending $1.36, accepted two candidates that the safety
filter then correctly blocked because they were write tools.

**Lesson.** Every external integration needs at least one live round-trip
before "wired" is a defensible claim. Mocks reproduce the shapes you
specified; they don't expose contracts you got wrong.

### 3. The stale artifact / correct code trap

**The setup.** A reviewer flagged that `_overlay.json` shipped 18 tools —
2 of which `policy.yaml` classified as `write` (`GITHUB_ADD_OR_UPDATE_TEAM_*`).
Those should never be in the overlay.

**The bug.** I checked the code. `_overlay_safe()` rejected
`policy.operation_type in {write, auth}`. The unit test passed. Every
write tool was correctly filtered out *by the function*.

The artifact was wrong. It had been generated by a prior commit that
didn't have the filter. The function was correct, the file was stale,
and the test suite verified the function — not the file the function
produced six commits ago.

**The fix.** Two parts. First, regenerate the artifact (which produced 0
entries — the truthful state under the new gates). Second, add a
defense-in-depth check at the proxy's `SchemaOverlay.reload()` so even a
hand-edited or stale overlay can't apply rewrites to non-read tools at
runtime:

```python
def reload(self) -> None:
    # ... load JSON ...
    safe: dict[str, dict] = {}
    for slug, fields in raw.items():
        policy = load_cache_policy(slug)
        if policy.operation_type not in _SAFE_OPERATION_TYPES:  # {"read"}
            logger.warning(
                "overlay: dropping %s (operation_type=%s; only 'read' is allowed)",
                slug, policy.operation_type,
            )
            self._dropped_unsafe.append(slug)
            continue
        safe[slug] = fields
    self._tools = safe
```

**Lesson.** When you add a gate, every artifact downstream of that gate
is suspect until regenerated. Tests verify functions; they don't verify
files.

### 4. The CachedResult leak through dispatch

**The setup.** The cache layer returns `CachedResult(data, cached_age_seconds,
original_cost_tokens)` — a frozen dataclass — on hit, and the raw payload
on miss. The proxy's `_call_tool` hands the result to `_content_blocks()`
which serializes it to MCP `TextContent`.

**The bug.** `_content_blocks()` only knew about `dict | str | list[ContentBlock]`.
A `CachedResult` instance hit the fallback and got JSON-dumped, leaking
internal fields (`cached_age_seconds`, `original_cost_tokens`) to the
LLM client. Worse, on a cache hit the LLM saw a wrapper instead of the
payload it asked for.

**The fix.** Unwrap immediately after dispatch, before the response path
ever sees the value:

```python
response = await dispatch(name, arguments, context=context, ...)
response = unwrap_cached_result(response)        # CachedResult → payload
response = _strip_upstream_error_marker(response) # cache sentinel cleanup
tokenizer.schedule_count(response, context.model, on_complete=...)
return _content_blocks(response)
```

A test now drives an ASGI `tools/call` round-trip with a mocked dispatch
that returns a `CachedResult` and asserts the response text contains the
payload but not `"CachedResult"` or `"cached_age_seconds"`.

**Lesson.** When a contract changes (we added the dataclass for cache
hits), audit every consumer that handles that contract's outputs.

---

## Engineering decisions worth defending

**Defense-in-depth, not single-point gates.** The schema overlay is
gated by *four independent checks*: the rewriter never strips
safety/auth keywords (`send`, `delete`, `oauth`, `token`, `permission`);
`_overlay_safe` requires `operation_type == "read"` AND
`validation_cases_run >= 50`; `SchemaOverlay.reload` applies the same
read-only positive list at startup; the LLM judge silent-pass guard
prevents false-accepts on transport errors. The 522-call live run
verified the chain: judge accepted 2 write tools, the next layer down
blocked both. **Every layer must independently catch the same failure
the previous layer would catch.** That's what defense-in-depth means.

**Positive lists, not deny lists.** I tightened `_overlay_safe` from
"reject `operation_type in {write, auth}`" to "accept only `operation_type ==
"read"`." `unknown` is now blocked by default. This means a tool that
hasn't been classified yet (a new Composio addition, say) cannot
accidentally land in the overlay just because policy.yaml hasn't been
updated. The cost: false-negatives on legitimately safe tools that
haven't been classified. The benefit: zero false-positives on misclassified
write tools.

**Quality-graded artifacts with explicit metadata.** Without Anthropic
credits, I can't ship an `llm_judged` overlay. Two bad options: pretend
or ship nothing. I chose a third: ship a `structural_only` overlay with
explicit metadata. The file has `quality_level: "structural_only"` at
the top. Each entry has `validation.quality_level: "structural_only"`.
The dashboard renders a yellow warning banner. The README's overlay
section spells out the difference between the two paths and the recipe
for upgrading. **Operators can choose risk levels with full disclosure.**
This is the same pattern that ships in mature systems — security headers
have `Strict` vs `Lax` SameSite cookies; databases have `READ COMMITTED`
vs `SERIALIZABLE` isolation levels; the user picks the tradeoff knowing
the tradeoff.

**Fail loud, not silent.** `url_for()` raises `ValueError(f"upstream URL
template requires {missing!r}…")` instead of substituting `""` and
producing `https://backend.composio.dev/tool_router//mcp`. The truncation
fallback in the rewriter (which used to truncate to 18 words when no
rules matched) was removed; the rewriter now returns `[]` and the upper
layer records `rewriter_no_candidate` cleanly. **Truncation, default
substitution, "best effort" — these are silent-failure machines.**
Every place I removed one of these felt like turning the lights on.

**Read-only ranker filter as architectural insurance.** A late-stage fix.
The optimizer ranks candidate fields by `tokens × frequency`. Without
filtering, the live run on Composio's 1,700+ tool registry spent budget
on `GITHUB_ADD_*`/`GITHUB_OR_UPDATE_*` slugs that the safety filter would
later reject. By filtering at rank time to `operation_type == "read"`,
the live judge only ever sees candidates that *could* land in the
overlay. Money saved per run, more relevant top-N, no behavior change to
the safety semantics. **Found by reading the budget telemetry from a
real run.**

---

## What I learned about MCP

Most engineers haven't worked with the Model Context Protocol yet. Six
specifics I learned the hard way:

**Streamable HTTP, not WebSocket.** Aperture is built on
`mcp.server.lowlevel.Server` and `StreamableHTTPSessionManager` with
`stateless=True`. The transport is HTTP with Server-Sent Events for
streaming responses. This means the proxy can be horizontally scaled —
each request is independent, the LLM client gets routed to whichever
proxy instance handles it. Sessions live in the LLM client's headers
(`mcp-session-id`), not in the proxy's process memory.

**FastMCP is the wrong abstraction for upstream-defined tools.** I
considered using FastMCP's `@mcp.tool` decorator. It forces static tool
declarations: every tool has to be defined in the proxy's code at
startup. Aperture's tools are *Composio's* — published dynamically by
the upstream. The low-level `Server` class with `@server.list_tools()`
and `@server.call_tool()` decorators is the right abstraction; it
forwards `tools/list` requests to upstream and returns whatever Composio
publishes. (The schema overlay applies on top of that response.)

**Lifespan-owned state, not module globals.** The `lifespan`
context-manager pattern in MCP server lets you construct shared
resources once at startup and pass them to request handlers via
`server.request_context.lifespan_context`. The proxy uses this for the
upstream client, session registry, tokenizer service, schema overlay,
and cache store. Every request reads from the lifespan context;
nothing is constructed in the request hot path.

**Headers are everything.** Composio's tool-router URL embeds the
session ID as a path segment
(`https://backend.composio.dev/tool_router/{session_id}/mcp`) and
authentication as an `x-api-key` header. The proxy must (a) substitute
`{session_id}` from the inbound request's `mcp-session-id` header,
(b) forward `x-api-key` and other auth headers verbatim without dropping
them, and (c) NOT forward hop-by-hop headers like `accept`,
`content-length`, `transfer-encoding` (those are owned by the
proxy's own HTTP transport).

**MCP `CallToolResult.isError` is not in the JSON content payload.**
The error flag is at the result level, not in the response body. When
the proxy forwards a result, the cache layer needs to know "this was an
error" so it doesn't store it. I solved that by tagging the dict
payload with `_aperture_upstream_error: True` before it reached the
cache, then stripping the marker before the response went out to the
LLM. The cache's `_success_response` learned to look for this marker.

**Background tokenization needs strong references.** A naive
`asyncio.create_task(_runner())` can be garbage-collected mid-flight if
nothing holds a reference. The `TokenizerService` keeps an
`_inflight: set[asyncio.Task]` and uses
`task.add_done_callback(self._inflight.discard)` to clean up. On
lifespan shutdown, `tokenizer.drain(timeout=2.0)` waits for in-flight
tasks to complete (or cancels them) before tearing down the upstream
client.

These are MCP-specific lessons that don't generalize to "any HTTP
proxy." If you're hiring for a role that touches MCP — building tooling
on top of Anthropic's protocol, building MCP servers/clients, or
integrating with platforms that use MCP — these are the gotchas that
matter.

---

## Tradeoffs I considered and rejected

**Qdrant / vector / semantic cache.** v1 uses exact-match keys
(`sha256(stable_serialize_payload(params))`). A semantic cache would
hit on near-duplicate prompts even when the args differ slightly. I
rejected this for v1 because (a) the policy-version coupling
(`:p1:`) and scope isolation are hard enough to get right with exact
match, and adding semantic similarity adds an entire new failure mode
(false-hits on tools where args matter exactly), and (b) the
attribution data we collect should drive the decision: if `SEARCH_TOOLS`
near-duplicates are common, semantic caching is worth it; if they're
rare, it's not. v2 territory.

**FastMCP.** Already covered above. The dynamic-tool issue made it
wrong for this use case. Worth flagging because it's the obvious
"why didn't you just use…" question from a reviewer.

**Writing into Composio's registry directly.** v1's schema optimizer
produces an *overlay file* the proxy applies on outbound responses —
it does not commit rewrites back into Composio's registry. I rejected
direct registry writes because (a) we don't have internal Composio
access, (b) committing to a shared registry would affect every other
Composio user, not just our LLM, and (c) keeping rewrites in our
overlay means we can roll back instantly without coordination with
Composio. The overlay path is operationally clean.

**Doing schema optimization at runtime instead of offline.** I
considered making the proxy *compute* description rewrites on the fly
during a `tools/list`. Rejected: rewrite generation needs the full LLM
judge run (50 prompts × 2 schemas × Haiku/Sonnet) which costs ~$0.20
per candidate. Doing that at runtime would cost dollars per
`tools/list`. Offline batch optimization with a cached overlay is
strictly better.

**A unified telemetry pipeline (OpenTelemetry).** v1 uses an in-process
SQLite event log + JSONL sink. Production-grade observability would mean
OTel traces, Prometheus metrics, structured logs to ELK/Datadog. I
deferred this because the v1 acceptance criteria specifically asked for
the `/api/v3.1/...` API shape that mirrors Composio's own attribution
endpoints. Cleaner to ship that single contract first, then add OTel
on top later.

---

## Layered testing strategy

Different test layers exist to catch different failure modes:

**Unit tests (most of the 234)** — pure functions, deterministic, no
network. Catches type errors, wrong-shape bugs, off-by-one, contract
violations within a module. Cheap to run; runs in pre-commit.

**Replay-mode LLM-judge tests** — JSON fixtures recorded from real
Anthropic responses, played back in tests. Catches regressions in the
judge's accept/reject logic without burning $0.20 per CI run. Test
fixtures are seeded by hand for the basic cases and (in production)
recorded automatically by setting `replay_dir=` during a live run.

**ASGI integration tests** — `tests/proxy/test_proxy_integration.py`
boots `create_app()` with `TestClient`, monkey-patches
`UpstreamClient` and `dispatch`, sends real MCP `initialize` and
`tools/list` / `tools/call` JSON-RPC requests through the full Starlette
+ MCP middleware stack, and asserts that auth headers, session IDs, and
dispatch routing all work end-to-end. This is what catches the "proxy
is not actually wired" class of bug.

**Compression regression tests** — `test_rewriter_compression_benchmark.py`
runs the rewriter against the actual fixture corpus and asserts ≥20%
aggregate reduction on top-15 plus ≥9/15 fields with non-zero savings.
This locks in the rewriter quality so a future change can't silently
regress it back to 0%.

**Live integration tests** — gated on `live_composio`, `live_anthropic`,
`live_redis` env-var markers. NEVER run in CI. Run manually when
verifying a new version against real Composio + Anthropic. The 522-call
live judge run was via this mechanism.

The mistake I made early was **conflating layers**: thinking that
passing unit tests + a replay-mode test + an ASGI test meant the live
integration was good. It wasn't, twice (the silent-pass and
schema-shape bugs). Each layer needs at least one corresponding live
verification. Each layer's coverage is real but bounded.

**Lesson.** Test coverage isn't a single number. It's a layer matrix.
A bug in the live-integration row can sit there for months while
unit-test coverage is "100%."

---

## The privacy decision

The Anthropic `count_tokens` API is **opt-in via
`APERTURE_USE_ANTHROPIC_TOKENIZER=true`**. By default, the tokenizer
falls back to `cl100k_base` (the OpenAI GPT-4 tokenizer) and returns
counts marked `tokenizer_is_approximate=True`.

The decision: every Composio tool response body that flowed through
the proxy would otherwise be sent to Anthropic for tokenization,
regardless of which LLM the user is actually using. A user running on
GPT-4 would have payload bodies leave for Anthropic. A user running on
self-hosted Llama would have payload bodies leave for Anthropic. That
is a privacy regression no operator would accept.

The fix is the opt-in flag plus a default that keeps everything
local. The accuracy tradeoff is real — `cl100k_base` over-estimates
Anthropic-bound counts by ~5% on average — but it's the right
default for cross-cutting privacy. If you're running Claude end-to-end
and want exact counts, opt in. The flag is documented in the README
env-var matrix and in `docs/security_privacy.md`.

**Lesson.** When a feature has a cross-cutting privacy implication,
opt-in is the right default. The flag costs you nothing operationally;
silently shipping the regression costs you trust.

---

## The Phase 1 baseline that wasn't done

The original v1 plan called for "Phase 1 — Real-token-cost baseline":
100 real Composio sessions across the seven connected toolkits, captured
through the proxy, tokenized end-to-end, used to inform the
`policy.yaml` ranking and the schema-optimizer top-N selection.

I didn't do it. Two reasons: (a) the user had not provided active
Composio sessions across all seven toolkits — only GitHub had a real
connected account in the live integration; (b) Anthropic credits ran
out before the schema optimizer had a chance to run live against the
real session data.

What this absence costs: the schema optimizer's "top-15 candidates"
ranking is computed from `tokens × frequency_prior`. The frequency_prior
in v1 is a uniform constant (every tool has frequency=1) because we
have no real session data. With real session data, `frequency` would be
"how often did this tool appear in the 100-session corpus" — and the
ranking would prioritize tools that get called a lot, not just tools
with long descriptions. The current overlay's 4 tools (GitHub list
issues, Notion query, Slack search, Gmail search) are the right ones
to optimize first regardless of frequency, but a real-session baseline
would have surfaced ~20-30 more.

The pipeline is right; the input data is approximate. A future
engineer with funded Anthropic and active Composio sessions can rerun
the optimizer with real frequency data and the overlay will populate
naturally.

**Lesson.** When a planned input dataset doesn't materialize, the
pipeline isn't broken — its inputs are approximate. Be explicit about
what's approximate. Don't pretend the uniform-frequency-prior is the
same as real data.

---

## Working with AI agents — the meta-skill

The hardest part of this project wasn't writing the code. It was
catching the four times an AI agent (Codex or a subagent dispatched
from this session) reported "done, all wired" when key pieces were not
actually wired.

The first reviewer subagent caught that `13ff81d1` had not actually wired
the proxy. It said `dispatch` wasn't being called. I had been about to
celebrate. Reading the actual `server.py` showed the reviewer was right —
`call_tool` had `headers={}` and never invoked `dispatch`.

The Codex audit caught that the prior session's verification claimed
`"Live MCP tools/list works"` but had only verified `initialize`. The
real `tools/list` was 401-erroring upstream because the proxy passed
empty headers. That single finding triggered the whole `cd0b1562` fix
sequence.

The second subagent caught that `_overlay.json` had stale write-tool
entries even though the safety filter was correctly written. That's
what surfaced the regenerate-the-artifact rule.

The third subagent caught the `Requires` substitution bug — sentence-position
matters for "filter that requires the user to authenticate," which my
greedy regex was mangling into "filter that Required: user."

The pattern: **a subagent's "ready to commit" is one data point, not a
verification.** The discipline that mattered was running fresh
verification commands myself, reading the actual output, and pushing
back when claims didn't match evidence. I ran `git diff --stat`, I read
the changed files, I executed the live judge knowing what numbers to
expect, I checked the budget tracker output character-by-character.

I also learned to *use subagents adversarially*. Three of the four
reviewer subagents were dispatched with prompts like *"Don't trust my
claims — run the commands and read the actual code. If tests fail, that's
a Critical issue regardless of cause."* That framing produced reviews
that found things, instead of reviews that nodded along.

**The durable skill is "evidence over claims."** It's the same discipline
that separates a senior engineer from a mid-level one when working with
any unreliable collaborator (a flaky CI system, a vendor with shaky
docs, an agent with a tendency to hallucinate). AI tools accelerate
building. Verifying what they actually built is what separates code that
looks good from code that holds up under load.

---

## Quantified results

| Metric | Before | After |
|---|---|---|
| Pytest count | 197 → 234 | +37 net new tests across 5 commits |
| Ruff findings | 0 | 0 |
| Rewriter compression on top-15 fixtures | 0% | **26.4%** (locked in by `test_rewriter_achieves_at_least_20pct_reduction_on_top_15`) |
| Prompt fixtures per toolkit | 30 | 50–60 (260 total) |
| `policy.yaml` tools classified | 9 | **1,700+** across 15 toolkits |
| Anthropic calls validated live | 0 verified-real | **654** (132 + 522) |
| Independent reviewer sign-offs | 1 | 4 (3 subagents + 1 Codex audit) |
| Overlay safety layers | 1 (writer only) | 4 (writer, loader, rewriter, judge guard) |
| Latent bugs caught and locked in | 0 | 4 (silent-pass, schema-shape, stale-artifact, CachedResult-leak) |
| Hand-wavy "PR N will…" docstrings | 12 | 0 |

---

## What "done" actually means

I scoped this carefully and I don't pretend otherwise.

**The code is well-engineered.** Separated concerns. Type-checked.
Defensively guarded. Adversarially reviewed. The full test suite and ruff
checks pass.
Defense-in-depth verified live. Real bugs caught and locked in by
regression tests. The Codex audit + 3 subagent reviews produced concrete
findings, every one of which got addressed and committed with traceable
motivation.

**The product has named gaps.** The overlay ships at `quality_level:
structural_only` (4 read tools, 9 fields, 64 tokens saved) because
Anthropic credits ran out mid-validation; upgrading to `llm_judged` is a
one-line script run when funded. The original plan's "100 real-session
baseline" was never collected. End-to-end benchmark runs that would
produce the actual `aperture_full ≥50% savings` numbers haven't been
committed (the runner exists; the numbers don't). A leaked Composio API
key is in git history at `5b6b6847` and would need to be rotated +
optionally history-scrubbed before public release.

What I *didn't* do: claim the overlay is production-grade when it isn't.
The README labels it `structural_only`, the dashboard surfaces a warning
banner, the file's own metadata says so, the case-count threshold for
the production path is documented. **A future engineer reading the repo
gets the truth, not a marketing document.**

That honesty is itself an engineering decision. It's a load-bearing one
in a product where the wrong overlay rewriting a `delete` tool's
description could cause data loss in someone's GitHub repo. I'd rather
ship `structural_only` with a banner than `llm_judged`-labeled content
that wasn't actually judged.

---

## What I'd do differently next time

- **Bake the live integration test into CI from day one.** Most of these
  bugs would have been caught immediately if every PR ran one
  smoke-test live call against staging Anthropic. The cost is small;
  the catch rate is enormous.
- **Make budget telemetry the canary.** A budget tracker that says
  "$0.00 spent" while accepting candidates is a louder signal than any
  test result. Surface it in CI, make a CI step assert
  `budget.calls > 0` whenever the live judge runs.
- **Write the artifact-regeneration rule into the contributing guide.**
  When a new safety gate lands, a checklist item must be "regenerate
  every dependent artifact." I learned this by hitting the trap; future
  contributors shouldn't have to.
- **Treat "PR N will…" docstrings as a code smell.** If the docstring
  describes the future, it's already wrong. Prune ruthlessly.
- **Run an adversarial subagent against every commit, not just at
  milestones.** The marginal cost is small. The marginal catch rate is
  high.

---

## Closing

Aperture v1 isn't a finished product. It's a deeply-engineered code base
with a clearly-labeled preview-grade artifact and a recipe for upgrading
when external dependencies are restored. Five iterations driven by
adversarial review found four latent bugs that mocks would never have
caught, locked them in by regression tests, and produced a verifiable,
honest audit trail.

What this project taught me is that **engineering AI-augmented systems
is mostly about the meta-skill of refusing to accept "looks good"
without evidence.** The agents accelerate. The verification disciplines
the acceleration into something trustworthy. Without that discipline,
you ship a codebase that passes its own tests and silently fails in
production. With it, you ship something a future engineer can read,
understand, and extend without surprises.

Show this to a hiring engineer at Composio (or anywhere else). Point at
the 522-call live verification, the four-layer defense-in-depth, the
silent-pass guard test, the explicit `quality_level` metadata. Then
point at the named gaps. **The combination is the signal.** Anyone can
ship code; few engineers will tell you exactly what they didn't finish
and why.

---

### Repository pointers

- `README.md` — setup, architecture, env vars, scripts
- `docs/architecture.md` — system design walkthrough
- `docs/V1_CODEX_REVIEW.md` — independent audit driving `13ff81d1`
- `docs/schema_optimization.md` — Component C pipeline + quality levels
- `docs/security_privacy.md` — opt-in tokenizer rationale, scope safety
- `aperture/proxy/server.py` — the actual proxy, ~370 lines
- `aperture/schema_optimizer/llm_judge.py` — judge with the silent-pass guard
- `aperture/schema_optimizer/reports.py` — the optimizer pipeline
- `tests/proxy/test_proxy_integration.py` — the ASGI live-wiring tests
- `tests/schema_optimizer/test_llm_judge_replay.py` — the replay-mode judge tests
- `tests/schema_optimizer/test_rewriter_compression_benchmark.py` — the regression floor
