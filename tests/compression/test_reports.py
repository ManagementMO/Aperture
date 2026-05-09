from datetime import datetime, timezone

from aperture.compression.reports import build_compression_report
from aperture.types import TokenAttributionEvent


def test_build_compression_report():
    event = TokenAttributionEvent(
        event_type="tool_output_compression",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None,
        user_id=None,
        session_id="s1",
        connected_account_id=None,
        toolkit_slug="GITHUB",
        tool_slug="GITHUB_LIST_ISSUES",
        meta_tool_slug=None,
        payload_kind="compressed",
        model=None,
        tokenizer="fallback",
        tokenizer_is_approximate=True,
        raw_payload_bytes=100,
        compressed_payload_bytes=50,
        raw_tokens=20,
        compressed_tokens=10,
        input_tokens_contributed=10,
        tokens_saved=10,
        compression_ratio=0.5,
        cache_status=None,
        aperture_version="0.1.0",
    )

    report = build_compression_report([event])

    assert "Compression Savings Report" in report
    assert "GITHUB_LIST_ISSUES" in report
