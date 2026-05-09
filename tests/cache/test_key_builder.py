from aperture.cache.key_builder import build_cache_key
from aperture.cache.policy import load_cache_policy
from aperture.types import ExecutionContext


def _context(account="acct_1"):
    return ExecutionContext("p1", "u1", "s1", account, "GITHUB", "GITHUB_LIST_ISSUES", None, None)


def test_same_params_different_order_produce_same_key():
    policy = load_cache_policy("GITHUB_LIST_ISSUES")
    assert build_cache_key("GITHUB_LIST_ISSUES", {"a": 1, "b": 2}, _context(), policy) == build_cache_key(
        "GITHUB_LIST_ISSUES", {"b": 2, "a": 1}, _context(), policy
    )


def test_missing_account_scope_prevents_caching():
    policy = load_cache_policy("GITHUB_LIST_ISSUES")
    assert build_cache_key("GITHUB_LIST_ISSUES", {"a": 1}, _context(account=None), policy) is None

