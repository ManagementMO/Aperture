# Security and Privacy

## Anthropic tokenizer is opt-in (handoff plan decision #5)

By default, `count_tokens_for_payload()` for Claude models does NOT call
Anthropic's `messages.count_tokens` API. The reason: every payload sent
to that API leaves the process for Anthropic's servers, regardless of
whether the user's actual LLM provider is Anthropic. Defaulting that on
would silently exfiltrate Composio tool outputs (Gmail bodies, GitHub
private repo metadata, Slack messages) to Anthropic for OpenAI/Gemini/etc.
users who never expected it.

To enable, set `APERTURE_USE_ANTHROPIC_TOKENIZER=true`. Then:
- The flag controls the tokenizer choice, not whether tokens are counted —
  default behavior still counts via cl100k_base (close approximation, marked
  `tokenizer_is_approximate=True` in events).
- An `ANTHROPIC_API_KEY` is required for the real path; missing keys fall
  back to cl100k.
- Per-payload responses are cached in the proxy's in-process LRU
  (`TokenizerService`), so a given payload only leaves the process once
  per 24h.

Document this in any external-facing onboarding for the proxy: developers
adopting the hosted variant should know that enabling
`APERTURE_USE_ANTHROPIC_TOKENIZER` makes their Composio responses visible
to Anthropic's servers.

## Cache scope safety

Three guarantees enforced by `aperture/cache/key_builder.py`:

1. **Write/auth tools never cache.** Every YAML entry classified
   `operation_type: write` or `operation_type: auth` has `cacheable: false`.
   Tested by `tests/cache/test_policy_yaml_coverage.py:test_no_write_or_auth_tool_is_cacheable`.

2. **Public scope rejects connected-account context.** If a request
   carries a `connected_account_id` and the policy says scope=public, the
   key builder returns `None` and the call doesn't cache. This prevents
   "I logged into my private GitHub account, asked for a public repo, and
   another user's request got served my personalized repo metadata."
   Tested by `tests/cache/test_key_builder.py:test_public_scope_rejects_connected_account_context`.

3. **Required scope identifier missing → no cache.** Account-scoped reads
   without a `connected_account_id`, user-scoped reads without a `user_id`,
   etc. — all return `None` from the key builder. Failure mode is
   "no cache hit," never "wrong cache hit."

## Cache key version coupling

Cache keys carry a `p1:` segment that's the policy YAML version. When
`policy.yaml`'s `version:` field bumps (e.g., after a TTL re-classification),
all cache entries from the previous policy are silently invalidated because
no new request can produce a key with the old segment. This avoids
serving cached entries that were classified under an older policy.

## Failed responses don't poison the cache

`aperture/cache/interceptor.py:_success_response` skips storage when:
- `response.get("success") is False`
- `response.get("error")` is truthy

A transient API failure can't get cached and served to subsequent
requests as if it were a successful result.

## Event log retention

The SQLite event log is append-only. There's no retention policy in the
v1 codebase — `aperture/observability/event_log_sqlite.py` doesn't TTL or
delete rows. Operators MUST configure their own retention if running the
proxy in production.

The JSONL secondary sink also grows unbounded; it's gitignored
(`reports/events.jsonl`) so test runs and benchmark runs don't accumulate
in version control.

## Auth pass-through

The proxy receives the developer's `x-api-key` header on every inbound
MCP request and forwards it, along with non-hop-by-hop auth/context
headers, to Composio's MCP URL. The proxy NEVER persists or logs the
header value. See
`aperture/proxy/upstream.py:UpstreamClient` — the header dict flows from
the inbound request straight into the outbound HTTPX call.

For hosted multi-tenant deployment (out of scope for v1), the proxy would
issue an Aperture-side API key and map it to the developer's Composio key
via encrypted storage. v1 is local-dev or single-tenant only.

## SOC2 implications

If the proxy is deployed as a hosted service, every Composio tool
payload that flows through it is visible to Aperture's infrastructure.
That's a data-processing relationship that requires:
- TLS in transit (uvicorn / starlette default)
- Encrypted storage for the SQLite event log (deployment concern)
- Tenant isolation in the v3.1 API endpoints — currently the endpoints
  filter by `user_id`/`session_id` on the request, but cross-user query
  isolation depends on the deployer's auth layer
- Documented retention for the event log

These are Phase 7+ concerns for a hosted deployment; the v1 codebase
ships with all the hooks needed but doesn't bake an auth layer.

## What's never logged

- API keys (env vars stay in env; not embedded in events)
- Cache key bodies (only the SHA-256 hash via `cache_key_hash()`)
- Raw payload contents in default JSONL/SQLite (only token counts +
  byte counts; the cache layer DOES store payloads but only in the
  configured cache store, not in the event log)

## Secret scanning

The repository includes a local pre-commit hook (`aperture-secret-scan`)
that blocks known Composio and Anthropic credential formats from being
committed. This does not rotate previously exposed keys; leaked provider
keys must still be revoked in the provider dashboard and removed from git
history before a public release.
