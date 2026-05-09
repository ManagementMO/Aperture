from datetime import datetime, timezone

import pytest

from aperture.observability.event_schema import event_to_dict, validate_cache_event, validate_token_event
from aperture.types import CacheEvent, TokenAttributionEvent


def _token_event():
    return TokenAttributionEvent(
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
        model=None,
        tokenizer="fallback",
        tokenizer_is_approximate=True,
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


def _cache_event(status="hit"):
    return CacheEvent(
        event_type="cache_lookup",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project_id=None,
        user_id=None,
        session_id="s1",
        connected_account_id="acct_1",
        tool_slug="GITHUB_LIST_ISSUES",
        toolkit_slug="GITHUB",
        cache_status=status,
        cache_scope="account",
        cache_key_hash="abc123",
        ttl_seconds=60,
        cached_age_seconds=1,
        api_call_avoided=True,
        tokens_saved_estimate=5,
        reason=None,
    )


def test_event_to_dict_and_validation():
    event = _token_event()
    validate_token_event(event)
    assert event_to_dict(event)["payload_kind"] == "result"


def test_token_event_rejects_negative_contribution():
    event = _token_event()
    bad = TokenAttributionEvent(**{**event.__dict__, "input_tokens_contributed": -1})
    with pytest.raises(ValueError):
        validate_token_event(bad)


def test_cache_event_rejects_invalid_status():
    with pytest.raises(ValueError):
        validate_cache_event(_cache_event(status="stale"))
