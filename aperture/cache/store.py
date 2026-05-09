"""Cache store with Upstash Redis backend and in-memory fallback."""

import json
import time
from typing import Any

from aperture.config import Config


class _MemoryStore:
    """In-memory cache for local development / demos."""

    def __init__(self):
        self._data: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ex: int = 0) -> bool:
        expires_at = time.time() + ex if ex else None
        self._data[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> bool:
        self._data.pop(key, None)
        return True

    def ping(self) -> bool:
        return True


class CacheStore:
    """Simple cache store using Upstash Redis (or in-memory fallback).

    Uses a module-level singleton so cache survives across runner instances.
    """

    _instance: "CacheStore | None" = None

    def __new__(cls) -> "CacheStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._redis = None
            cls._instance._memory = _MemoryStore()
        return cls._instance

    def _client(self):
        if self._redis is None:
            try:
                self._redis = Config.redis_client()
            except RuntimeError:
                # No Redis configured — use in-memory fallback
                self._redis = self._memory
        return self._redis

    def get(self, key: str) -> Any | None:
        """Fetch a cached value. Returns None if not found."""
        try:
            result = self._client().get(key)
            if result is None:
                return None
            return json.loads(result)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """Store a value with TTL. Returns True on success."""
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            self._client().set(key, serialized, ex=ttl_seconds)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        try:
            self._client().delete(key)
            return True
        except Exception:
            return False

    def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self._client().ping()
        except Exception:
            return False
