"""Event emission for token attribution, compression, and caching."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from aperture.contracts import CacheEvent, TokenEvent


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventEmitter:
    """Collects events for a single run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._events: list[dict[str, Any]] = []

    def emit_token(
        self,
        event_type: str,
        toolkit_slug: str | None = None,
        tool_slug: str | None = None,
        payload_kind: str = "result",
        model: str | None = None,
        tokenizer: str = "cl100k_base",
        approximate: bool = False,
        raw_tokens: int = 0,
        compressed_tokens: int = 0,
        tokens_saved: int = 0,
        compression_ratio: float | None = None,
        cache_status: str | None = None,
    ) -> None:
        event = TokenEvent(
            event_type=event_type,
            run_id=self.run_id,
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            payload_kind=payload_kind,
            model=model,
            tokenizer=tokenizer,
            approximate=approximate,
            raw_tokens=raw_tokens,
            compressed_tokens=compressed_tokens,
            tokens_saved=tokens_saved,
            compression_ratio=compression_ratio,
            cache_status=cache_status,
        )
        self._events.append({"timestamp": _now_iso(), **asdict(event)})

    def emit_cache(
        self,
        toolkit_slug: str | None,
        tool_slug: str,
        cache_status: str,
        cache_scope: str = "user",
        cache_key_hash: str | None = None,
        schema_version: str | None = None,
        api_version: str | None = None,
        freshness_policy: str | None = None,
        api_call_avoided: bool = False,
        tokens_saved_estimate: int = 0,
        reason: str | None = None,
    ) -> None:
        event = CacheEvent(
            run_id=self.run_id,
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            cache_status=cache_status,
            cache_scope=cache_scope,
            cache_key_hash=cache_key_hash,
            schema_version=schema_version,
            api_version=api_version,
            freshness_policy=freshness_policy,
            api_call_avoided=api_call_avoided,
            tokens_saved_estimate=tokens_saved_estimate,
            reason=reason,
        )
        self._events.append({"timestamp": _now_iso(), **asdict(event)})

    def all_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def token_events(self) -> list[dict[str, Any]]:
        return [e for e in self._events if "event_type" in e and e["event_type"] in {
            "schema", "argument", "result", "compressed", "cache"
        }]

    def cache_events(self) -> list[dict[str, Any]]:
        return [e for e in self._events if "cache_status" in e]
