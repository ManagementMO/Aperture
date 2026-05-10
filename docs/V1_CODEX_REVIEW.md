# V1 Codex Review

## 1. Executive Summary

The previous report is partly true but overstates the production readiness of the system. The unit suite, ruff, policy size, Path-2 live cache check, live Anthropic judge, and standalone v3.1 API all verify. The actual MCP proxy, however, is still effectively a PR1 transparent forwarder: it does not pass inbound auth headers, does not substitute the `{session_id}` upstream URL template, does not call `router.dispatch`, and therefore does not use the cache, token attribution, session tracking, tokenizer service, or schema overlay code. A live `tools/list` through the proxy fails with an upstream 401 hidden as an MCP error. The dashboard builds and the API proxy works, but the Schema Overlay page fetches HTML instead of JSON. The tracked verification document also contains a real Composio API key and connected-account ID. Components A/B/C work in isolated or Path-2 paths; the MCP-proxy-backed product is not production-ready.

## 2. Per-Claim Verification Table

| Claim from `docs/V1_FINAL_VERIFICATION.md` | Verdict | Evidence |
|---|---:|---|
| Branch is `v1-realignment` at final verification head | CONFIRMED | `git rev-parse --abbrev-ref HEAD && git rev-parse --short HEAD` -> `v1-realignment`, `5b6b6847`. Note: the doc body says branch @ `6f066469`, so the doc itself is stale about the commit it verifies. |
| `197 tests passing, 1 skipped` | CONFIRMED | `uv run pytest --tb=no -q` -> `197 passed, 1 skipped in 54.57s`. |
| `0 ruff findings` | CONFIRMED | `uv run ruff check aperture/ tests/ scripts/` -> `All checks passed!`. |
| `1768 tools in policy.yaml` | CONFIRMED | `grep -c '^  [A-Z]' aperture/cache/policy.yaml && wc -l aperture/cache/policy.yaml` -> `1768`, `11923 aperture/cache/policy.yaml`. |
| MCP proxy serves a real `initialize` | CONFIRMED, narrow | Booted `uv run python -m aperture.proxy`; `curl -X POST http://127.0.0.1:8001/mcp/ ... initialize` -> HTTP 200, `content-type: text/event-stream`, `serverInfo.name="aperture-proxy"`. This only proves initialize, not tool forwarding. |
| MCP proxy can forward real Composio meta-tool traffic | DISPROVEN | `curl ... method="tools/list" -H "x-api-key: $COMPOSIO_API_KEY"` -> HTTP 200 carrying MCP error `unhandled errors in a TaskGroup`. Proxy log shows `POST https://backend.composio.dev/tool_router/%7Bsession_id%7D/mcp "HTTP/1.1 401 Unauthorized"`. Source confirms `server.py:83` and `server.py:92` pass `headers={}` and never substitute the template. |
| Live cache hit on second call | CONFIRMED for Path-2 SDK runner, not MCP proxy | First run with `.env` only failed: Composio said no connected account for user `default`. Rerun with `COMPOSIO_USER_ID=mo` and connected account succeeded: `/tmp/aperture_codex_live_check.json` shows cache statuses `miss`, `hit`, `api_call_avoided=true`, `tokens_saved_estimate=3460`. This does not go through the MCP proxy. |
| v3.1 API serves aggregated data | CONFIRMED | With `APERTURE_SQLITE_EVENT_LOG=/tmp/aperture_codex_live_events.db`, `GET /api/v3.1/health` -> token events `2`, cache events `2`; `input_tokens_contributed` -> one bucket, 2358 tokens; `cache_tokens_saved` -> `GITHUB_LIST_REPOSITORY_ISSUES`, hits `1`, misses `1`, tokens_saved `3460`. |
| Live Anthropic tokenizer path works | CONFIRMED | `APERTURE_USE_ANTHROPIC_TOKENIZER=true ... count_tokens_for_payload(..., 'claude-haiku-4-5')` -> `TokenCount(tokens=22, tokenizer='anthropic_count_tokens', tokenizer_is_approximate=False, ...)`; disabled path -> `cl100k_base (claude-fallback)`, approximate. |
| Live LLM judge accepted `GITHUB_CREATE_ISSUE` rewrite under budget | CONFIRMED | Ran `run_judge(... live=True, BudgetTracker(cap_usd=1.0), 5 prompts, Sonnet 20% spot-check)` -> `passed: true`, `haiku_passes: 5`, `sonnet_passes: 1`, `sonnet_disagreements: 0`, `budget.total_usd: 0.0194`, `calls: 12`. |
| `optimize_schemas(live=True)` pipeline | PARTIAL | `optimize_schemas(live=True)` -> `total 90`, `accepted 36`, `tokens_saved 364`, `cases [1]`. This is structural-only validation, not LLM-judged pipeline. |
| Overlay JSON exists with accepted rewrites | CONFIRMED but unsafe/partial | `jq '.stats, (.tools | length)' aperture/schema_optimizer/_overlay.json` -> `accepted: 36`, `tools: 18`. Entries have `validation.cases_run = 1`; many are write/auth-sensitive GitHub tools. |
| Dashboard build | CONFIRMED | `cd aperture-v1-dashboard && npm run build` -> `46 modules transformed`, `built in 371ms`. |
| Dashboard renders 3 pages reading real data | PARTIAL / DISPROVEN for overlay | Vite serves `/`, `/reports`, `/overlay` as HTML and `/api/v3.1/health` proxies correctly. But `fetch('http://127.0.0.1:5180/aperture/schema_optimizer/_overlay.json').json()` fails: `SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON`. The overlay page cannot load its data from the dev server. |
| Hot-path proxy latency p99 <=50ms | DISPROVEN / invalid claim | 50 concurrent `tools/call` requests through the proxy returned 50 HTTP 200 MCP error payloads. Measured p50 `422.61ms`, p95 `518.9ms`, p99 `525.89ms`. Since requests failed upstream, this does not measure successful overhead, but it disproves the unqualified p99 claim. |
| `git status` clean | DISPROVEN in this workspace | `git status --short` before writing this report showed `M AGENTS.md` from prior local work. |
| `docs/HANDOFF_V1_REALIGNMENT.md` available for acceptance review | DISPROVEN | `test -f docs/HANDOFF_V1_REALIGNMENT.md ...` -> `MISSING: docs/HANDOFF_V1_REALIGNMENT.md`. `git ls-tree -r --name-only HEAD | rg HANDOFF` also returned nothing. |

