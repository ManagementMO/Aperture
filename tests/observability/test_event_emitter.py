from datetime import datetime, timezone

from aperture.observability.event_emitter import (
    clear_in_memory_events,
    emit_token_event,
    get_in_memory_token_events,
)
from aperture.types import TokenAttributionEvent


def test_emit_token_event_does_not_store_raw_payload(tmp_path):
    clear_in_memory_events()
    event = TokenAttributionEvent(
        event_type="input_tokens_contributed",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None,
        user_id=None,
        session_id="s1",
        connected_account_id=None,
        toolkit_slug="GITHUB",
        tool_slug="GITHUB_LIST_ISSUES",
        meta_tool_slug=None,
        payload_kind="result",
        model="gpt-4o-mini",
        tokenizer="o200k_base",
        tokenizer_is_approximate=False,
        raw_payload_bytes=10,
        compressed_payload_bytes=None,
        raw_tokens=5,
        compressed_tokens=None,
        input_tokens_contributed=5,
        tokens_saved=0,
        compression_ratio=None,
        cache_status=None,
        aperture_version="0.1.0",
    )
    emit_token_event(event, sink_path=tmp_path / "events.jsonl")
    assert get_in_memory_token_events() == [event]
    assert "raw_secret" not in (tmp_path / "events.jsonl").read_text()

