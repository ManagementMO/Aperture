from aperture.compression.flattening import flatten_fields
from aperture.compression.profile_loader import load_compression_profile


def test_flatten_user_login_to_author():
    profile = load_compression_profile("GITHUB_LIST_ISSUES")
    payload = {"user": {"login": "nikos", "avatar_url": "x"}}
    assert flatten_fields(payload, profile)["author"] == "nikos"

