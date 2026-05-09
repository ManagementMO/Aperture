"""High-level integration that wires tokenization, compression, and caching."""

from typing import Any, Callable

from aperture.cache.interceptor import CachedExecutor
from aperture.compression.engine import compress_tool_output
from aperture.contracts import ApertureRunConfig, CompressionResult
from aperture.observability.trace import RunTrace
from aperture.routing.effort_modes import get_effort_config
from aperture.tokenization import count_tokens


class ApertureRunner:
    """Main entry point for running tools with Aperture optimization."""

    def __init__(self, config: ApertureRunConfig):
        self.config = config
        self.trace = RunTrace(run_id=config.run_id, config=config)
        self.cache = CachedExecutor()
        self.effort = get_effort_config(config.effort_mode)

    def run_tool(
        self,
        tool_slug: str,
        arguments: dict,
        executor: Callable[[], Any],
        toolkit_slug: str | None = None,
    ) -> dict[str, Any]:
        """Execute a single tool with full Aperture optimization.

        Returns:
            Dict with 'result', 'compression', 'cache_event', 'token_event'
        """
        # Count argument tokens
        arg_tokens = count_tokens(arguments, self.config.model)
        self.trace.events.emit_token(
            event_type="argument",
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            payload_kind="argument",
            model=self.config.model,
            raw_tokens=arg_tokens.tokens,
            compressed_tokens=arg_tokens.tokens,
            tokenizer=arg_tokens.tokenizer,
            approximate=arg_tokens.approximate,
        )

        # Execute with cache
        raw_result, cache_event = self.cache.execute(
            tool_slug=tool_slug,
            arguments=arguments,
            executor=executor,
            config=self.config,
        )
        self.trace.events._events.append({
            "timestamp": self.trace.started_at,
            **cache_event.__dict__,
        })

        # Compress result (skip if cache hit — already compressed)
        if cache_event.cache_status == "hit":
            compressed_result = CompressionResult(
                compressed_payload=raw_result,
                raw_tokens=0,
                compressed_tokens=0,
                tokens_saved=0,
                compression_ratio=1.0,
                strategy="cache_hit",
            )
        else:
            compressed_result = compress_tool_output(
                raw_payload=raw_result,
                tool_slug=tool_slug,
                mode=self.effort.compression_mode,
                model=self.config.model,
            )

        # Record token event
        self.trace.events.emit_token(
            event_type="result",
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            payload_kind="compressed" if self.effort.compression_mode != "off" else "result",
            model=self.config.model,
            raw_tokens=compressed_result.raw_tokens,
            compressed_tokens=compressed_result.compressed_tokens,
            tokens_saved=compressed_result.tokens_saved,
            compression_ratio=compressed_result.compression_ratio,
            cache_status=cache_event.cache_status,
        )

        return {
            "result": compressed_result.compressed_payload,
            "raw_result": raw_result,
            "compression": compressed_result,
            "cache_event": cache_event,
        }

    def finish(self) -> dict[str, Any]:
        """Finish the run and return summary."""
        self.trace.finish()
        return self.trace.compute_summary()

    def export(self, path: str) -> None:
        """Export run trace to JSONL."""
        from pathlib import Path

        self.trace.export_jsonl(Path(path))