## 3. New Bugs Found

### Critical: MCP proxy is not wired to the v1 product

Files: `aperture/proxy/server.py:72-93`, `aperture/proxy/upstream.py:43`

Failure mode: `server.py` still contains the PR1 transparent handlers. It does not call `router.dispatch`, does not instantiate `SessionRegistry` or `TokenizerService`, does not invoke cache bridge, and does not apply schema overlay or attribution. It also calls upstream with `headers={}` and uses the literal URL template.

Reproduction:

```bash
APERTURE_COMPOSIO_MCP_URL_TEMPLATE='https://backend.composio.dev/tool_router/{session_id}/mcp' uv run python -m aperture.proxy
curl -X POST http://127.0.0.1:8001/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream, application/json' \
  -H 'x-api-key: <redacted>' \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Output: MCP error `unhandled errors in a TaskGroup`; proxy log: upstream 401 to `.../tool_router/%7Bsession_id%7D/mcp`.

Fix: thread inbound headers and request/session identifiers into `UpstreamClient`; substitute `{session_id}`; route `tools/call` through `router.dispatch`; create shared cache/tokenizer/session resources in lifespan; add an integration test that boots the ASGI app and verifies a `tools/list` or `COMPOSIO_SEARCH_TOOLS` call uses mocked upstream headers and dispatch.

### Critical: tracked Markdown leaks a real API key

File: `docs/V1_FINAL_VERIFICATION.md:7`

Reproduction:

```bash
rg -n --no-heading 'ak_|sk-ant|COMPOSIO_API_KEY|ANTHROPIC_API_KEY|ca__' docs README.md .env.example pyproject.toml
```

Output includes `docs/V1_FINAL_VERIFICATION.md:7` with a real Composio API key and connected-account ID. I redacted it in command display, but the file contains the raw secret.

Fix: rotate the leaked key, purge it from git history if this branch ever left the machine, and replace the doc line with redacted identifiers.

### High: schema optimizer LLM wrapper is unusable without monkeypatching

File: `aperture/schema_optimizer/validator.py:84-133`

Failure mode: `validate_schema_rewrite_with_llm_judge()` exposes no `live`, `tracker`, or `replay_dir` arguments. The real function calls `run_judge()` with defaults (`live=False`, `replay_dir=None`) and rejects with `missing_replay_fixtures`.

Reproduction:

```bash
uv run python - <<'PY'
from aperture.schema_optimizer.validator import validate_schema_rewrite_with_llm_judge
orig = {"name":"GITHUB_CREATE_ISSUE","description":"Creates issue.","input_schema":{"type":"object","properties":{"owner":{"type":"string"}},"required":["owner"]}}
cand = {**orig, "description":"Create issue. Required owner."}
print(validate_schema_rewrite_with_llm_judge(orig, cand, ["Create an issue in foo/bar"]))
PY
```

Output: `ValidationResult(validation_cases_run=1, passed=False, rejection_reason='missing_replay_fixtures')`.

Fix: add explicit `live`, `replay_dir`, `tracker`, and `candidate_index` parameters; remove the monkeypatch-based test and assert the wrapper works in replay and live-gated modes.

### High: overlay pipeline is structural-only and can rewrite write/auth tools

Files: `aperture/schema_optimizer/reports.py:34-70`, `aperture/schema_optimizer/_overlay.json`

Failure mode: `optimize_schemas()` uses only `validate_schema_rewrite()`. Current overlay has 36 accepted rewrites across 18 tools, all with `validation.cases_run = 1`; examples include mutation-like tools such as `GITHUB_ACCEPT_REPOSITORY_INVITATION`, `GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE`, and `GITHUB_ADD_EMAIL_ADDRESS_FOR_AUTHENTICATED_USER`.

Reproduction:

```bash
jq '.stats, (.tools | length)' aperture/schema_optimizer/_overlay.json
jq '[.tools | to_entries[] | {tool:.key, cases:(.value|to_entries|map(.value.validation.cases_run)|unique)}][0:3]' aperture/schema_optimizer/_overlay.json
```

Output: `accepted: 36`, `tools: 18`, cases `[1]`.

Fix: block write/auth slugs from overlay unless LLM-judged; integrate `run_judge` into the report pipeline; store judge model, prompt count, and budget summary in overlay metadata.

### High: dashboard Schema Overlay page cannot fetch overlay data

File: `aperture-v1-dashboard/src/pages/SchemaOverlay.tsx:28`

Failure mode: the component fetches `/aperture/schema_optimizer/_overlay.json`, but Vite serves the SPA HTML shell for that path. JSON parse fails.

Reproduction:

```bash
cd aperture-v1-dashboard && APERTURE_V1_BACKEND=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1
node -e "fetch('http://127.0.0.1:5180/aperture/schema_optimizer/_overlay.json').then(r=>r.json()).catch(e=>console.log(e.message))"
```

Output: `Unexpected token '<', "<!doctype "... is not valid JSON`.

Fix: serve overlay via the FastAPI backend or copy it into `aperture-v1-dashboard/public/` at build/dev time and fetch a real static JSON URL.

### Medium: Redis env var is documented but not wired

Files: `aperture/proxy/cache_bridge.py:21-29`, `aperture/config.py:37`

Failure mode: `APERTURE_REDIS_URL` is read by config but no runtime code calls `set_default_store(RedisCacheStore(...))`. The proxy default store is always an in-memory process-local dict unless tests manually inject.

Evidence:

```bash
rg -n "set_default_store|RedisCacheStore|APERTURE_REDIS_URL" aperture tests docs README.md
```

Only tests call `set_default_store`; no production path wires Redis.

Fix: in proxy lifespan or app startup, create `RedisCacheStore(ApertureConfig.from_env().redis_url)` when configured.

## 4. Phase 2 Results

1. Real Composio payload benchmark: I did not overwrite tracked fixtures. I generated three live GitHub read responses and measured the same compression/cache pipeline in `/tmp/aperture_codex_real_payload_metrics.json`. Results: 11,524 raw tokens -> 4,845 compressed tokens, 6,679 saved, 57.96% savings. Per-tool: issues 69.08%, pull requests 49.13%, repository 45.83%. The two account-scoped reads hit cache on the second call; `GITHUB_GET_A_REPOSITORY` was `not_cacheable` with a connected account, matching the public-scope guard.
2. Dashboard browser verification: API proxy works, build works, but overlay data flow fails as described above. Headless Chrome screenshot attempts hung and were killed; HTTP/Node fetch evidence proves the data bug.
3. Hot-path latency under load: 50 concurrent `tools/call` requests through proxy produced MCP error payloads, p50 422.61ms, p95 518.9ms, p99 525.89ms. This is a failed-path measurement, not successful overhead.
4. LLM-judge schema pipeline: not built into repo. Manual `run_judge` works for one candidate, but `optimize_schemas(live=True)` remains structural-only: `total 90`, `accepted 36`, `cases [1]`.
5. `CachedResult`: the dataclass contract is not honored. Reproduction:

```bash
uv run python - <<'PY'
import asyncio
from aperture.cache.interceptor import maybe_execute_with_cache
from aperture.cache.redis_store import InMemoryCacheStore
from aperture.types import ExecutionContext
ctx = ExecutionContext('p','u','s','acct','GITHUB','GITHUB_LIST_REPOSITORY_ISSUES',None,'gpt-4o-mini')
store = InMemoryCacheStore()
async def main():
    async def execute(): return {'ok': True}
    first = await maybe_execute_with_cache('GITHUB_LIST_REPOSITORY_ISSUES', {'owner':'o','repo':'r'}, ctx, execute, store=store)
    second = await maybe_execute_with_cache('GITHUB_LIST_REPOSITORY_ISSUES', {'owner':'o','repo':'r'}, ctx, execute, store=store)
    print(type(first).__name__, first)
    print(type(second).__name__, second)
