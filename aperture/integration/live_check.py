"""Live Composio validation workflow for Aperture."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aperture.cache.policy import load_cache_policy
from aperture.cache.redis_store import InMemoryCacheStore
from aperture.config import ApertureConfig
from aperture.integration.composio_adapter import ComposioToolExecutor
from aperture.integration.pipeline import aperture_tool_result_pipeline
from aperture.observability.event_emitter import (
    clear_in_memory_events,
    get_in_memory_cache_events,
    get_in_memory_token_events,
)
from aperture.tokenization.token_counter import count_tokens_for_payload
from aperture.types import ExecutionContext


def _json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must decode to a JSON object")
    return parsed


async def run_live_check(
    *,
    toolkit: str,
    tool_slug: str | None,
    arguments: dict[str, Any],
    out_path: Path,
    connected_account_id: str | None = None,
    execute: bool = False,
    tool_router: bool = False,
    search_query: str | None = None,
) -> dict[str, Any]:
    """Run live Composio schema fetch and optional read-tool execution through Aperture."""

    config = ApertureConfig.from_env()
    if not config.composio_api_key:
        raise RuntimeError("COMPOSIO_API_KEY is required")

    clear_in_memory_events()
    executor = ComposioToolExecutor(config)
    tools = executor.get_tools(toolkits=[toolkit], slug=tool_slug)
    schema_count = count_tokens_for_payload(tools, model="gpt-4o-mini")
    result: dict[str, Any] = {
        "toolkit": toolkit,
        "tool_slug": tool_slug,
        "schema_tokens": asdict(schema_count),
        "schema_fetch_ok": True,
        "tool_router": None,
        "execute_requested": execute,
        "execution": None,
        "cache_events": [],
        "token_events": [],
    }

    if tool_router:
        session_tools = executor.session_tools(user_id=config.composio_user_id, toolkits=[toolkit.lower()])
        session_tool_count = count_tokens_for_payload(session_tools, model="gpt-4o-mini")
        session_search = executor.session_search(
            search_query or f"{toolkit} read tool",
            user_id=config.composio_user_id,
            toolkits=[toolkit.lower()],
        )
        result["tool_router"] = {
            "session_tools_tokens": asdict(session_tool_count),
            "search_tokens": asdict(count_tokens_for_payload(session_search, model="gpt-4o-mini")),
            "search_preview": session_search,
        }

    if execute:
        if not tool_slug:
            raise RuntimeError("--tool-slug is required when --execute is set")
        policy = load_cache_policy(tool_slug)
        if not policy.cacheable or policy.operation_type != "read":
            raise RuntimeError(f"Refusing live execution for non-cacheable/read policy tool: {tool_slug}")
        if policy.privacy_scope == "account" and not connected_account_id:
            connected_account_id = executor.find_active_connected_account_id(toolkit, config.composio_user_id)
        toolkit_version = os.getenv("COMPOSIO_TOOL_VERSION") or executor.get_toolkit_version(toolkit)
        context = ExecutionContext(
            project_id=os.getenv("APERTURE_PROJECT_ID", "live_project"),
            user_id=config.composio_user_id,
            session_id=os.getenv("APERTURE_SESSION_ID", "live_session"),
            connected_account_id=connected_account_id,
            toolkit_slug=toolkit.upper(),
            tool_slug=tool_slug,
            meta_tool_slug=None,
            model="gpt-4o-mini",
        )
        store = InMemoryCacheStore()

        def execute_fn() -> object:
            if tool_router:
                return executor.session_execute(
                    tool_slug=tool_slug,
                    arguments=arguments,
                    user_id=config.composio_user_id,
                    toolkits=[toolkit.lower()],
                    account=connected_account_id,
                )
            return executor.execute(
                    tool_slug=tool_slug,
                    arguments=arguments,
                    user_id=config.composio_user_id,
                    connected_account_id=connected_account_id,
                    version=toolkit_version,
                )

        first = await aperture_tool_result_pipeline(tool_slug, arguments, context, execute_fn, cache_store=store)
        second = await aperture_tool_result_pipeline(tool_slug, arguments, context, execute_fn, cache_store=store)
        result["execution"] = {
            "first_payload_tokens": asdict(count_tokens_for_payload(first, model="gpt-4o-mini")),
            "second_payload_tokens": asdict(count_tokens_for_payload(second, model="gpt-4o-mini")),
            "first_payload_preview": first,
            "second_payload_preview": second,
        }
    result["cache_events"] = [asdict(event) for event in get_in_memory_cache_events()]
    result["token_events"] = [asdict(event) for event in get_in_memory_token_events()]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def live_check_from_env(out_path: Path, execute: bool = False) -> dict[str, Any]:
    """Run live check using environment variables."""

    return asyncio.run(
        run_live_check(
            toolkit=os.getenv("COMPOSIO_TOOLKIT", "GITHUB"),
            tool_slug=os.getenv("COMPOSIO_TOOL_SLUG") or None,
            arguments=_json_arg(os.getenv("COMPOSIO_TOOL_ARGS")),
            connected_account_id=os.getenv("COMPOSIO_CONNECTED_ACCOUNT_ID") or None,
            execute=execute,
            tool_router=os.getenv("COMPOSIO_USE_TOOL_ROUTER", "").lower() in {"1", "true", "yes"},
            search_query=os.getenv("COMPOSIO_SEARCH_QUERY") or None,
            out_path=out_path,
        )
    )
