from aperture.cache.interceptor import maybe_execute_with_cache
from aperture.cache.redis_store import InMemoryCacheStore
from aperture.observability.event_emitter import clear_in_memory_events, get_in_memory_cache_events
from aperture.types import ExecutionContext


def _context(cache_bypass=False):
    return ExecutionContext("p1", "u1", "s1", "acct_1", "GITHUB", "GITHUB_LIST_ISSUES", None, "gpt-4o-mini", cache_bypass)


async def test_cache_hit_avoids_execution():
    clear_in_memory_events()
    calls = {"count": 0}
    store = InMemoryCacheStore()

    def execute():
        calls["count"] += 1
        return {"ok": True}

    first = await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(), execute, store)
    second = await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(), execute, store)
    assert first == second == {"ok": True}
    assert calls["count"] == 1
    assert any(event.cache_status == "hit" for event in get_in_memory_cache_events())


async def test_bypass_forces_execution():
    calls = {"count": 0}

    def execute():
        calls["count"] += 1
        return {"ok": True}

    await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(cache_bypass=True), execute, InMemoryCacheStore())
    await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(cache_bypass=True), execute, InMemoryCacheStore())
    assert calls["count"] == 2


async def test_failed_response_is_not_cached():
    calls = {"count": 0}
    store = InMemoryCacheStore()

    def execute():
        calls["count"] += 1
        return {"success": False, "error": "failed"}

    await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(), execute, store)
    await maybe_execute_with_cache("GITHUB_LIST_ISSUES", {"q": "auth"}, _context(), execute, store)
    assert calls["count"] == 2

