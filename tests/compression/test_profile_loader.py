from aperture.compression.profile_loader import load_compression_profile


def test_unknown_tool_uses_default_safe_profile():
    profile = load_compression_profile("UNKNOWN_TOOL")
    assert profile.mode == "safe"
    assert profile.raw_reference is True


def test_known_tool_profile_loads_balanced_rules():
    profile = load_compression_profile("GITHUB_LIST_ISSUES")
    assert profile.mode == "balanced"
    assert profile.flatten["user.login"] == "author"

