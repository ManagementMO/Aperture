"""Cache store implementations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol


class CacheStore(Protocol):
    def get(self, key: str) -> object | None:
        """Return cached value or None."""

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        """Store cached value with TTL."""

    def delete(self, key: str) -> None:
        """Delete cached value."""

    def age_seconds(self, key: str) -> int | None:
        """Return cached value age in seconds if available."""


@dataclass
class _Entry:
    value: object
    expires_at: float
    stored_at: float


class InMemoryCacheStore:
    """In-memory cache store for tests and local fixtures."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if time.time() >= entry.expires_at:
            self.delete(key)
            return None
        return entry.value

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        self._entries[key] = _Entry(value=value, expires_at=time.time() + ttl_seconds, stored_at=time.time())

    def delete(self, key: str) -> None:
        self._entries.pop(key, None)

    def age_seconds(self, key: str) -> int | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        return max(0, int(time.time() - entry.stored_at))


class RedisCacheStore:
    """Redis-backed cache store using JSON serialization."""

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except Exception as exc:
            raise RuntimeError("redis package is required for RedisCacheStore") from exc
        self._client = redis.Redis.from_url(redis_url)

    def get(self, key: str) -> object | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)["value"]

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        wrapped = {"stored_at": time.time(), "value": value}
        self._client.setex(key, ttl_seconds, json.dumps(wrapped, sort_keys=True))

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def age_seconds(self, key: str) -> int | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return max(0, int(time.time() - data.get("stored_at", time.time())))
