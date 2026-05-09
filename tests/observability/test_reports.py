from datetime import datetime, timezone

from aperture.observability.reports import compression_savings_report, top_expensive_tools_report
from aperture.types import TokenAttributionEvent


def _event(tool: str, tokens: int, saved: int = 0):
    return TokenAttributionEvent(
        event_type="tool_output_compression",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None,
        user_id=None,
        session_id="s1",
        connected_account_id=None,
        toolkit_slug=None,
        tool_slug=tool,
        meta_tool_slug=None,
        payload_kind="compressed",
        model=None,
        tokenizer="fallback",
        tokenizer_is_approximate=True,
        raw_payload_bytes=0,
        compressed_payload_bytes=0,
        raw_tokens=tokens + saved,
        compressed_tokens=tokens,
        input_tokens_contributed=tokens,
        tokens_saved=saved,
        compression_ratio=None,
        cache_status=None,
        aperture_version="0.1.0",
    )


def test_reports_group_by_tool():
    events = [_event("A", 10, 20), _event("A", 5, 10), _event("B", 1, 1)]
    assert "A" in top_expensive_tools_report(events)
    assert "30" in compression_savings_report(events)

