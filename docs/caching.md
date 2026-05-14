# Caching (Component A)

The cache lives in `aperture/cache/` and is wired into the MCP proxy via
`aperture/proxy/cache_bridge.py` and the per-meta-tool intercept handlers.

## Policy

Defined in `aperture/cache/policy.yaml`. Loaded by
`aperture/cache/policy.py:load_cache_policy(tool_slug) → CachePolicy`.

Each entry has `cacheable | operation_type | privacy_scope | ttl_seconds | matching | reason?`.

The default block at the top is deny-by-default — any tool not listed
returns `cacheable=False, operation_type=unknown`. Adding a new tool
requires an explicit YAML entry. The auto-classifier
`scripts/seed_cache_policy.py` produces these from a slug list.

Today's coverage: **1768+ tools** across 15 live Composio toolkits
(github, gmail, slack, notion, linear, googlesheets, supabase, youtube,
googlecalendar, googledocs, googledrive, asana, jira, discord,
salesforce) + Composio meta auth slugs + the legacy seed list. The YAML
coverage gate at `tests/cache/test_policy_yaml_coverage.py` enforces
≥1500. The current count is the union of `scripts/seed_cache_policy.py
--live --user-id mo` and `scripts/_seed_tool_list.json`. To regenerate,
run the seed script with live Composio credentials.

## Key format

```
aperture:v1:p1:{privacy_scope}:{scope_id}:{tool_slug}:{sha256_hex}
```

- `v1` — cache schema version (this codebase). Distinguishes from any
  v0 keys that might still be in the store after a migration.
- `p1` — policy YAML version. Bump `version:` in `policy.yaml` (currently 1)
  to invalidate all entries on the next read. See `aperture/cache/key_builder.py`.
- `privacy_scope` — `public | account | user | project | session`. Determines
  which scope_id field gets read from the `ExecutionContext`.
- `scope_id` — `none` for public; otherwise the connected_account_id /
  user_id / project_id / session_id depending on scope.
- `tool_slug` — the inner tool slug, e.g. `GITHUB_GET_REPO`. For
  SEARCH_TOOLS responses, the cache uses `COMPOSIO_SEARCH_TOOLS` itself.
- `sha256_hex` — full SHA-256 of the deterministically-serialized
  normalized params dict. Full hex (not truncated) so collision is
  cryptographically impossible.

## What's cacheable

The decision matrix from `aperture/proxy/meta_tools.py`:

| Meta tool | Cacheable | Notes |
|---|---|---|
| `COMPOSIO_SEARCH_TOOLS` | yes | Schema+plan portion cached at scope=public. `search_tools_cache.py` can merge fresh `connection_status` when a status-only callback is available; the proxy does not issue a second full SEARCH_TOOLS upstream call just to refresh status. |
| `COMPOSIO_MULTI_EXECUTE_TOOL` | yes (per-inner-tool) | Partial-batch fan-out — each inner tool checked against its own `policy.yaml` entry; misses are forwarded as a subset; results merged back into original ordering. |
| `COMPOSIO_GET_TOOL_SCHEMAS` | no | Args almost always vary; cache hit rate would be near-zero. |
| `COMPOSIO_MANAGE_CONNECTIONS` | no | Auth tool. |
| `COMPOSIO_WAIT_FOR_CONNECTIONS` | no | Connect-only auth-flow wait primitive; forwarded and tokenized if present. |
| `COMPOSIO_REMOTE_WORKBENCH` | no | Stateful sandbox. |
| `COMPOSIO_REMOTE_BASH_TOOL` | no | Non-deterministic. |

Inside `MULTI_EXECUTE`, every individual tool call is classified by
`policy.yaml`. Writes/auth never cache. Reads cache per their TTL.

## Bypass

A request can opt out per-call:
- HTTP header: `X-Aperture-Cache-Bypass: true|1|yes` (case-insensitive)
- Request metadata: `aperture_cache_bypass: true`
- `ExecutionContext.cache_bypass=True` (programmatic)

Parser: `aperture/cache/bypass.py:cache_bypass_requested(headers, metadata)`.
Wired into the proxy at request entry; the Path-2 SDK runner takes the
field directly via `ApertureRunConfig`.

## Failed responses

`aperture/cache/interceptor.py:_success_response` skips storage when:
- `response.get("success") is False`
- `response.get("error")` is truthy

So a transient API failure can't poison the cache.

## Stores

- `InMemoryCacheStore` (default for tests + local dev) — per-process dict
  with TTL and `age_seconds()` accounting.
- `RedisCacheStore(redis_url)` — backed by `redis-py`'s sync `Redis.from_url`.
  Wraps values in a `{stored_at, value}` envelope so `age_seconds()` works.
  The proxy selects this store at startup when `APERTURE_REDIS_URL` is set;
  otherwise it uses the in-memory store.

## Events

Every cache lookup emits a `CacheEvent` to:
- in-memory list (test inspection)
- JSONL sink (if `APERTURE_EVENT_SINK_PATH` set)
- SQLite event log (if `APERTURE_SQLITE_EVENT_LOG` set or
  `event_log_sqlite.set_default_log()` called)

`cache_status` in `{hit, miss, bypass, not_cacheable, error}`. `api_call_avoided`
flags whether the upstream was skipped. `tokens_saved_estimate` counts the
original payload cost stored with the cache entry. `maybe_execute_with_cache()`
returns `CachedResult(data, cached_age_seconds, original_cost_tokens)` on
hits and the raw upstream response on misses.

## Verifying

```bash
uv run pytest tests/cache/                # 30+ tests
uv run pytest tests/proxy/test_cache_*.py # cache-aware proxy paths
```

The coverage gate test fails if `policy.yaml` drops below 1500 tools.
The seed-classifier test parametrizes 23 representative slugs to lock
the classification rules.
