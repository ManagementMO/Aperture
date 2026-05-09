from aperture.cache.redis_store import InMemoryCacheStore


def test_in_memory_cache_store_roundtrip_and_expiry():
    store = InMemoryCacheStore()
    store.set("k", {"v": 1}, ttl_seconds=10)
    assert store.get("k") == {"v": 1}
    assert store.age_seconds("k") is not None
    store.delete("k")
    assert store.get("k") is None

