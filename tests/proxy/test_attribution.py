"""Tests for the proxy's TokenAttributionEvent builders."""

from __future__ import annotations


import pytest

from aperture import __version__
from aperture.observability.event_emitter import clear_in_memory_events, get_in_memory_token_events
from aperture.proxy.attribution import (
    attribute_to_dict,
    build_cache_hit_savings_event,
    build_meta_tool_response_event,
    emit_meta_tool_event,
)
from aperture.types import ExecutionContext, TokenCount


def _ctx(meta="COMPOSIO_SEARCH_TOOLS") -> ExecutionContext:
    return ExecutionContext(
        project_id="p1",
        user_id="u1",
        session_id="s_a",
        connected_account_id="acct_1",
        toolkit_slug=None,
        tool_slug=None,
        meta_tool_slug=meta,
        model="gpt-4o",
    )


def _count(tokens: int = 100, approximate: bool = False) -> TokenCount:
    return TokenCount(
        tokens=tokens,
        tokenizer="o200k_base",
        tokenizer_is_approximate=approximate,
        payload_bytes=tokens * 4,
    )


@pytest.fixture(autouse=True)
def _reset_events():
    clear_in_memory_events()
    yield
    clear_in_memory_events()


def test_meta_tool_response_event_has_canonical_event_type():
    event = build_meta_tool_response_event(context=_ctx(), raw_count=_count(150))
    assert event.event_type == "meta_tool_response"


def test_meta_tool_response_event_uses_aperture_version():
    event = build_meta_tool_response_event(context=_ctx(), raw_count=_count())
    assert event.aperture_version == __version__


def test_meta_tool_response_event_payload_kind_for_multi_execute():
    ctx = _ctx(meta="COMPOSIO_MULTI_EXECUTE_TOOL")
    event = build_meta_tool_response_event(context=ctx, raw_count=_count())
    assert event.payload_kind == "execution_result"


def test_meta_tool_response_event_payload_kind_for_search_tools():
    event = build_meta_tool_response_event(context=_ctx(), raw_count=_count())
    assert event.payload_kind == "schema"


@pytest.mark.parametrize(
    "meta",
    [
        "COMPOSIO_MANAGE_CONNECTIONS",
        "COMPOSIO_WAIT_FOR_CONNECTIONS",
        "COMPOSIO_REMOTE_WORKBENCH",
        "COMPOSIO_REMOTE_BASH_TOOL",
    ],
)
def test_meta_tool_response_event_payload_kind_for_non_schema_meta_tools(meta):
    event = build_meta_tool_response_event(context=_ctx(meta=meta), raw_count=_count())
    assert event.payload_kind == "execution_result"


def test_meta_tool_response_event_carries_session_turn():
    event = build_meta_tool_response_event(
        context=_ctx(), raw_count=_count(), session_turn=7
    )
    assert event.session_turn == 7


def test_compressed_count_reduces_input_tokens_contributed():
    raw = _count(200)
    compressed = _count(80)
    event = build_meta_tool_response_event(
        context=_ctx(), raw_count=raw, compressed_count=compressed
    )
    assert event.input_tokens_contributed == 80
    assert event.tokens_saved == 120
    assert event.compression_ratio < 1


def test_cache_hit_savings_event_marks_full_savings():
    cached = _count(150)
    event = build_cache_hit_savings_event(context=_ctx(), cached_payload_count=cached)
    assert event.event_type == "cache_hit_savings"
    assert event.cache_status == "hit"
    assert event.tokens_saved == 150
    assert event.input_tokens_contributed == 150


def test_emit_meta_tool_event_writes_to_in_memory_log():
    emit_meta_tool_event(context=_ctx(), raw_count=_count(123))
    events = get_in_memory_token_events()
    assert len(events) == 1
    assert events[0].input_tokens_contributed == 123


def test_attribute_to_dict_serializes_event():
    event = build_meta_tool_response_event(context=_ctx(), raw_count=_count())
    d = attribute_to_dict(event)
    assert d["event_type"] == "meta_tool_response"
    assert d["aperture_version"] == __version__
    # Round-trip through dict shouldn't lose session_turn
    event2 = build_meta_tool_response_event(
        context=_ctx(), raw_count=_count(), session_turn=3
    )
    d2 = attribute_to_dict(event2)
    assert d2["session_turn"] == 3
