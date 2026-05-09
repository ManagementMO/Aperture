from datetime import datetime, timezone

from aperture.cache.reports import build_cache_report
from aperture.types import CacheEvent


def test_build_cache_report():
    event = CacheEvent(
        event_type="cache_lookup",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None,
        user_id=None,
        session_id="s1",
        connected_account_id="acct_1",
        tool_slug="GITHUB_LIST_ISSUES",
        toolkit_slug="GITHUB",
        cache_status="hit",
        cache_scope="account",
        cache_key_hash="abc123",
        ttl_seconds=60,
        cached_age_seconds=1,
        api_call_avoided=True,
        tokens_saved_estimate=10,
        reason=None,
    )

    report = build_cache_report([event])

    assert "Cache Savings Report" in report
    assert "GITHUB_LIST_ISSUES" in report
