from aperture.cache.policy import load_cache_policy


def test_unknown_tools_are_not_cacheable():
    policy = load_cache_policy("UNKNOWN")
    assert policy.cacheable is False
    assert policy.reason == "deny_by_default"


def test_write_tools_are_never_cacheable():
    policy = load_cache_policy("GMAIL_SEND_EMAIL")
    assert policy.cacheable is False
    assert policy.operation_type == "write"


def test_auth_tools_are_never_cacheable():
    policy = load_cache_policy("OAUTH_REFRESH_TOKEN")
    assert policy.cacheable is False
    assert policy.operation_type == "auth"
