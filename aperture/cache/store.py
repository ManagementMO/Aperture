"""Cache store with Upstash Redis backend and in-memory fallback."""

import json
import os
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
            cls._instance._metadata = {}
        return cls._instance

    def _client(self):
        if os.getenv("PYTEST_CURRENT_TEST"):
            return self._memory
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

    def track_entry(self, key: str, metadata: dict[str, Any], ttl_seconds: int) -> None:
        """Track cache entry metadata for local demo visibility.

        The cached value may live in Redis, but this small metadata index is
        process-local and intentionally avoids storing response payloads.
        """
        now = time.time()
        self._metadata[key] = {
            **metadata,
            "stored_at": now,
            "expires_at": now + ttl_seconds if ttl_seconds else None,
        }

    def tracked_entries(self) -> list[dict[str, Any]]:
        """Return non-expired tracked cache entries for UI display."""
        now = time.time()
        expired = [
            key for key, meta in self._metadata.items()
            if meta.get("expires_at") and now > meta["expires_at"]
        ]
        for key in expired:
            self._metadata.pop(key, None)

        entries: list[dict[str, Any]] = []
        for meta in self._metadata.values():
            expires_at = meta.get("expires_at")
            stored_at = meta.get("stored_at", now)
            entries.append({
                **meta,
                "age_seconds": round(max(0.0, now - stored_at), 1),
                "ttl_remaining_seconds": (
                    round(max(0.0, expires_at - now), 1) if expires_at else None
                ),
            })
        return sorted(entries, key=lambda entry: entry.get("stored_at", 0), reverse=True)

    def clear_tracked(self) -> int:
        """Clear tracked in-memory cache entries and metadata."""
        count = len(self._metadata)
        keys = list(self._metadata.keys())
        for key in keys:
            self.delete(key)
        self._metadata.clear()
        if self._redis is None or self._redis is self._memory:
            self._memory._data.clear()
        return count

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