asyncio.run(main())
PY
```

Output was `dict {'ok': True}` for both miss and hit. Either return `CachedResult` on hits and persist original token cost, or delete the dataclass and update the handoff/docs. I recommend honoring the contract because the v3.1 savings event currently recomputes tokens on cached payloads and loses original-cost metadata.

## 5. New Weak Tests Found

- `tests/proxy/test_skeleton.py` only proves the ASGI app has a `/mcp` mount. It does not verify header pass-through, URL template substitution, dispatch, cache, attribution, or overlay. This is why the production proxy can be PR1-only while tests pass.
- `tests/proxy/test_router.py` verifies `router.dispatch` in isolation, but no test proves `server.py` calls it.
- `tests/schema_optimizer/test_llm_judge_replay.py::test_validator_calls_into_judge_when_present` monkeypatches `run_judge` to inject a replay dir. The real wrapper rejects with `missing_replay_fixtures`.
- `tests/integration/test_live_check.py` monkeypatches `ComposioToolExecutor` with `FakeExecutor`. It is useful unit coverage but does not catch `.env` missing `COMPOSIO_USER_ID` or real connected-account failures.
- `tests/cache/test_policy_yaml_coverage.py` enforces only `len(doc["tools"]) >= 100`, while docs and acceptance criteria discuss >=800 or 1768. A policy shrink to 101 entries would pass.
- `tests/benchmarks/test_task_set.py` asserts `len(tasks) >= 5`; current benchmark acceptance talks about 20 workflows and 50% savings, neither enforced.
- Strengthened tests checked: `uv run pytest tests/proxy/test_intercept_multi_execute.py::test_multi_execute_partial_batch_forwards_only_misses -q` passed, and the assertions do check subset semantics. `uv run pytest tests/schema_optimizer/test_llm_judge_replay.py::test_run_judge_with_missing_replay_fixtures_rejects -q` passed. I did not mutate production code to prove they fail under breakage.

## 6. New Doc Lies Found

- `docs/architecture.md:16-32` says the proxy flow includes router dispatch, intercept handlers, tokenizer, attribution, session registry, and safe fallbacks. `server.py` does none of this.
- `docs/architecture.md:34` shows upstream `/v3/mcp/...`; `ProxyConfig` defaults to `/tool_router/{session_id}/mcp`, and live logs show the literal template is sent URL-escaped.
- `docs/architecture.md:85` lists the old default `APERTURE_COMPOSIO_MCP_URL_TEMPLATE`, not the code default.
- `docs/architecture.md:89` says `APERTURE_REDIS_URL` backs the cache. No production code wires it.
- `docs/architecture.md:115` says 188 tests; actual is 197 passed, 1 skipped.
- `docs/caching.md:3-4` says cache is wired into MCP proxy via intercept handlers. It is not wired into `server.py`.
- `docs/caching.md:71` says bypass is wired into proxy at request entry. It is not.
- `docs/token_attribution.md:61-62` says the proxy uses `schedule_count` and forwards before tokenization completes. The live proxy never instantiates `TokenizerService`.
- `docs/schema_optimization.md:5-7` and `151-153` say the proxy applies overlay to outbound schema responses. It does not.
- `docs/security_privacy.md:78-82` says the proxy forwards inbound `x-api-key` headers verbatim. `server.py` passes `headers={}`, and live proxy traffic gets 401.
- `docs/V1_FINAL_VERIFICATION.md:7` embeds a real Composio API key and connected-account ID.

## 7. Final Scorecard

| Component | Score | Rationale |
|---|---:|---|
| Component A: cache | PARTIALLY WORKING | The cache interceptor, keying, policy, live Path-2 miss/hit, and real payload savings work. But it is not wired into the actual MCP proxy, Redis is not wired from env, and `CachedResult` contract is not honored. |
| Component B: token attribution + v3.1 API | PARTIALLY WORKING | Event emitters, SQLite log, aggregations, API endpoints, and Anthropic token counting work in direct paths. The MCP proxy does not emit attribution events because it never uses the tokenization/attribution layer. |
| Component C: schema description optimizer | HAND-WAVY / PARTIAL | Structural rewrite pipeline and live single-candidate LLM judge work separately. The production overlay is structural-only, accepted with one validation case, includes write-like tools, and is not applied by the proxy or loadable by the dashboard page. |
| MCP proxy | NOT PRODUCTION WORKING | Initialize works. Real tools/list/call forwarding fails because auth headers and session template are not handled, and all v1 intercept logic is unused. |
| Dashboard | PARTIAL | Build and API proxy work. Schema Overlay page data load fails. |

## 8. Highest-Priority Follow-Ups

1. Fix the MCP proxy integration first: header pass-through, template substitution, `router.dispatch`, session/tokenizer/cache/attribution resources, and a live or mocked end-to-end `tools/list`/`tools/call` test through the ASGI app.
2. Rotate the leaked Composio key, scrub `docs/V1_FINAL_VERIFICATION.md`, and add a secret-scan check before any push.
3. Replace the schema optimizer overlay pipeline with a real LLM-gated flow or clearly mark it experimental: no write/auth tool overlays without behavioral validation, and serve overlay JSON through the dashboard/API correctly.
