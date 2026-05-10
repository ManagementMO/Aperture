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

Today's coverage: **126 tools** across the seven seed toolkits + Composio
meta auth slugs. The YAML coverage gate at
`tests/cache/test_policy_yaml_coverage.py` enforces ≥100. To scale to ≥800,
run `python scripts/seed_cache_policy.py --live`.

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
| `COMPOSIO_SEARCH_TOOLS` | yes | Schema+plan portion cached at scope=public; `connection_status` always re-fetched and merged. See `aperture/cache/search_tools_cache.py`. |
| `COMPOSIO_MULTI_EXECUTE_TOOL` | yes (per-inner-tool) | Partial-batch fan-out — each inner tool checked against its own `policy.yaml` entry; misses are forwarded as a subset; results merged back into original ordering. |
| `COMPOSIO_GET_TOOL_SCHEMAS` | no | Args almost always vary; cache hit rate would be near-zero. |
| `COMPOSIO_MANAGE_CONNECTIONS` | no | Auth tool. |
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
  PR 5 will add `AsyncRedisCacheStore` for the proxy; PR 2's bridge uses
  the existing sync interface through `asyncio.to_thread`.

## Events

Every cache lookup emits a `CacheEvent` to:
- in-memory list (test inspection)
- JSONL sink (if `APERTURE_EVENT_SINK_PATH` set)
- SQLite event log (if `APERTURE_SQLITE_EVENT_LOG` set or
  `event_log_sqlite.set_default_log()` called)

`cache_status` ∈ `{hit, miss, bypass, not_cacheable, error}`. `api_call_avoided`
flags whether the upstream was skipped. `tokens_saved_estimate` counts the
cached payload's tokens (recomputed on read; PR 5 will persist this at
write time).

## Verifying

```bash
uv run pytest tests/cache/                # 30+ tests
uv run pytest tests/proxy/test_cache_*.py # cache-aware proxy paths
```

The coverage gate test fails if `policy.yaml` drops below 100 tools.
The seed-classifier test parametrizes 23 representative slugs to lock
the classification rules.
