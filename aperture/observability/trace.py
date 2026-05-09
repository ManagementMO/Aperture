"""Run trace builder and export."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aperture.contracts import ApertureRunConfig
from aperture.observability.events import EventEmitter


@dataclass
class RunTrace:
    """Complete trace of a single Aperture-enhanced run."""

    run_id: str
    config: ApertureRunConfig
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str | None = None
    events: EventEmitter = field(init=False)
    summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.events = EventEmitter(self.run_id)

    def finish(self) -> None:
        self.ended_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "config": {
                "run_id": self.config.run_id,
                "tenant_id": self.config.tenant_id,
                "user_id": self.config.user_id,
                "connected_account_id": self.config.connected_account_id,
                "model": self.config.model,
                "effort_mode": self.config.effort_mode,
                "cache_bypass": self.config.cache_bypass,
            },
            "events": self.events.all_events(),
            "summary": self.summary,
        }

    def export_jsonl(self, path: Path) -> None:
        """Append this run as one JSONL line."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")

    def compute_summary(self) -> dict[str, Any]:
        """Compute aggregate metrics from events."""
        token_events = self.events.token_events()
        cache_events = self.events.cache_events()

        total_raw = sum(e.get("raw_tokens", 0) for e in token_events)
        total_compressed = sum(e.get("compressed_tokens", 0) for e in token_events)
        total_saved = sum(e.get("tokens_saved", 0) for e in token_events)

        cache_hits = sum(1 for e in cache_events if e.get("cache_status") == "hit")
        cache_misses = sum(1 for e in cache_events if e.get("cache_status") == "miss")
        api_calls_avoided = sum(1 for e in cache_events if e.get("api_call_avoided"))

        self.summary = {
            "total_raw_tokens": total_raw,
            "total_compressed_tokens": total_compressed,
            "total_tokens_saved": total_saved,
            "compression_ratio": round(total_compressed / max(total_raw, 1), 3),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "api_calls_avoided": api_calls_avoided,
        }
        return self.summary
