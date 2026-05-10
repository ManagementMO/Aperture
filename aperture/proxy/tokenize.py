"""Async tokenizer service for the proxy hot path.

Wraps `aperture.tokenization.token_counter.count_tokens_for_payload` with a
result cache (keyed by `(model, sha256(serialized))`). For the proxy, the
hot-path rule (Plan-Agent 1 §6) is: NEVER block the response on tokenization.
Style 1: kick off the upstream forward and tokenization concurrently with
asyncio, return as soon as the upstream completes; tokenization continues
in the background and emits its event when it lands.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass

from aperture.tokenization.serializers import stable_serialize_payload
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import TokenCount

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CacheEntry:
    count: TokenCount
    cached_at: float


class TokenizerService:
    """Module-instance-owned tokenizer wrapper.

    Per-process LRU cache (we don't go to Redis here; the count is cheap to
    recompute compared to the network round-trip, and Anthropic's count_tokens
    is the actual expensive path which has its own caching layer below).
    """

    def __init__(self, max_entries: int = 10_000, ttl_seconds: int = 24 * 3600) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
        # Strong refs so Python doesn't GC fire-and-forget tasks mid-flight.
        # See PEP 4 "asyncio.create_task strong reference" warning, 3.11+.
        self._inflight: set[asyncio.Task] = set()

    @staticmethod
    def _key(serialized: str, model: str | None) -> str:
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
        return f"{model or '_unspecified'}::{digest}"

    async def count(self, payload: object, model: str | None) -> TokenCount:
        """Return token count, blocking only on cache miss → tokenizer call.

        For the proxy hot path, prefer count_async_fire_and_forget() which
        schedules tokenization without awaiting it.
        """
        serialized = (
            payload if isinstance(payload, str) else stable_serialize_payload(payload)
        )
        key = self._key(serialized, model)
        now = time.time()

        async with self._lock:
            entry = self._cache.get(key)
            if entry is not None and (now - entry.cached_at) < self._ttl_seconds:
                self._stats["hits"] += 1
                return entry.count
            if entry is not None:
                # Expired — fall through to recompute.
                self._cache.pop(key, None)
                self._stats["evictions"] += 1
            self._stats["misses"] += 1

        # Tokenization is CPU-bound; offload to a worker thread so we don't
        # block the event loop on long payloads (>100kB serialized).
        count = await asyncio.to_thread(count_tokens_for_payload, payload, model)

        async with self._lock:
            if len(self._cache) >= self._max_entries:
                # Naive LRU: evict oldest.
                oldest_key = min(self._cache, key=lambda k: self._cache[k].cached_at)
                self._cache.pop(oldest_key, None)
                self._stats["evictions"] += 1
            self._cache[key] = _CacheEntry(count=count, cached_at=now)

        return count

    def schedule_count(
        self,
        payload: object,
        model: str | None,
        *,
        on_complete=None,
    ) -> asyncio.Task:
        """Fire-and-forget tokenization for the proxy hot path.

        Returns the asyncio.Task so the caller can `await` later if it wants;
        otherwise the task runs in the background. `on_complete(token_count)`
        is invoked when done (for the attribution layer to emit its event).
        """

        async def _runner():
            try:
                count = await self.count(payload, model)
            except Exception as exc:
                logger.warning("aperture.proxy.tokenize.schedule_count failed: %s", exc)
                return None
            if on_complete is not None:
                try:
                    result = on_complete(count)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    logger.warning(
                        "aperture.proxy.tokenize on_complete callback failed: %s",
                        exc,
                    )
            return count

        task = asyncio.create_task(_runner())
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        return task

    async def drain(self, timeout: float | None = None) -> None:
        """Wait for in-flight tokenization tasks to finish (lifespan shutdown)."""

        if not self._inflight:
            return
        pending = list(self._inflight)
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            for task in pending:
                if not task.done():
                    task.cancel()

    def stats(self) -> dict[str, int]:
        return {**self._stats, "entries": len(self._cache), "inflight": len(self._inflight)}

    def clear(self) -> None:
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
