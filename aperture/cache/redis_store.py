"""Cache store implementations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol


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
    """Redis-backed cache store using JSON serialization.

    All Redis network calls are wrapped in try/except — Redis being down
    must NEVER break the proxy or SDK runner. Failures log a warning and
    return safe defaults (None for reads, no-op for writes). Per
    adversarial review 2026-05-10: the previous implementation let
    Redis exceptions bubble up, and while the @safe decorators in the
    proxy caught them, the SDK runner path didn't — and the silent
    failure on `set` meant subsequent identical calls would also miss.
    """

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except Exception as exc:
            raise RuntimeError("redis package is required for RedisCacheStore") from exc
        self._client = redis.Redis.from_url(redis_url)
        import logging
        self._logger = logging.getLogger(__name__)

    def get(self, key: str) -> object | None:
        try:
            raw = self._client.get(key)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("redis get failed for key prefix %s...: %s", key[:32], exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)["value"]
        except (KeyError, ValueError, TypeError) as exc:
            # Corrupt/old-format entry. Treat as miss + best-effort delete.
            self._logger.warning("redis get returned malformed value for %s...: %s", key[:32], exc)
            self.delete(key)
            return None

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        wrapped = {"stored_at": time.time(), "value": value}
        try:
            self._client.setex(key, ttl_seconds, json.dumps(wrapped, sort_keys=True))
        except Exception as exc:  # noqa: BLE001
            # Cache miss propagates silently to the caller — they got their
            # response from upstream and we just couldn't persist it.
            self._logger.warning("redis set failed for %s...: %s", key[:32], exc)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("redis delete failed for %s...: %s", key[:32], exc)

    def age_seconds(self, key: str) -> int | None:
        try:
            raw = self._client.get(key)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("redis age_seconds get failed for %s...: %s", key[:32], exc)
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return max(0, int(time.time() - data.get("stored_at", time.time())))
