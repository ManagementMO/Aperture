"""High-level runner that wires tokenization, compression, and caching."""

from pathlib import Path
from typing import Any, Callable

from aperture.cache.interceptor import CachedExecutor
from aperture.compression.engine import compress_tool_output
from aperture.contracts import ApertureRunConfig
from aperture.observability.trace import RunTrace
from aperture.routing.effort_modes import get_effort_config
from aperture.routing.intelligent_effort import EffortDecision, select_effort
from aperture.routing.quality_gate import QualityGateResult, select_mode_for_quality
from aperture.tokenization import count_tokens
from aperture.tokenization.budget_manager import ContextBudgetManager


class ApertureRunner:
    """Run Composio tools with Aperture optimization."""

    def __init__(self, config: ApertureRunConfig):
        self.config = config
        self.trace = RunTrace(run_id=config.run_id, config=config)
        self.cache = CachedExecutor()
        self.budget = ContextBudgetManager()
        self._auto_decisions: list[dict[str, Any]] = []

        if config.effort_mode == "auto":
            self.effort = None
            self._auto_mode = True
        else:
            self.effort = get_effort_config(config.effort_mode)
            self._auto_mode = False

    def run_tool(
        self,
        tool_slug: str,
        arguments: dict,
        executor: Callable[[], Any],
        toolkit_slug: str | None = None,
        user_query: str | None = None,
        required_signals: list[str] | None = None,
        task: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool and return compressed result + observability data.

        Args:
            tool_slug: Composio tool identifier.
            arguments: Tool arguments.
            executor: Callable that returns the raw tool result.
            toolkit_slug: Optional toolkit identifier for telemetry.
            user_query: User's natural-language ask. Used by `auto` mode to
                classify ask difficulty.
            required_signals: Substrings or dot-paths the LLM-bound payload
                MUST still contain. When `effort_mode == "auto"` and signals
                are provided, the quality gate picks the most aggressive
                mode that preserves every signal.
            task: Optional task profile name for task-aware compression.
        """
        arg_count = count_tokens(arguments, self.config.model)
        self.trace.events.emit_token(
            event_type="argument",
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            payload_kind="argument",
            model=self.config.model,
            raw_tokens=arg_count.tokens,
            compressed_tokens=arg_count.tokens,
            tokenizer=arg_count.tokenizer,
            approximate=arg_count.approximate,
        )

        decision: EffortDecision | None = None
        gate_result: QualityGateResult | None = None
        if self._auto_mode:
            decision = select_effort(
                tool_slug=tool_slug,
                arguments=arguments,
                user_query=user_query,
                context_used=self.budget.snapshot.used,
                previous_calls=self.budget.history(),
            )
            compression_mode = decision.compression_mode
            self._auto_decisions.append({"tool_slug": tool_slug, "decision": decision})
        else:
            compression_mode = self.effort.compression_mode

        raw_result, cache_event = self.cache.execute(
            tool_slug=tool_slug,
            arguments=arguments,
            executor=executor,
            config=self.config,
        )
        self.trace.events.emit_cache(
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            cache_status=cache_event.cache_status,
            cache_scope=cache_event.cache_scope,
            cache_key_hash=cache_event.cache_key_hash,
            api_call_avoided=cache_event.api_call_avoided,
            tokens_saved_estimate=cache_event.tokens_saved_estimate,
            reason=cache_event.reason,
        )

        if self._auto_mode and required_signals:
            # Auto mode + signals → calibrate against the actual schema.
            gate_result = select_mode_for_quality(
                raw_payload=raw_result,
                tool_slug=tool_slug,
                required_signals=required_signals,
                ask=user_query,
                model=self.config.model,
                task=task,
            )
            compressed_result = compress_tool_output(
                raw_payload=raw_result,
                tool_slug=tool_slug,
                mode=gate_result.selected_mode,
                model=self.config.model,
                task=task,
            )
            compression_mode = gate_result.selected_mode
        else:
            compressed_result = compress_tool_output(
                raw_payload=raw_result,
                tool_slug=tool_slug,
                mode=compression_mode,
                model=self.config.model,
                task=task,
            )

        self.budget.add_tool_call(
            tool_slug=tool_slug,
            raw_payload=raw_result,
            compressed_payload=compressed_result.compressed_payload,
            cache_hit=cache_event.cache_status == "hit",
        )

        self.trace.events.emit_token(
            event_type="result",
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            payload_kind="compressed" if compression_mode != "off" else "result",
            model=self.config.model,
            raw_tokens=compressed_result.raw_tokens,
            compressed_tokens=compressed_result.compressed_tokens,
            tokens_saved=compressed_result.tokens_saved,
            compression_ratio=compressed_result.compression_ratio,
            cache_status=cache_event.cache_status,
        )

        result: dict[str, Any] = {
            "result": compressed_result.compressed_payload,
            "raw_result": raw_result,
            "compression": compressed_result,
            "cache_event": cache_event,
        }
        if decision:
            result["effort_decision"] = decision
        if gate_result:
            result["quality_gate"] = gate_result
        return result

    def finish(self) -> dict[str, Any]:
        self.trace.finish()
        summary = self.trace.compute_summary()
        summary["budget"] = self.budget.snapshot.to_dict()
        summary["recommendation"] = self.budget.get_recommendation()
        if self._auto_decisions:
            summary["auto_decisions"] = [
                {
                    "tool": d["tool_slug"],
                    "effort": d["decision"].effort_mode,
                    "compression": d["decision"].compression_mode,
                    "reasoning": d["decision"].reasoning,
                    "confidence": round(d["decision"].confidence, 2),
                }
                for d in self._auto_decisions
            ]
        return summary

    def export(self, path: str) -> None:
        self.trace.export_jsonl(Path(path))
